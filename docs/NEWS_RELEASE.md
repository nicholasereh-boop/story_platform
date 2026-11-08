# News: release guide

News is an isolated module (`apps/news`, `src/features/news`) switched on by flags. With the flags off, the site behaves exactly as before.

## Edits to existing files (everything else is new)

| File | Change |
| --- | --- |
| `backend/config/settings/base.py` | `"apps.news"` in `INSTALLED_APPS`; the News settings block; four new throttle rates (`news_takedown`, `news_comment`, `news_search`, `news_counter`) |
| `backend/config/api_urls.py` | one `include("apps.news.urls")` line |
| `backend/config/celery.py` | four beat entries: publish scheduled (60 s), poll sources (15 min), rights maintenance (daily 02:20), monitor (hourly) |
| `backend/apps/audit/actions.py` | the `news.*` action names |
| `backend/.env.example`, `frontend/.env.example` | commented News switches |
| `frontend/src/features.js` | `FEATURE_NEWS` (default off, kept out of `FEATURES`), the News menu links |
| `frontend/src/extensionRoutes.jsx` | spreads the News routes (empty when the flag is off) |
| `frontend/src/utils/audit.js` | a "News" filter in the audit log |

New backend migrations, all touching only new tables: `news/0001_initial` to `news/0005_comments`. No existing table is altered. `bleach` (already in requirements) is the HTML sanitizer.

## Switches

| Switch | Default | Effect |
| --- | --- | --- |
| `NEWS_ENABLED` | `true` | `false`: every News endpoint answers 404 (staff included). The rollback switch. |
| `NEWS_PUBLIC_ENABLED` | `false` | `false`: public endpoints answer 404 while staff can still use the newsroom. |
| `NEWS_IMPORT_ENABLED` | `false` | `false`: no automatic polling of feeds (manual import still works). |
| `NEWS_COMMENTS_ENABLED` | `false` | `false`: no comments at all. |
| `NEWS_COMMENT_MODERATION` | `false` | `true`: new comments wait for staff approval. |
| `NEWS_REQUIRE_COMMERCIAL_RIGHTS` | `true` | Keep `true` while the site shows advertising. |
| `VITE_FEATURE_NEWS` (frontend, build time) | off | Only the exact value `true` shows the News pages, menu links and admin screens. |

Other settings: `NEWS_COPYRIGHT_CONTACT`, `NEWS_TAKEDOWN_NOTIFY_EMAIL`, `NEWS_PUBLIC_CACHE_SECONDS` (60), `NEWS_FEED_TIMEOUT_SECONDS` (10), `NEWS_FEED_MAX_BYTES` (2 MB), `NEWS_RIGHTS_WARNING_DAYS` (14).

## Before you start

1. Create a branch, for example `feature/news-platform`, and record the commit.
2. Back up the database and the media folder.
3. Run the existing backend and frontend test suites and keep the results (baseline).
4. Settle the decisions in the roadmap: who may comment (this build: logged-in readers only), whether editors may rewrite licensed articles (this build: only when the rights record allows modification), launch categories, who reviews rights, and the copyright contact.

## Staging, in order

1. Deploy with `NEWS_PUBLIC_ENABLED=false`, `NEWS_IMPORT_ENABLED=false`, `NEWS_COMMENTS_ENABLED=false` and the frontend built **without** `VITE_FEATURE_NEWS`. Run `python manage.py migrate`. Confirm the existing site works as before.
2. Run the checks: `pytest tests/test_news_*.py`, then the whole backend suite, then `npm test` and `npm run build`. Fix anything red before moving on.
3. Rebuild the frontend with `VITE_FEATURE_NEWS=true`. Staff see **News** in the admin menu; the public still sees nothing (the public API answers 404).
4. In the newsroom: add one source, add its rights record with the evidence, approve both, and write or import one article. Check the rights messages, preview, schedule and withdraw. Add an image and clear it.
5. Set `NEWS_PUBLIC_ENABLED=true` on staging only. Open the article as a visitor. Check the credit line, the original link, the licence line and the report form. Send a test complaint and handle it (hold, dismiss, check that the article returns to review, not to public).
6. Make sure Celery worker and beat are running, then run `python manage.py news_health`. It should print "All good."
7. Optional: `NEWS_COMMENTS_ENABLED=true` with `NEWS_COMMENT_MODERATION=true`. Post as a normal user, approve as staff.
8. Optional: `NEWS_IMPORT_ENABLED=true`, then add a feed source and use **Poll now**. Imports land in the review queue.
9. CSP: the production Nginx policy in `docs/SECURITY.md` already allows `frame-src https://www.youtube-nocookie.com`, which is what News video uses. No change is needed. If you use Report-Only first, check for violations on a News article page.

## Production

1. Take the backups again. Deploy the same build.
2. Migrate. Start with the public switch **off** and the frontend flag on, so only staff see News.
3. Enter the first sources and a handful of articles. Have the rights reviewer check each one.
4. Turn `NEWS_PUBLIC_ENABLED=true`. Watch the monitor strip at the top of the newsroom and the hourly log lines (`apps.news.monitoring`).
5. Add comments and automatic imports later, one at a time, each after a quiet week.

## What to monitor

| What | Where | Act when |
| --- | --- | --- |
| Overdue scheduled articles | health strip, `news_health` exit code 1 | the Celery worker or beat is down |
| Open complaints | Complaints tab, strip | older than 24 hours |
| Quarantined articles | strip | an editor must decide: fix the rights or withdraw |
| Rights ending | strip, hourly log | renew before the end date |
| Failing or stale feeds | strip, Import tab (ingestion health) | 3 failures in a row, or no success for 3 poll intervals |
| Comments waiting | strip, Comments tab | moderation is on |
| Audit log | Admin, Audit, filter "News" | review decisions and changes |

Cron or an uptime checker can run `python manage.py news_health`; it exits with code 1 only for error-level problems.

## Rollback

1. Fastest: `NEWS_PUBLIC_ENABLED=false`. Readers get 404 at once and nothing is deleted.
2. Whole section: `NEWS_ENABLED=false` (and rebuild the frontend without `VITE_FEATURE_NEWS`). The existing site is unchanged.
3. Stop automatic imports: `NEWS_IMPORT_ENABLED=false`.
4. Data: nothing in the old tables was changed, so there is nothing to restore there. Do not drop the News tables unless you are sure; switching off is enough. To remove the code, delete the News registrations listed above and the two folders.

## Test results

| Check | Status |
| --- | --- |
| flake8 on News code and tests | passes |
| Frontend route and test files bundle (syntax and imports) | passes |
| News text helpers and article-body sanitiser tests in a real browser | pass |
| Rights logic, RSS and Atom parser, SSRF guard against stand-ins for Django | pass |
| Django tests (`tests/test_news_*.py`) and Vitest tests | written, **run them yourself** |
| Existing backend and frontend suites | **run them yourself** |