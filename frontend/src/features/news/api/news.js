// Public News API (backend: apps/news/public_views.py). Anonymous reads through the public client: no cookies, no CSRF.
import { api, data, paged, publicApi } from "../../../api/client";

const BASE = "/news";

export const getNewsConfig = () => publicApi.get(`${BASE}/config/`).then(data);
export const listNewsArticles = (params) => publicApi.get(`${BASE}/articles/`, { params }).then(paged);
export const getNewsArticle = (slug) => publicApi.get(`${BASE}/articles/${encodeURIComponent(slug)}/`).then(data);
export const listNewsCategories = () => publicApi.get(`${BASE}/categories/`).then(data);
export const getNewsFeatured = () => publicApi.get(`${BASE}/featured/`).then(data);
export const getNewsBreaking = () => publicApi.get(`${BASE}/breaking/`).then(data);
export const getNewsRelated = (slug) => publicApi.get(`${BASE}/related/${encodeURIComponent(slug)}/`).then(data);
// The page-view counter some licences require. Counts only; fire-and-forget.
export const countNewsView = (slug) => publicApi.post(`${BASE}/articles/${encodeURIComponent(slug)}/view/`).then(data);
export const submitNewsComplaint = (body) => publicApi.post(`${BASE}/takedown/`, body).then(data);

// Comments depend on who is asking (own pending comments) and writes need the CSRF header, so they use the cookie-carrying client.
export const listNewsComments = (slug, page = 1) => api.get(`${BASE}/articles/${encodeURIComponent(slug)}/comments/`, { params: { page } }).then(paged);
export const postNewsComment = (slug, body) => api.post(`${BASE}/articles/${encodeURIComponent(slug)}/comments/`, { body }).then(data);
export const deleteNewsComment = (id) => api.delete(`${BASE}/comments/${id}/`).then(data);
