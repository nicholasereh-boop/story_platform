# Analytics (Phase 9): anonymous visitors, page views, reports

First-party and privacy-minimal. No cookies and no third-party scripts. By default there is no consent banner; Phase 10 adds an optional one (see "Consent mode"). Everything below is under `/api/v1/`.

## What is collected (and why)

| Collected | How | Why |
|---|---|---|
| A random visitor id (UUID) | kept by the browser in `localStorage`; the server stores only an **HMAC-SHA256 hash** of it | count unique visitors per day, week and month |
| A random session id | `sessionStorage` (per tab); stored hashed | tell visits apart |
| The public path (`/stories/my-story`) | sent without the query string | page views and top stories |
| Referrer **domain** | `news.example`, never the full URL; our own site is dropped | "where visitors come from" |
| Device category | `desktop`, `mobile`, `tablet` or `other`, derived from the user agent | the device split |

## What is never collected

- IP addresses and full user-agent strings (they are read to decide a category, then discarded).
- Names, emails or account data. Page views are not linked to accounts.
- Visits from **bots** (dropped, not stored), **logged-in staff**, the **admin**, `/login`, `/register`, password and verify pages, `/account`.
- Anything when the browser sends **Do Not Track** or **Global Privacy Control**, or the visitor switched analytics off.

The hash secret is `ANALYTICS_HASH_SECRET`; when it is empty the Django `SECRET_KEY` is used. The hash includes a purpose label, so a visitor hash and a session hash of the same id differ. Ids are not reversible and cannot be matched to other sites. Changing the secret makes every browser a new visitor from then on.

## Opting out

- Footer toggle "Analytics: on / off" and the `/privacy` page (stores `sb.analytics-off` in `localStorage`).
- Browser Do Not Track / Global Privacy Control: nothing is sent, and the footer says so.
- Site-wide: `ANALYTICS_ENABLED=false` makes the collect endpoint ignore every event.

## Consent mode (Phase 10)

`PRIVACY_CONSENT_MODE` (backend setting, read by the frontend from `GET /api/v1/public-config/`) decides how visitors are asked:

| Mode | Behaviour | Banner |
|---|---|---|
| `notice` (default) | Counting is on; the footer toggle and `/privacy` explain and let people switch it off. | none |
| `opt_in` | Counting is OFF until the visitor presses Accept. | yes |
| `opt_out` | Counting is on until the visitor presses Reject. | yes |

The banner has equally prominent Accept and Reject buttons and a link to the policy, is keyboard accessible, never traps
focus, never shows on `/admin` or the login and account pages, and can be reopened from the footer link "Privacy settings".
The choice is kept for 6 months in `localStorage` under `sb.consent` and is never sent to or stored on the server.

The tracker sends nothing unless ALL of these allow it: the site master switch, Do Not Track / Global Privacy Control, the
footer toggle, and the consent mode. In `opt_in` mode the browser also adds `"consent": true` to each event, and the collect
endpoint ignores events without it, so a stale or modified client cannot count a visitor who has not agreed. In the other
modes the flag is not required.

This is a technical implementation of the choices, not legal advice. Whether `notice` is enough for your country or your
visitors is a question for you and a qualified adviser. `docs/SECURITY.md` lists what needs that review.

## Collect endpoint

`POST /analytics/collect/` with `{path, visitor_id, session_id, referrer}`. Anonymous, no CSRF, throttle scope `analytics` (120/min per IP).
It answers **204 with an empty body** whether the event was counted or ignored, so it reveals nothing. Ignored: malformed ids, paths that are
not public-site paths, non-public stories (draft, scheduled, archived, unknown), bots, staff, opted-out requests, repeats.

**Anti-inflation:** the same visitor opening the same path again within `ANALYTICS_DEDUPE_MINUTES` (30) is not stored (an atomic cache `add`; if the cache is
down, one database query is used instead). Refreshing 20 times counts once. `Story.view_count` goes up (atomic `F()` update) only when a story view is counted;
it stays hidden from the public API.

## Tables

`Visitor`, `PageViewEvent` (raw, deleted after the retention period), `DailyAnalytics`, `PeriodAnalytics` (week or month, **exact** distinct visitors),
`DailyStoryStats` (feeds Top stories), `AnalyticsState` (the `purged_before` marker).

## Time rules

All days are **UTC**. A week starts on **Monday**. A month is a calendar month. Weekly and monthly visitors are the number of distinct visitors in the whole period, not a sum of daily numbers.

## Aggregation

```bash
python manage.py aggregate_analytics                              # yesterday and today
python manage.py aggregate_analytics --from 2026-01-01 --to 2026-03-31   # back-fill a range
```
Idempotent: it upserts, so running it twice gives the same numbers. It rebuilds the days in the range and every week and month that overlaps it.
`registered_users`, `likes` and `comments` (approved only) are counted from the user, like and comment tables by their `created_at` date.
Days older than the purge marker are skipped, because their raw events are gone and the stored numbers must be kept.

**Without Celery** the dashboard still works: when a range includes today, the admin endpoints refresh today (older than 5 minutes) and yesterday first.
Older days need the command or Celery.

**With Celery** (`celery -A config worker -l info` and `celery -A config beat -l info`, Redis running): `aggregate_recent` every 15 minutes and at 00:10 UTC
(closes yesterday, last week, last month), `purge_old` at 03:30 UTC. See `config/celery.py`.

## Retention and purge

```bash
python manage.py purge_analytics --dry-run
python manage.py purge_analytics
```
Raw events older than `ANALYTICS_RETENTION_DAYS` (default 90, **never less than 35**, so a month in progress is always complete in raw data) are deleted, and visitors not seen for
about 13 months. The affected days, weeks and months are **aggregated first**; every aggregate is kept. After a purge, unique-visitor numbers
for ranges that start before the purge date are estimates (sum of daily uniques) and the API says so with `unique_visitors_exact: false`.

## Admin API (staff only; everybody else gets 403)

All accept `?days=` (1 to 366, default 30) or `?from=YYYY-MM-DD&to=YYYY-MM-DD`; the range is capped at 366 days and never passes today. Bad parameters are `400` in the usual envelope.

| Path | Result |
|---|---|
| `GET /admin/analytics/overview/` | `current` and `previous` (same length, just before) totals for `unique_visitors, page_views, story_views, registered_users, likes, comments`, plus `change` in percent (`null` when there is no previous data) |
| `GET /admin/analytics/daily/?granularity=day\|week\|month` | gap-free `points`; week and month points start on the period's first day |
| `GET /admin/analytics/stories/?limit=10` | top stories by views (max 50): `id, title, slug, views, unique_visitors, likes, comments`; only stories that have been published |
| `GET /admin/analytics/traffic/` | `referrers` (top 10 domains, "Direct" for none) and the `devices` split |

No endpoint returns visitor hashes, session hashes, IP addresses or user data.

## Frontend

- Tracker: `src/analytics/tracker.js` and `useTracker.js` (used by `PublicLayout`): one event per route change, `sendBeacon` or `fetch` with `keepalive`, never retried, never blocks rendering.
- Footer toggle and `/privacy`: `AnalyticsToggle`, `PrivacyPage`.
- Dashboard: `/admin/analytics` with range (7/30/90 days), grouping (daily/weekly/monthly), six tiles with change versus the previous period, two accessible inline-SVG line charts
  (line style and marker shape differ per series; "Show as table" fallback), top stories, referrers and devices. No chart library.

## Settings and environment variables (`backend/.env`)

| Variable | Default | Meaning |
|---|---|---|
| `ANALYTICS_ENABLED` | `true` | master switch |
| `ANALYTICS_DEDUPE_MINUTES` | `30` | repeat views of one page by one visitor count once |
| `ANALYTICS_RETENTION_DAYS` | `90` | raw event retention (minimum 35 is enforced) |
| `ANALYTICS_HASH_SECRET` | empty | secret for the id hashes (empty = Django `SECRET_KEY`) |
| `PRIVACY_CONSENT_MODE` | `notice` | `notice`, `opt_in` or `opt_out` (see "Consent mode") |
| `THROTTLE_ANALYTICS` | `120/min` | collect endpoint, per IP |

## Known limits

- Unique visitors are per browser, not per person: another browser, private mode or cleared storage is a new visitor.
- The bot filter is a simple user-agent list, not a guarantee.
- Today's numbers can be up to 5 minutes old without Celery.
- If the site is behind a proxy set `NUM_PROXIES`, otherwise the throttle sees one IP for everybody.
