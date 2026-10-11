# Public API (Phase 7, extended in Phase 8)

Read-only endpoints for the public website. **No login, GET only** (other methods return 405). Likes and comments (Phase 8) are
reader actions with their own endpoints, documented in `ENGAGEMENT.md`. Same envelope as the rest
of the API: `{"data", "pagination", "errors", "message"}`. All paths are under `/api/v1/`.

Rules that apply to every endpoint:

- Only **public** stories are ever returned: `status = published` **and** `published_at` already in the past
  (`Story.objects.public()`). Drafts, scheduled, archived and future-dated stories never appear in a list, search, related
  list, count or sitemap list. Asking for one directly gives **404** (never 403).
- Scheduled stories whose time has come are published on the spot (`publish_due()`), no need to wait for Celery.
- Throttled per IP with the scope `public_read` (default `120/min`, override with `THROTTLE_PUBLIC_READ=300/min`). This replaces the site-wide
  anonymous limit of 100/hour for these views. Exceeding it returns 429.
- Responses never contain: `status`, `scheduled_at`, user ids or emails, `view_count`, revisions,
  `search_text`, or the media library id of an image. (Phase 8 deliberately exposes `like_count` and `comment_count`, see below.)
- Pagination: 12 per page, `?page=`, optional `?page_size=` up to 50. `pagination` is `{count, page, page_size, total_pages, has_next, has_previous}`.

## Story list item (used by every list)

| Field | Type | Notes |
|---|---|---|
| `id` | int | story id |
| `title`, `slug`, `excerpt` | string | excerpt is never empty (generated from the text when the editor left it blank) |
| `cover` | object or null | `{url, alt_text, width, height}` |
| `categories` | array | `[{name, slug}]` |
| `tags` | array | `[{name, slug}]` |
| `author` | string or null | display name only |
| `published_at` | ISO datetime | |
| `reading_minutes` | int | words / 200, rounded up, minimum 1 |
| `is_featured` | bool | |
| `like_count` | int | number of likes (Phase 8) |
| `comment_count` | int | number of APPROVED comments, replies included (Phase 8) |

## Endpoints

### `GET /stories/`
Public stories, newest published first, paginated.
Filters: `?category=<slug>`, `?tag=<slug>` (both can be combined), `?featured=1`, `?page=`. An unknown slug gives an empty list (200).

### `GET /stories/{slug}/`
One story: all list fields plus

| Field | Notes |
|---|---|
| `content_json` | TipTap JSON (see `CONTENT_SCHEMA.md`). Image nodes carry read-only `src`, `width`, `height` |
| `seo_title` | falls back to `title` |
| `seo_description` | falls back to `excerpt` |
| `canonical_path` | `"/stories/<slug>"` (the frontend adds its own origin) |
| `updated_at` | ISO datetime |
| `liked_by_me` | bool, **only for a logged-in reader** (Phase 8). Absent for visitors |

`404` when the story does not exist or is not public.

The detail response is the one public response that can differ per reader, so it always sends `Vary: Cookie`, and
`Cache-Control: private` when the reader is logged in (the body then contains `liked_by_me`). A shared cache must not
store the logged-in variant. The website itself reads this endpoint without cookies, so it stays cacheable there.

### `GET /stories/{slug}/related/`
Up to **4** public stories that share categories or tags with this story, ordered by the number of shared terms
(descending), then newest. Never includes the story itself. Not paginated. Empty list when the story has no categories or tags.
`404` when the story is not public.

### `GET /categories/`
Only categories that have at least one public story. `[{name, slug, description, story_count}]` where `story_count` counts **public**
stories only. Not paginated, ordered by name.

### `GET /categories/{slug}/stories/`
Paginated list items of one category. `404` if the category does not exist **or has no public story**.

### `GET /tags/`
Only tags with at least one public story. `[{name, slug, story_count}]`, public stories only, ordered by name. Not paginated.
(Stories of a tag: `GET /stories/?tag=<slug>`.)

### `GET /search/?q=`
Case-insensitive match on title, excerpt and the plain text of the story. Paginated list items, newest first.
`q` must be **2 to 100 characters** after trimming, otherwise `400` with `message: "Search must be 2 to 100 characters."`.

### `GET /sitemap-data/`
`[{slug, updated_at}]` of all public stories (newest first, at most 5000), **cached for 5 minutes**. Meant for a future `sitemap.xml`
generator; the page URL is `/stories/<slug>`.
