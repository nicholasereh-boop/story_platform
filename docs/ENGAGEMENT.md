# Reader engagement (Phase 8): likes, comments, moderation, accounts

All paths are under `/api/v1/`. Every response uses the usual envelope `{data, pagination, errors, message}`.
Writes use session cookie auth + the CSRF header (`X-CSRFToken`), exactly like the rest of the API.

## Likes (`apps/reactions`)

| Method and path | Who | Result |
|---|---|---|
| `POST /stories/{slug}/like/` | logged in | `200 {count, liked: true}`. Idempotent: liking twice leaves one like and returns the same answer |
| `DELETE /stories/{slug}/like/` | logged in | `200 {count, liked: false}`. Idempotent: unliking when not liked is still 200 |
| `GET /stories/{slug}/likes/` | anyone | `200 {count, liked}`. `liked` is always `false` for visitors |

- Only **public** stories (published and `published_at` in the past) can be liked. Anything else is `404`.
- Anonymous `POST`/`DELETE` is refused with `403` in the standard error envelope.
- The slug is used in the URL (the public identifier).
- `Like` has a database `UNIQUE(user, story)`. Two simultaneous requests cannot both count: the loser hits the constraint
  and is treated as "already liked".
- `Story.like_count` is changed with one atomic `UPDATE ... SET like_count = like_count +/- 1` in the same transaction as the
  like row (never read-modify-write), and never goes below zero.
- Throttle scope `like`: 60 per minute per user.

## Comments (`apps/comments`)

### Statuses

| Status | Meaning | Who sees it in the story's comment list |
|---|---|---|
| `pending` | waiting for a moderator | only its own author, marked `pending` |
| `approved` | published | everyone |
| `hidden` | hidden by a moderator | nobody (moderators use the admin screen). **Its replies are hidden with it** |
| `deleted` | soft-deleted by the author or a moderator | nobody, **except** as a placeholder (`"[This comment was deleted]"`, no author) when it still has approved replies, so the thread stays readable |

Staff see the same public list as everybody; they moderate in `/admin/comments`.

### Reader endpoints

| Method and path | Rules |
|---|---|
| `GET /stories/{slug}/comments/` | Top-level comments oldest first, **20 per page** (`?page=`, the size cannot be changed), replies nested in `replies`. A logged-in reader also gets their own pending comments |
| `POST /stories/{slug}/comments/` | Login **and verified email** required (`403 "Please verify your email address first."` otherwise). Body `{body, parent?}`. Throttle `comment`: 10 per hour per user. `201` with the comment |
| `PATCH /comments/{id}/` | Owner only, only within `COMMENT_EDIT_WINDOW_MINUTES` (default 15) of creation; sets `edited_at`. Same input rules as posting. Others get `403`, after the window `403` |
| `DELETE /comments/{id}/` | Owner (soft delete, `200`, idempotent) or staff. Other readers get `403`; comments they cannot see are `404` |
| `POST /comments/{id}/report/` | Logged in. Body `{reason}` (0 to 300 characters). First report `201`, a repeat by the same user is a harmless `200`. Throttle `report`: 20 per hour per user. Only approved comments can be reported (`404` otherwise) |

Comment fields in public output: `id, parent, body, author, status, is_mine, can_edit, can_delete, edit_expires_at,
created_at, edited_at, replies`. `author` is a **display name only**. Emails and user ids never appear in public responses.
`can_edit`/`can_delete` are computed for the asking reader; the server enforces them again on every write.

### Replies

Replies are **one level deep**. A reply to a reply is attached to the top-level comment. You can only reply to an approved
comment whose thread is not hidden (`400 "You can no longer reply to that comment."`).

### Input safety (plain text only)

- The body is stored as **plain text**. Control characters are removed (tabs and line breaks stay), `\r\n` becomes `\n`,
  trailing spaces are trimmed, more than 2 blank lines in a row are collapsed to 2, and the text is trimmed.
- 1 to 2000 characters (counted before cleaning). Whitespace-only bodies are rejected.
- The React app renders comments as **text** (CSS `white-space: pre-wrap`), never as HTML. `<script>` typed by a reader is just
  characters on the screen.
- **Spam filter v1**, each rejection is `400` with a clear message:
  more than **2 links** (`http(s)://...` or `www....`); a word from **`COMMENT_BLOCKED_WORDS`** (whole words, any case);
  the **same text** by the same user within the last **hour**.
- Staff comments are never held for moderation.

### Moderation modes

Site setting `comment_moderation` (default `off`), changed in the admin or with `PATCH /admin/comment-settings/`:

| Mode | New comment status |
|---|---|
| `off` | `approved` at once |
| `approve_first` | `pending` for every non-staff comment |
| `approve_first_time` | `pending` until the user has at least one **approved** comment, then `approved` |

An edited comment keeps its status (an approved comment stays approved after an edit within the window).

### `Story.comment_count`

The number of **approved** comments, replies included, **except replies whose parent is hidden** (they are not visible, so
they are not counted). Every status change computes the change and applies it with one atomic `UPDATE`, so the counter is
correct after create, approve, hide, delete and restore. `python manage.py recount_engagement` rebuilds both counters from
the tables (`--dry-run` only reports how many stories are wrong).

## Admin moderation API (staff only, `403` for everybody else)

| Method and path | Purpose |
|---|---|
| `GET /admin/comments/` | Filters `?status=`, `?story=` (id or slug), `?reported=1`, `?q=` (body or author email), `?page=`. Each row has story `{id,title,slug}`, author `{display_name,email}` and `report_count`. Newest first |
| `PATCH /admin/comments/{id}/` | Body `{status: approved|hidden|deleted}`. Nothing else can be changed (any other key is `400`) |
| `GET /admin/comments/{id}/reports/` | The open reports: reporter, reason, time |
| `POST /admin/comments/{id}/dismiss-reports/` | Clears the reports without changing the comment's status. `{dismissed: n}` |
| `GET` / `PATCH /admin/comment-settings/` | `{comment_moderation}` |

The React screen is `/admin/comments` (tabs Pending, Approved, Hidden, Deleted, Reported; search; pagination; Approve / Hide /
Delete; a reports drawer; the moderation-mode select, which saves as soon as you change it). The sidebar badge shows the
pending count and refreshes every 60 seconds.

## Accounts

`GET /auth/providers/` returns `{google: true|false}` (is Google sign-in configured?). The React app hides "Continue with
Google" when it is `false`. Pages: `/login` (everybody), `/register`, `/forgot-password`, `/reset-password?uid=&token=`,
`/verify-email?key=`, `/account`. After login staff go to where they came from or `/admin/stories`; readers to where they came
from or `/`. The `/admin` guard sends readers to `/`. No tokens or passwords are ever stored in the browser.

## The signup prompt (anonymous visitors only)

A small dialog (Google button, sign-up and log-in links, Close). It opens when a visitor clicks Like or Comment, after about
60% of a story has been read, or on the 3rd page view of the session. Never on every load: once closed, `localStorage`
remembers it for **14 days** (a click on Like or Comment may still open it). Never on `/login`, `/register`, the password
pages, `/verify-email` or `/admin`. All storage access is wrapped in `try/catch`. It stores only a quiet-until timestamp and a
page-view counter; nothing is tracked.

## Settings and environment variables (`backend/.env`)

| Variable | Default | Meaning |
|---|---|---|
| `COMMENT_EDIT_WINDOW_MINUTES` | `15` | how long a reader may edit their own comment |
| `COMMENT_BLOCKED_WORDS` | empty | comma-separated words the spam filter rejects, e.g. `viagra,casino` |
| `THROTTLE_LIKE` | `60/min` | like / unlike, per user |
| `THROTTLE_COMMENT` | `10/hour` | posting comments, per user |
| `THROTTLE_REPORT` | `20/hour` | reporting comments, per user |

The moderation mode is **not** an environment variable: it is stored in the database (`SiteSetting`, key `comment_moderation`).

## Known limits

- Edited comments are not re-checked by a moderator.
- The spam filter is deliberately simple (links, word list, repeats). It is not a replacement for moderation.
- Comments are not deleted when a user is deleted from the Django admin without `recount_engagement` being run afterwards.
