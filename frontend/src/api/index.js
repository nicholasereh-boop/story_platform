// One small function per backend endpoint. Components never build URLs themselves.
import { api, data, paged } from "./client";

// ---- auth ----
export const me = () => api.get("/auth/me/").then(data); // user, or null when logged out
export const login = (body) => api.post("/auth/login/", body).then(data);
export const logout = () => api.post("/auth/logout/").then(data);
export const register = (body) => api.post("/auth/register/", body).then(data); // also logs the new user in
export const requestPasswordReset = (email) => api.post("/auth/password/reset/", { email }).then(data);
export const resetPassword = (body) => api.post("/auth/password/reset/confirm/", body).then(data); // {uid, token, password}
export const verifyEmail = (key) => api.post("/auth/email/verify/", { key }).then(data);
export const resendVerification = () => api.post("/auth/email/resend/").then(data);
export const updateProfile = (body) => api.patch("/auth/me/", body).then(data); // {display_name, bio}
export const providers = () => api.get("/auth/providers/").then(data); // {google: bool}

// ---- stories ----
export const listStories = (params) => api.get("/admin/stories/", { params }).then(paged);
export const getStory = (id) => api.get(`/admin/stories/${id}/`).then(data);
export const createStory = (body) => api.post("/admin/stories/", body).then(data);
export const patchStory = (id, body, { autosave = false } = {}) =>
  api.patch(`/admin/stories/${id}/`, body, { params: autosave ? { autosave: 1 } : undefined }).then(data);
export const deleteStory = (id) => api.delete(`/admin/stories/${id}/`);
// action: publish | unpublish | archive | schedule (schedule needs {scheduled_at})
export const storyAction = (id, action, body) => api.post(`/admin/stories/${id}/${action}/`, body).then(data);
export const listRevisions = (id, params) => api.get(`/admin/stories/${id}/revisions/`, { params }).then(paged);
export const restoreRevision = (id, revisionId) => api.post(`/admin/stories/${id}/revisions/${revisionId}/restore/`).then(data);

// ---- categories & tags ----
export const listCategories = () => api.get("/admin/categories/").then(data);
export const createCategory = (name) => api.post("/admin/categories/", { name }).then(data);
export const searchTags = (q) => api.get("/admin/tags/", { params: q ? { q } : undefined }).then(data);
export const createTag = (name) => api.post("/admin/tags/", { name }).then(data);

// ---- media ----
export const listMedia = (params) => api.get("/admin/media/", { params }).then(paged);
export const getMedia = (id) => api.get(`/admin/media/${id}/`).then(data); // includes used_in
export const uploadMedia = (files, onProgress) => {
  const form = new FormData();
  Array.from(files).forEach((file) => form.append("files", file));
  return api
    .post("/admin/media/", form, {
      onUploadProgress: (e) => onProgress?.(e.total ? e.loaded / e.total : null),
    })
    .then(data);
};
export const updateMedia = (id, body) => api.patch(`/admin/media/${id}/`, body).then(data);
export const replaceMedia = (id, file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post(`/admin/media/${id}/replace/`, form).then(data);
};
export const deleteMedia = (id, force = false) => api.delete(`/admin/media/${id}/`, { params: force ? { force: 1 } : undefined });

// ---- comment moderation (staff) ----
export const adminListComments = (params) => api.get("/admin/comments/", { params }).then(paged);
export const setCommentStatus = (id, status) => api.patch(`/admin/comments/${id}/`, { status }).then(data);
export const listCommentReports = (id) => api.get(`/admin/comments/${id}/reports/`).then(data);
export const dismissCommentReports = (id) => api.post(`/admin/comments/${id}/dismiss-reports/`).then(data);
export const getCommentSettings = () => api.get("/admin/comment-settings/").then(data);
export const setCommentSettings = (body) => api.patch("/admin/comment-settings/", body).then(data);

// ---- analytics (staff). params: {days} or {from, to}; daily also takes granularity, stories takes limit ----
export const analyticsOverview = (params) => api.get("/admin/analytics/overview/", { params }).then(data);
export const analyticsDaily = (params) => api.get("/admin/analytics/daily/", { params }).then(data);
export const analyticsStories = (params) => api.get("/admin/analytics/stories/", { params }).then(data);
export const analyticsTraffic = (params) => api.get("/admin/analytics/traffic/", { params }).then(data);

// Phase 10: security and privacy endpoints live in their own file.
export * from "./security";
