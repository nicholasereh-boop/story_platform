# Video tools

A page (`/video-tools`) where a member pastes a link from **YouTube, Facebook, Instagram, TikTok or X**. The site checks the link,
explains what is possible, and downloads a file **only where a reviewed, permitted method exists for that platform**.

Code: `backend/apps/video_tools/` · `frontend/src/pages/video/` · `frontend/src/components/video/`
Tests: `backend/tests/test_video_*.py` · `frontend/src/__tests__/videoToolsPage.test.jsx`

## Where it stands: every platform is "link check only"

None of the five platforms offers a public way to download arbitrary videos, and their terms generally forbid it (YouTube's, for
example, only allows downloads through features YouTube itself provides). The roadmap says not to bypass platform restrictions, so
this feature ships the whole safe pipeline **with the download gate closed**. Without a reviewed adapter a person can check a link
and is told, in plain words, what the platform itself allows (for example, downloading your own uploads from its own tools).
No scraping, no watermark removal, no access-control or DRM circumvention exists anywhere in the code.

A platform becomes downloadable only when **all three** are true:

1. a reviewed adapter class is configured: `VIDEO_TOOLS_ADAPTERS=youtube=my_package.my_module.MyAdapter` (comma-separated for several);
2. the adapter reports itself configured (`is_configured()`: credentials present, quota available);
3. staff switch the platform on in the Django admin (**Video tools → Provider capabilities**) after reviewing its current terms,
   recording the permitted method and the review date.

Switching a platform off in the admin takes effect immediately, even for jobs already waiting.

### Writing an adapter

Subclass `apps.video_tools.services.providers.DownloadAdapter`: set `provider`, `method` (plain-language description of the permitted
method), `formats`, and implement `fetch(job, format_key, workdir)` returning `FetchResult(path, filename, content_type)` for a file
written inside `workdir`. Raise `AdapterError(message, code)` for failures a person should read. Any network access must go through
`services/net.py:download_to_file` (allow-listed hosts, public addresses only, checked redirects, size and time limits).
Realistic starting points are official APIs used with the **owner's own authorisation** (for example the Meta Graph API for an
Instagram/Facebook account the person manages, or the X API for their own posts). Review each platform's current terms first.

## Link validation (`services/url_validation.py`)

The pasted link is **never fetched**. It is parsed, must be `https`, on an exact-match host list, and is reduced to a provider and a
content id; everything afterwards uses a canonical link **rebuilt from the id** (so tracking parameters never travel on or get stored).
Refused: other schemes, credentials in the address, other ports, IP addresses, look-alike hosts (`youtube.com.evil.example`,
`youtube.com@evil.example`), non-ASCII hosts, encoded or traversal paths, control characters, links over 2048 characters, and
playlist/channel/profile links. Short links (`vm.tiktok.com`, `fb.watch`, …) are recognised but not followed; the person is asked
for the full address.

## Jobs, limits and cleanup

`POST /downloads/` (login + a ticked "I own this or have permission" confirmation, stored with a timestamp) creates a job with an
unguessable UUID, runs it in Celery (or inline with `VIDEO_TOOLS_RUN_INLINE=true`, development only), and the page polls it.
Files live in private storage (`VIDEO_TOOLS_PRIVATE_ROOT`, no URL), only the requester can see or fetch them, and they are deleted
after `VIDEO_TOOLS_RETENTION_HOURS` (24). A Celery beat entry runs the cleanup every 10 minutes; without Celery run
`python manage.py cleanup_video_downloads` from cron. Cleanup also fails stuck jobs and forgets job records after 30 days.

| Setting | Default |
| --- | --- |
| `VIDEO_TOOLS_ENABLED` | `true` (`false` = every endpoint answers 404; frontend: `VITE_FEATURE_VIDEO_TOOLS=false`) |
| `VIDEO_TOOLS_MAX_FILE_BYTES` | 200 MB |
| `VIDEO_TOOLS_MAX_ACTIVE_JOBS` / `_MAX_JOBS_PER_DAY` | 2 / 20 per person |
| `VIDEO_TOOLS_RETENTION_HOURS` / `_JOB_RETENTION_DAYS` | 24 h / 30 days |
| `THROTTLE_VIDEO_INSPECT` / `_DOWNLOAD` / `_POLL` | 60/min per IP · 10/hour per user · 180/min per user |

Logs carry the job id and provider only, never the link or an adapter's internal error text.
