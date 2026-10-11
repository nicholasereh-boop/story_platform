// Pure helpers for the story edit screen: the form's shape and how it maps to the API.
import { fromServerDoc, emptyDoc, toServerDoc } from "../../editor/schema";

// Fields the API accepts on create/PATCH. Autosave compares and sends only the ones that changed.
export const PAYLOAD_KEYS = ["title", "slug", "excerpt", "content_json", "cover_image", "category_ids", "tag_ids", "is_featured", "seo_title", "seo_description"];

export const blankForm = () => ({
  title: "", slug: "", excerpt: "", content_json: emptyDoc(), cover: null,
  category_ids: [], tags: [], is_featured: false, seo_title: "", seo_description: "",
});

// API story -> form state (what the screen edits; cover and tags keep their display objects).
export const formFromStory = (s) => ({
  title: s.title || "",
  slug: s.slug || "",
  excerpt: s.excerpt || "",
  content_json: fromServerDoc(s.content_json),
  cover: s.cover || null,
  category_ids: (s.categories || []).map((c) => c.id),
  tags: (s.tags || []).map((t) => ({ id: t.id, name: t.name })),
  is_featured: Boolean(s.is_featured),
  seo_title: s.seo_title || "",
  seo_description: s.seo_description || "",
});

// Form state -> comparable/sendable payload. Content goes through toServerDoc, so src/width/height never leave the browser.
export const toPayloadForm = (f) => ({
  title: f.title,
  slug: f.slug,
  excerpt: f.excerpt,
  content_json: toServerDoc(f.content_json),
  cover_image: f.cover?.id ?? null,
  category_ids: [...f.category_ids].sort((a, b) => a - b),
  tag_ids: f.tags.map((t) => t.id).sort((a, b) => a - b),
  is_featured: f.is_featured,
  seo_title: f.seo_title,
  seo_description: f.seo_description,
});

// Server fields the screen shows but never edits directly.
export const metaFrom = (s) => ({
  status: s.status, published_at: s.published_at, scheduled_at: s.scheduled_at, updated_at: s.updated_at,
});

// Which error key belongs to which form field.
export const ERROR_KEY = { cover: "cover_image", tags: "tag_ids" };
