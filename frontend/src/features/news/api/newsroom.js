// Staff newsroom API (backend: apps/news/views*.py). Every endpoint checks is_staff on the server; these pages are a convenience.
import { api, data, paged } from "../../../api/client";

const A = "/news/admin";

// sources and rights
export const listSources = (params) => api.get(`${A}/sources/`, { params }).then(paged);
export const getSource = (id) => api.get(`${A}/sources/${id}/`).then(data);
export const createSource = (body) => api.post(`${A}/sources/`, body).then(data);
export const updateSource = (id, body) => api.patch(`${A}/sources/${id}/`, body).then(data);
// action: approve | suspend | reject | activate | deactivate
export const sourceAction = (id, action, body) => api.post(`${A}/sources/${id}/${action}/`, body).then(data);
export const pollSource = (id) => api.post(`${A}/sources/${id}/poll/`).then(data);
export const createRights = (sourceId, body) => api.post(`${A}/sources/${sourceId}/rights/`, body).then(data);
export const updateRights = (id, body) => api.patch(`${A}/rights/${id}/`, body).then(data);
// action: approve | revoke
export const rightsAction = (id, action, body) => api.post(`${A}/rights/${id}/${action}/`, body).then(data);

// categories
export const listNewsCategoriesAdmin = () => api.get(`${A}/categories/`).then(data);
export const createNewsCategory = (body) => api.post(`${A}/categories/`, body).then(data);

// articles
export const listNewsroom = (params) => api.get(`${A}/articles/`, { params }).then(paged);
export const getNewsroomArticle = (id) => api.get(`${A}/articles/${id}/`).then(data);
export const createNewsArticle = (body) => api.post(`${A}/articles/`, body).then(data);
export const updateNewsArticle = (id, body) => api.patch(`${A}/articles/${id}/`, body).then(data);
// action: submit | publish | schedule | reject | withdraw | restore
export const newsArticleAction = (id, action, body) => api.post(`${A}/articles/${id}/${action}/`, body).then(data);
export const listNewsRevisions = (id) => api.get(`${A}/articles/${id}/revisions/`).then(data);

// assets
export const createNewsAsset = (articleId, body) => api.post(`${A}/articles/${articleId}/assets/`, body).then(data);
export const updateNewsAsset = (id, body) => api.patch(`${A}/assets/${id}/`, body).then(data);
export const deleteNewsAsset = (id) => api.delete(`${A}/assets/${id}/`);
// action: clear | reject
export const newsAssetAction = (id, action) => api.post(`${A}/assets/${id}/${action}/`).then(data);

// importing, ingestion health, takedowns
export const previewImport = (body) => api.post(`${A}/articles/import-preview/`, body).then(data);
export const importArticle = (body) => api.post(`${A}/articles/import/`, body).then(data);
export const listIngestionRuns = (params) => api.get(`${A}/ingestion/`, { params }).then(paged);
export const ingestionHealth = () => api.get(`${A}/ingestion/health/`).then(data);
export const listTakedowns = (params) => api.get(`${A}/takedowns/`, { params }).then(paged);
// action: hold | uphold | dismiss
export const takedownAction = (id, action, body) => api.post(`${A}/takedowns/${id}/${action}/`, body).then(data);

// comments moderation and monitoring
export const listCommentsAdmin = (params) => api.get(`${A}/comments/`, { params }).then(paged);
// action: approve | hide | delete
export const commentAction = (id, action) => api.post(`${A}/comments/${id}/${action}/`).then(data);
export const getMonitoring = () => api.get(`${A}/monitoring/`).then(data);
