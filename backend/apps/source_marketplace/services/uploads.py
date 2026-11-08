"""Safe handling of uploaded and imported source archives.

Nothing is ever extracted to disk and nothing is ever executed. An archive is READ entry by entry and REBUILT into a
clean ZIP, so what we store is something we produced, not something the seller handed us:

  * path traversal ("../x", absolute paths, drive letters, NUL bytes) rejects the whole archive;
  * symlinks are dropped; encrypted entries are rejected (they cannot be checked);
  * archive bombs are stopped by limits on entry count, bytes ACTUALLY read (the header's claim is not trusted),
    per-file size and compression ratio;
  * files that usually hold secrets (.env, private keys, databases ...) and dependency folders are left out;
  * text files are scanned for private keys and well-known token formats: a hit rejects the upload and names the
    FILE (never the value) so the seller can remove it and rotate the secret.
"""
import hashlib
import re
import stat
import tempfile
import zipfile
from dataclasses import dataclass, field

from django.conf import settings

CHUNK = 64 * 1024
SCAN_BYTES = 512 * 1024  # text files up to this size are scanned for secrets

EXCLUDED_DIRS = {".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".pytest_cache", ".mypy_cache", "__macosx"}
EXCLUDED_NAMES = {
    ".ds_store", "thumbs.db", ".npmrc", ".pypirc", ".netrc", ".htpasswd", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "credentials.json", "secrets.json", "secrets.yml", "secrets.yaml", "service-account.json", "serviceaccount.json",
}
EXCLUDED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".sqlite3", ".sqlite", ".db", ".pyc")
ENV_EXAMPLES = {".env.example", ".env.sample", ".env.template", ".env.dist", ".env.defaults"}

SECRET_PATTERNS = (
    ("a private key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----")),
    ("an AWS access key", re.compile(rb"\bAKIA[0-9A-Z]{16}\b")),
    ("a GitHub token", re.compile(rb"\b(?:ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{50,}\b")),
    ("a live payment key", re.compile(rb"\b[sr]k_live_[A-Za-z0-9]{16,}\b")),
    ("a Slack token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("a Google API key", re.compile(rb"\bAIza[0-9A-Za-z_\-]{35}\b")),
)


class ArchiveRejected(Exception):
    """The archive cannot be accepted. `message` is safe to show to the seller."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


@dataclass
class SanitizedArchive:
    file: object  # a temporary file object, positioned at 0
    size: int
    sha256: str
    file_count: int
    report: dict = field(default_factory=dict)

    def close(self):
        try:
            self.file.close()
        except Exception:
            pass


def limits():
    return {
        "archive": int(settings.MARKETPLACE_MAX_ARCHIVE_BYTES),
        "unpacked": int(settings.MARKETPLACE_MAX_UNPACKED_BYTES),
        "files": int(settings.MARKETPLACE_MAX_FILES),
        "file": int(settings.MARKETPLACE_MAX_FILE_BYTES),
    }


def _mb(n):
    return f"{n / (1024 * 1024):.0f} MB"


def normalise_name(raw):
    """A safe, relative, forward-slash path, or raises ArchiveRejected for anything that tries to escape."""
    if "\x00" in raw:
        raise ArchiveRejected("The archive contains an invalid file name.")
    name = raw.replace("\\", "/")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise ArchiveRejected("The archive contains absolute paths, which are not allowed.")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ArchiveRejected("The archive contains paths that try to leave its folder (\"..\"), so it was rejected.")
    if len("/".join(parts)) > 400 or any(len(p) > 255 for p in parts):
        raise ArchiveRejected("The archive contains a file name that is too long.")
    return "/".join(parts)


def _is_symlink(info):
    mode = info.external_attr >> 16
    return bool(mode) and stat.S_ISLNK(mode)


def exclusion_reason(path):
    """Why this file is left out of the package, or None to keep it."""
    parts = path.split("/")
    lowered = [p.lower() for p in parts]
    if any(p in EXCLUDED_DIRS for p in lowered[:-1]):
        return "dependency or version-control folder"
    name = lowered[-1]
    if name in ENV_EXAMPLES:
        return None
    if name == ".env" or name.startswith(".env."):
        return "environment file (may hold secrets)"
    if name in EXCLUDED_NAMES or name.endswith(EXCLUDED_SUFFIXES):
        return "credential, key or database file"
    return None


def _looks_binary(head):
    return b"\x00" in head[:2048]


def scan_for_secrets(data):
    """The label of the first secret pattern found in `data`, or None."""
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(data):
            return label
    return None


def _common_root(paths):
    """The single top-level folder every file sits in (GitHub zipballs, zipped project folders), else None."""
    roots = {p.split("/", 1)[0] for p in paths}
    if len(roots) == 1 and all("/" in p for p in paths):
        return roots.pop()
    return None


def sanitize_archive(source, *, size_hint=None):
    """Validate and rebuild a ZIP. `source` is a seekable binary file. Returns a SanitizedArchive or raises ArchiveRejected."""
    cap = limits()
    source.seek(0, 2)
    size = source.tell()
    source.seek(0)
    if size == 0:
        raise ArchiveRejected("The file is empty.")
    if size > cap["archive"]:
        raise ArchiveRejected(f"The archive is larger than the {_mb(cap['archive'])} limit.")
    if not zipfile.is_zipfile(source):
        raise ArchiveRejected("This is not a valid ZIP file.")
    source.seek(0)

    try:
        zf = zipfile.ZipFile(source)
    except zipfile.BadZipFile:
        raise ArchiveRejected("This ZIP file is damaged.")

    with zf:
        infos = zf.infolist()
        if len(infos) > cap["files"] * 2:  # directory entries count too
            raise ArchiveRejected(f"The archive has too many entries (more than {cap['files']} files).")

        entries, seen = [], set()
        symlinks = 0
        for info in infos:
            if info.flag_bits & 0x1:
                raise ArchiveRejected("The archive is password-protected, so it cannot be checked. Upload it without a password.")
            name = normalise_name(info.filename)
            if info.is_dir() or not name:
                continue
            if _is_symlink(info):
                symlinks += 1
                continue
            if name in seen:
                raise ArchiveRejected("The archive lists the same file twice, so it was rejected.")
            seen.add(name)
            entries.append((name, info))

        kept, excluded = [], []
        for name, info in entries:
            reason = exclusion_reason(name)
            (excluded if reason else kept).append((name, info, reason))
        if len(kept) > cap["files"]:
            raise ArchiveRejected(f"The archive has more than {cap['files']} files after removing dependency folders.")
        if not kept:
            raise ArchiveRejected("The archive has no files left after removing secrets and dependency folders.")

        root = _common_root([n for n, _, _ in kept])
        flagged = []
        total = 0
        out = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
        digest = hashlib.sha256()
        try:
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dest:
                for name, info, _ in kept:
                    if info.file_size > cap["file"]:
                        raise ArchiveRejected(f"\"{name[:80]}\" is larger than the {_mb(cap['file'])} per-file limit.")
                    if info.compress_size and info.file_size > 10 * 1024 * 1024 and info.file_size / info.compress_size > 1000:
                        raise ArchiveRejected("The archive looks like a decompression bomb and was rejected.")
                    target = name[len(root) + 1:] if root else name
                    zinfo = zipfile.ZipInfo(target, date_time=info.date_time if info.date_time[0] >= 1980 else (1980, 1, 1, 0, 0, 0))
                    zinfo.compress_type = zipfile.ZIP_DEFLATED
                    zinfo.external_attr = 0o644 << 16
                    with zf.open(info) as src, dest.open(zinfo, "w", force_zip64=info.file_size > 2**30) as dst:
                        read = 0
                        head = src.read(min(CHUNK, SCAN_BYTES))
                        scan_buf = bytearray(head)
                        scannable = not _looks_binary(head)
                        chunk = head
                        while chunk:
                            read += len(chunk)
                            total += len(chunk)
                            if read > cap["file"] or total > cap["unpacked"]:
                                raise ArchiveRejected(f"The archive expands to more than {_mb(cap['unpacked'])}, so it was rejected.")
                            dst.write(chunk)
                            chunk = src.read(CHUNK)
                            if scannable and chunk and len(scan_buf) < SCAN_BYTES:
                                scan_buf += chunk[: SCAN_BYTES - len(scan_buf)]
                        if scannable:
                            label = scan_for_secrets(bytes(scan_buf))
                            if label:
                                flagged.append((target, label))
                if flagged:
                    shown = "; ".join(f"{path[:80]} (looks like {label})" for path, label in flagged[:8])
                    more = f" and {len(flagged) - 8} more" if len(flagged) > 8 else ""
                    raise ArchiveRejected(
                        f"Possible secrets were found in: {shown}{more}. Remove them, rotate the credentials, and upload again."
                    )
            if total > 100 * 1024 * 1024 and total / max(size, 1) > 200:
                raise ArchiveRejected("The archive's compression ratio is suspicious, so it was rejected.")
            out.seek(0, 2)
            result_size = out.tell()
            if result_size > cap["archive"]:
                raise ArchiveRejected(f"The cleaned archive is still larger than the {_mb(cap['archive'])} limit.")
            out.seek(0)
            for block in iter(lambda: out.read(CHUNK), b""):
                digest.update(block)
            out.seek(0)
        except ArchiveRejected:
            out.close()
            raise
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError, OSError, ValueError):
            out.close()
            raise ArchiveRejected("This ZIP file could not be read. It may be damaged or use an unsupported feature.")
        except Exception:
            out.close()
            raise

    report = {
        "excluded_count": len(excluded),
        "excluded": [{"path": n[:120], "reason": r} for n, _, r in excluded[:50]],
        "symlinks_removed": symlinks,
        "root_folder_removed": root or "",
    }
    return SanitizedArchive(file=out, size=result_size, sha256=digest.hexdigest(), file_count=len(kept), report=report)


def safe_download_name(project_slug, kind, version):
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{project_slug}-{kind}-v{version}").strip("-.")
    return f"{clean or 'package'}.zip"


def clean_version(value):
    """"" when blank (the package keeps its current version, or starts at 1.0.0); otherwise the cleaned version."""
    value = str(value or "").strip()
    if not value:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,29}", value):
        raise ArchiveRejected("The version may only contain letters, numbers, dots, dashes and +, up to 30 characters.")
    return value

