// Staff-side Academy API (backend: apps/academy/views_authoring.py). Every one of these is checked on the server (staff + two-step).
import { api, data, paged } from "../../api/client";
import { ACADEMY_BASE } from "./academy";

const BASE = `${ACADEMY_BASE}/admin`;

export const adminListCourses = (params) => api.get(`${BASE}/courses/`, { params }).then(paged);
export const adminGetCourse = (id) => api.get(`${BASE}/courses/${id}/`).then(data);
export const adminCreateCourse = (body) => api.post(`${BASE}/courses/`, body).then(data);
export const adminUpdateCourse = (id, body) => api.patch(`${BASE}/courses/${id}/`, body).then(data);
export const adminDeleteCourse = (id) => api.delete(`${BASE}/courses/${id}/`);
// action: "publish" | "unpublish" | "archive"
export const adminCourseAction = (id, action) => api.post(`${BASE}/courses/${id}/${action}/`).then(data);

export const adminListLessons = (courseId) => api.get(`${BASE}/courses/${courseId}/lessons/`).then(data);
export const adminCreateLesson = (courseId, body) => api.post(`${BASE}/courses/${courseId}/lessons/`, body).then(data);
export const adminUpdateLesson = (id, body) => api.patch(`${BASE}/lessons/${id}/`, body).then(data);
export const adminDeleteLesson = (id) => api.delete(`${BASE}/lessons/${id}/`);
export const adminReorderLessons = (courseId, order) => api.post(`${BASE}/courses/${courseId}/lessons/reorder/`, { order }).then(data);