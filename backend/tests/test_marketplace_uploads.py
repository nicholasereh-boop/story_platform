"""The archive sanitiser: every way a ZIP can be hostile, plus the normal case."""
import io
import zipfile

import pytest

from apps.source_marketplace.services.uploads import ArchiveRejected, sanitize_archive

from .marketplace_helpers import make_zip


def run(files=None, **kwargs):
    return sanitize_archive(io.BytesIO(make_zip(files, **kwargs)))


def names_of(archive):
    with zipfile.ZipFile(archive.file) as zf:
        return sorted(zf.namelist())


def test_a_clean_archive_is_rebuilt_and_its_single_top_folder_removed():
    a = run({"index.html": "<h1>x</h1>", "src/app.js": "ok"}, root="my-shop-abc123")
    assert names_of(a) == ["index.html", "src/app.js"]
    assert a.file_count == 2 and a.size > 0 and len(a.sha256) == 64
    assert a.report["root_folder_removed"] == "my-shop-abc123"


@pytest.mark.parametrize("bad", ["../evil.txt", "a/../../evil.txt", "/etc/passwd", "C:/windows/x.txt", "..\\evil.txt", "ok/..\\..\\evil.txt"])
def test_paths_that_escape_the_folder_reject_the_whole_archive(bad):
    with pytest.raises(ArchiveRejected):
        run({"fine.txt": "ok", bad: "x"})


def test_env_files_keys_databases_and_dependency_folders_are_left_out_and_reported():
    a = run({
        "app.py": "print(1)", ".env": "SECRET=1", ".env.local": "A=1", ".env.example": "A=", "keys/server.pem": "x",
        "node_modules/lib/index.js": "x", ".git/config": "x", "db.sqlite3": "x", "id_rsa": "x",
    })
    assert names_of(a) == [".env.example", "app.py"]
    reasons = {e["path"] for e in a.report["excluded"]}
    assert {".env", ".env.local", "keys/server.pem", "node_modules/lib/index.js", "db.sqlite3", "id_rsa"} <= reasons
    assert a.report["excluded_count"] == 7


def test_a_file_that_holds_a_secret_rejects_the_upload_and_names_the_file_not_the_value():
    key = "AKIA" + "ABCDEFGHIJKLMNOP"
    with pytest.raises(ArchiveRejected) as err:
        run({"config/settings.py": f"AWS = '{key}'", "ok.txt": "fine"})
    assert "config/settings.py" in err.value.message and key not in err.value.message
    with pytest.raises(ArchiveRejected):
        run({"deploy.sh": "-----BEGIN " + "RSA PRIVATE KEY-----\nabc\n-----END " + "RSA PRIVATE KEY-----"})  # split: the repo secret scan reads this file too
    with pytest.raises(ArchiveRejected):
        run({"pay.js": "const k = 'sk_live_" + "a" * 24 + "'"})


def test_binary_files_are_not_scanned_as_text():
    a = run({"logo.bin": b"\x00\x01AKIA" + b"ABCDEFGHIJKLMNOP" + b"\x00", "readme.md": "hi"})
    assert a.file_count == 2


def test_symlinks_are_dropped_not_stored():
    link = zipfile.ZipInfo("link-to-etc")
    link.external_attr = 0o120777 << 16
    a = run({"real.txt": "x"}, extra_infos=[(link, "/etc/passwd")])
    assert names_of(a) == ["real.txt"] and a.report["symlinks_removed"] == 1


def test_encrypted_entries_are_rejected_because_they_cannot_be_checked():
    data = bytearray(make_zip({"a.txt": "x"}))
    at = data.index(b"PK\x01\x02")  # central directory record; general-purpose flags sit at offset 8
    data[at + 8] |= 0x1  # (writestr resets flag_bits, so the bit is set on the finished bytes)
    with pytest.raises(ArchiveRejected, match="password"):
        sanitize_archive(io.BytesIO(bytes(data)))


def test_duplicate_names_are_rejected():
    with pytest.raises(ArchiveRejected, match="twice"):
        run({"a.txt": "one"}, extra_infos=[(zipfile.ZipInfo("a.txt"), "two")])


def test_too_many_files_and_oversized_expansion_are_rejected(settings):
    settings.MARKETPLACE_MAX_FILES = 3
    with pytest.raises(ArchiveRejected, match="too many|more than"):
        run({f"f{i}.txt": "x" for i in range(10)})
    settings.MARKETPLACE_MAX_FILES = 5000
    settings.MARKETPLACE_MAX_UNPACKED_BYTES = 1024 * 1024
    with pytest.raises(ArchiveRejected, match="expands"):
        run({"zeros.txt": "0" * (3 * 1024 * 1024)})  # tiny when compressed, 3 MB when read: the bytes READ are counted


def test_a_single_huge_file_is_rejected_even_if_the_header_lies_about_nothing(settings):
    settings.MARKETPLACE_MAX_FILE_BYTES = 1024
    with pytest.raises(ArchiveRejected, match="per-file"):
        run({"big.txt": "x" * 5000})


def test_archive_size_limit_and_non_zip_and_empty(settings):
    settings.MARKETPLACE_MAX_ARCHIVE_BYTES = 100
    with pytest.raises(ArchiveRejected, match="larger"):
        sanitize_archive(io.BytesIO(make_zip({"a.txt": "x" * 5000})))
    settings.MARKETPLACE_MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
    with pytest.raises(ArchiveRejected, match="not a valid ZIP"):
        sanitize_archive(io.BytesIO(b"this is not a zip" * 20))
    with pytest.raises(ArchiveRejected, match="empty"):
        sanitize_archive(io.BytesIO(b""))


def test_an_archive_with_only_excluded_files_is_rejected():
    with pytest.raises(ArchiveRejected, match="no files left"):
        run({".env": "x", "node_modules/a.js": "x"})


def test_a_corrupt_zip_is_a_clean_rejection_not_a_crash():
    data = bytearray(make_zip({"a.txt": "hello world" * 100}))
    data[40:60] = b"\xff" * 20  # damage inside the compressed stream
    with pytest.raises(ArchiveRejected):
        sanitize_archive(io.BytesIO(bytes(data)))
