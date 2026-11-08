// Academy API, shared parts (backend: apps/academy, docs/extension road map/ARCHITECTURE.md). Later phases add their own files
// next to this one (authoring.js, learning.js, paid.js); they all use the same clients as the rest of the site.
import { data, publicApi } from "../../api/client";

export const ACADEMY_BASE = "/academy";

// What the Academy pages need to describe themselves truthfully (currency, whether payments are switched on).
export const getAcademyConfig = () => publicApi.get(`${ACADEMY_BASE}/config/`).then(data);