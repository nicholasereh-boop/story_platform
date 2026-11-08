# Marketplace and video tools: release notes

## Edits to existing files (everything else is new)

| File | Change |
| --- | --- |
| `backend/config/settings/base.py` | two entries in `INSTALLED_APPS`; one new settings block **appended at the end** (also adds the new throttle rates) |
| `backend/config/api_urls.py` | two `include(...)` lines |
| `backend/apps/audit/actions.py` | five `marketplace.*` action names |
| `backend/config/celery.py` | one beat entry (video cleanup, every 10 minutes) |
| `backend/requirements.txt` | `requests` (already installed through django-allauth; now explicit) |
| `backend/tests/test_security_settings.py` | the CSRF-exempt allow-list now also names the Paystack webhook, with the reason |
| `frontend/src/App.jsx` | imports and spreads `extensionRoutes.jsx` (public and admin) |
| `frontend/src/components/public/Header.jsx` | spreads `EXTENSION_NAV_LINKS` into the menu |
| `frontend/src/layouts/AdminLayout.jsx` | spreads `ADMIN_EXTENSION_LINKS` into the sidebar |
| `frontend/src/utils/audit.js` | a "Marketplace" filter in the audit log |
| `frontend/.env.example` | two commented feature flags |

New: `backend/apps/source_marketplace/`, `backend/apps/video_tools/` (each with its own migration `0001`, touching only new tables),
`frontend/src/{features.js, extensionRoutes.jsx, api/marketplace.js, api/videoTools.js, auth/RequireLogin.jsx, components/{marketplace,video}/, pages/{marketplace,video}/, pages/admin/MarketplaceReviewPage.jsx}`,
the tests, and `docs/{MARKETPLACE,VIDEO_TOOLS,EXTENSIONS_RELEASE_NOTES}.md`.

## Test results

| | Before (original code) | After |
| --- | --- | --- |
| Backend | 603 passed, 143 failed | **878 passed** (275 new), the **same 143** fail, none new |
| Frontend | 310 passed, 6 failed | **375 passed** (65 new), the **same 6** fail, none new |

The failing tests were already failing in the archive: most are database-access errors from the current pytest-django version,
plus a few real findings worth fixing separately (a comments endpoint with no explicit permission class, an `email_verify`
throttle scope with no rate, and a stock Django `SECRET_KEY` string in the unused `backend/config/settings.py`).

## Deploying

1. Back up the database and `media/`. 2. `pip install -r requirements.txt`. 3. `python manage.py migrate` (staging first).
4. Set `PAYSTACK_SECRET_KEY` (test key first) and the Paystack webhook URL. 5. Make sure the web server accepts ~55 MB uploads on `/api/`.
6. Create the private folders' backup job (`private_media/`). 7. Rebuild the frontend. 8. Make one test purchase and one test upload before announcing.
To roll back: set `MARKETPLACE_ENABLED=false` / `VIDEO_TOOLS_ENABLED=false` (and the two `VITE_FEATURE_*` flags); the new tables can stay.

## Before you ship: things to know

* **`backend/.env` in the archive contains real credentials.** Rotate them if that archive was ever shared, and keep `.env` out of Git and out of ZIPs.
* The Paystack integration is tested against a faithful fake, not against Paystack. Run a real **test-mode** purchase before going live.
* Seller payouts, refunds and malware scanning are not built (see `MARKETPLACE.md`, "Known limits").
