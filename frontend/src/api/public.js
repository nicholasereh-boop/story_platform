// One function per PUBLIC endpoint (docs/PUBLIC_API.md). Anonymous, read-only. Lists resolve to
// {items, pagination}; the others to the bare data.
import { data, paged, publicApi } from "./client";

export const getStories = (params) => publicApi.get("/stories/", { params }).then(paged); // category, tag, featured, page, page_size
export const getStory = (slug) => publicApi.get(`/stories/${encodeURIComponent(slug)}/`).then(data);
export const getRelatedStories = (slug) => publicApi.get(`/stories/${encodeURIComponent(slug)}/related/`).then(data);
export const getCategories = () => publicApi.get("/categories/").then(data);
export const getCategoryStories = (slug, params) => publicApi.get(`/categories/${encodeURIComponent(slug)}/stories/`, { params }).then(paged);
export const getTags = () => publicApi.get("/tags/").then(data);
export const searchStories = (q, params) => publicApi.get("/search/", { params: { q, ...params } }).then(paged);
