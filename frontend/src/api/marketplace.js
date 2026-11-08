// One function per marketplace endpoint (backend: apps/source_marketplace, docs/extension road map/ARCHITECTURE.md).
// Reads of the public catalogue need no login; everything else carries the session cookie + CSRF header.
import { api, data, paged, publicApi } from "./client";
import { explainBlobError, filenameFromDisposition } from "../utils/saveBlob";

const enc = encodeURIComponent;
const BASE = "/marketplace";

// ---- public
export const listProjects = (params) => publicApi.get(`${BASE}/projects/`, { params }).then(paged); // q, tech, free, ordering, page
// The currency (US dollars) and the "backend code is always paid" rule, so the pages describe pricing truthfully.
export const getMarketplaceConfig = () => publicApi.get(`${BASE}/config/`).then(data);
export const listTechnologies = () => publicApi.get(`${BASE}/technologies/`).then(data);
// Uses the session client on purpose: the answer includes what THIS reader may do (download, already bought, own project).
export const getProject = (slug) => api.get(`${BASE}/projects/${enc(slug)}/`).then(data);

// ---- seller
export const createProject = (body) => api.post(`${BASE}/projects/`, body).then(data);
export const updateProject = (id, body) => api.patch(`${BASE}/projects/${id}/`, body).then(data);
export const deleteProject = (id) => api.delete(`${BASE}/projects/${id}/`);
export const myProjects = (params) => api.get(`${BASE}/my/projects/`, { params }).then(paged);
export const myProject = (id) => api.get(`${BASE}/my/projects/${id}/`).then(data);
export const submitProject = (id) => api.post(`${BASE}/projects/${id}/submit/`).then(data);
export const unpublishProject = (id) => api.post(`${BASE}/projects/${id}/unpublish/`).then(data);
export const archiveProject = (id) => api.post(`${BASE}/projects/${id}/archive/`).then(data);

export function uploadScreenshots(id, files, altText = "") {
  const form = new FormData();
  [...files].forEach((f) => form.append("files", f));
  if (altText) form.append("alt_text", altText);
  return api.post(`${BASE}/projects/${id}/screenshots/`, form).then(data);
}
export const deleteScreenshot = (id, shotId) => api.delete(`${BASE}/projects/${id}/screenshots/${shotId}/`);

export function uploadPackage(id, { kind, file, version }, onProgress) {
  const form = new FormData();
  form.append("kind", kind);
  form.append("file", file);
  if (version) form.append("version", version);
  return api
    .post(`${BASE}/projects/${id}/upload/`, form, { onUploadProgress: (e) => onProgress?.(e.total ? e.loaded / e.total : 0) })
    .then(data);
}
// The access token (private repositories only) is sent once, over HTTPS, in this request. It is never kept in state
// beyond the form field, never stored in the browser and never shown again.
export const importFromGitHub = (id, body) => api.post(`${BASE}/projects/${id}/github-import/`, body).then(data);
export const removePackage = (id, kind) => api.delete(`${BASE}/projects/${id}/packages/${kind}/`).then(data);

// ---- buying
export const startCheckout = (id, kind) => api.post(`${BASE}/projects/${id}/checkout/`, { kind }).then(data);
export const verifyPayment = (reference) => api.post(`${BASE}/payments/verify/`, { reference }).then(data);
export const myPurchases = (params) => api.get(`${BASE}/purchases/`, { params }).then(paged);

// The only way to a package. Resolves to {blob, filename}; on failure the error carries the server's sentence in err.friendly.
export async function downloadPackage(packageId, fallbackName = "package.zip") {
  try {
    const res = await api.get(`${BASE}/packages/${packageId}/download/`, { responseType: "blob" });
    return { blob: res.data, filename: filenameFromDisposition(res.headers?.["content-disposition"], fallbackName) };
  } catch (err) {
    throw await explainBlobError(err);
  }
}

// ---- staff moderation
export const adminProjects = (params) => api.get("/admin/marketplace/projects/", { params }).then(paged);
export const moderateProject = (id, action, body = {}) => api.post(`/admin/marketplace/projects/${id}/${action}/`, body).then(data);
