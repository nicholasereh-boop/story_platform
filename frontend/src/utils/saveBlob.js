// Saving a file the server streamed to us (source packages, finished downloads).

// The file name from a Content-Disposition header, made safe: no folders, no odd characters.
export function filenameFromDisposition(header, fallback = "download") {
  let name = "";
  const star = /filename\*\s*=\s*(?:UTF-8'')?([^;]+)/i.exec(header || "");
  const plain = /filename\s*=\s*"?([^";]+)"?/i.exec(header || "");
  try {
    name = star ? decodeURIComponent(star[1].trim()) : plain ? plain[1].trim() : "";
  } catch {
    name = plain ? plain[1].trim() : "";
  }
  name = name.split(/[\\/]/).pop().replace(/[^A-Za-z0-9._ -]+/g, "_").replace(/^[. ]+/, "").slice(0, 120);
  return name || fallback;
}

export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Blob.text() where it exists, FileReader where it does not (older browsers).
function readBlobText(blob) {
  if (typeof blob.text === "function") return blob.text();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

// When a download fails, axios hands us the error body as a Blob. Read the server's sentence out of it so the person sees
// "Buy this package to download it." instead of a generic message.
export async function explainBlobError(err) {
  const body = err?.response?.data;
  if (typeof Blob !== "undefined" && body instanceof Blob) {
    try {
      const json = JSON.parse(await readBlobText(body));
      if (typeof json.message === "string" && json.message) err.friendly = json.message;
    } catch {
      /* keep the generic message */
    }
  }
  return err;
}
