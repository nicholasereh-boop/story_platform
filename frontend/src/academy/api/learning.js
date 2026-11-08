// Learner-side Academy API (backend: apps/academy/views_learning.py). The server decides what a learner may open.
import { api, data, paged, publicApi } from "../../api/client";
import { ACADEMY_BASE } from "./academy";

export const listCourses = (params) => publicApi.get(`${ACADEMY_BASE}/courses/`, { params }).then(paged);
export const getCourse = (slug) => api.get(`${ACADEMY_BASE}/courses/${slug}/`).then(data);
export const enrollInCourse = (slug) => api.post(`${ACADEMY_BASE}/courses/${slug}/enroll/`).then(data);

export const getLesson = (id) => api.get(`${ACADEMY_BASE}/lessons/${id}/`).then(data);
export const getLessonAccess = (id) => api.get(`${ACADEMY_BASE}/lessons/${id}/access/`).then(data);
// body: { position_seconds, watched_seconds, duration_seconds }
export const saveProgress = (id, body) => api.post(`${ACADEMY_BASE}/lessons/${id}/progress/`, body).then(data);

export const listLessonComments = (id, params) => api.get(`${ACADEMY_BASE}/lessons/${id}/comments/`, { params }).then(paged);
export const postLessonComment = (id, body) => api.post(`${ACADEMY_BASE}/lessons/${id}/comments/`, { body }).then(data);
export const deleteLessonComment = (id) => api.delete(`${ACADEMY_BASE}/comments/${id}/`);

export const getMyLearning = () => api.get(`${ACADEMY_BASE}/my-learning/`).then(data);