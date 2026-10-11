// Reader endpoints for likes and comments (docs/ENGAGEMENT.md). They use the cookie-carrying client because
// the answers depend on who is asking (liked?, own pending comments) and writes need the CSRF header.
import { api, data, paged } from "./client";

const slugPath = (slug) => `/stories/${encodeURIComponent(slug)}`;

// ---- likes ----
export const getLikes = (slug) => api.get(`${slugPath(slug)}/likes/`).then(data); // {count, liked}
export const likeStory = (slug) => api.post(`${slugPath(slug)}/like/`).then(data); // idempotent
export const unlikeStory = (slug) => api.delete(`${slugPath(slug)}/like/`).then(data); // idempotent

// ---- comments ----
export const listComments = (slug, page = 1) => api.get(`${slugPath(slug)}/comments/`, { params: { page } }).then(paged);
export const createComment = (slug, body, parent) =>
  api.post(`${slugPath(slug)}/comments/`, parent ? { body, parent } : { body }).then(data);
export const editComment = (id, body) => api.patch(`/comments/${id}/`, { body }).then(data);
export const deleteComment = (id) => api.delete(`/comments/${id}/`).then(data);
export const reportComment = (id, reason) => api.post(`/comments/${id}/report/`, { reason }).then(data);
