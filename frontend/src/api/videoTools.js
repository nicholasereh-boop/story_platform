// Video tools endpoints (backend: apps/video_tools). Inspecting a link needs no login but still goes through the
// session client so the CSRF header is sent; downloads need a login.
import { api, data } from "./client";
import { explainBlobError, filenameFromDisposition } from "../utils/saveBlob";

const BASE = "/video-tools";

export const inspectLink = (url) => api.post(`${BASE}/inspect/`, { url }).then(data);
export const requestDownload = ({ url, format, authorizationConfirmed }) =>
  api.post(`${BASE}/downloads/`, { url, format, authorization_confirmed: authorizationConfirmed }).then(data);
export const getJob = (id) => api.get(`${BASE}/downloads/${id}/`).then(data);
export const removeJob = (id) => api.delete(`${BASE}/downloads/${id}/`);

export async function fetchJobFile(id, fallbackName = "video") {
  try {
    const res = await api.get(`${BASE}/downloads/${id}/file/`, { responseType: "blob" });
    return { blob: res.data, filename: filenameFromDisposition(res.headers?.["content-disposition"], fallbackName) };
  } catch (err) {
    throw await explainBlobError(err);
  }
}

export const TERMINAL = ["done", "failed", "cancelled", "expired"];
