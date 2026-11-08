// Paid-course API (backend: apps/academy/views_paid.py). The price is read on the server; the browser only asks to start a payment.
import { api, data, paged } from "../../api/client";
import { ACADEMY_BASE } from "./academy";

export const startCourseCheckout = (courseId) => api.post(`${ACADEMY_BASE}/courses/${courseId}/checkout/`).then(data);
export const verifyCoursePayment = (reference) => api.post(`${ACADEMY_BASE}/payments/verify/`, { reference }).then(data);
export const getMyOrders = (params) => api.get(`${ACADEMY_BASE}/orders/`, { params }).then(paged);

// Staff only (checked on the server)
export const adminListOrders = (params) => api.get(`${ACADEMY_BASE}/admin/orders/`, { params }).then(paged);
export const adminRefundOrder = (id) => api.post(`${ACADEMY_BASE}/admin/orders/${id}/refund/`).then(data);
export const adminCourseAccess = (courseId) => api.get(`${ACADEMY_BASE}/admin/courses/${courseId}/access/`).then(data);
export const adminGrantAccess = (courseId, body) => api.post(`${ACADEMY_BASE}/admin/courses/${courseId}/access/`, body).then(data);
export const adminRevokeAccess = (courseId, email) => api.delete(`${ACADEMY_BASE}/admin/courses/${courseId}/access/`, { data: { email } }).then(data);