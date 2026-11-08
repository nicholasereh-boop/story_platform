# ResourceBoard Feature Expansion Roadmap

This package documents a safe, additive plan for adding two features to the existing ResourceBoard project without replacing its current functionality.

## Goals

1. **Source Code Marketplace**
   - Publish website/software source code from an authorized GitHub repository or local ZIP upload.
   - Add project title, description/notes, screenshots, technology tags, and an embedded YouTube preview.
   - Offer frontend packages for free or optionally paid access.
   - Sell backend packages through Paystack with server-side payment verification and protected downloads.

2. **Video Tools**
   - Accept video URLs from YouTube, Facebook, Instagram, TikTok, and X.
   - Identify the provider and check what download methods are permitted and supported.
   - Offer downloads only where the user has authorization and a supported method exists.
   - Never promise watermark-free downloads for every platform or bypass DRM, access controls, private-account restrictions, or technical protections.

## Non-negotiable preservation rule

Treat the uploaded project ZIP and its current Git state as the baseline. Do not rebuild the project, replace existing pages, delete existing routes, rewrite existing models, or reset the database. Prefer new isolated modules. Make only the smallest additive registration changes required to load the new apps and pages.

A completely zero-touch integration is generally not possible because new Django apps and React pages must be registered. The goal is to keep existing business logic and behavior untouched.

## Project observations

The inspected project structure indicates:
- Django REST Framework backend.
- React 18/Vite frontend.
- Existing story editor at `frontend/src/pages/admin/StoryEditPage.jsx`.
- Existing story app under `backend/apps/stories/`.
- Existing media code under `backend/apps/media/` and `frontend/src/components/media/`.
- Account/security code under `backend/apps/accounts/` and `backend/apps/core/`.
- Backend app/API registration in `backend/config/settings/base.py` and `backend/config/api_urls.py`.
- Frontend route declarations in `frontend/src/App.jsx`.

Verify these paths against the working copy before making changes. This roadmap is a plan, not a claim that the features have been implemented.

---

# Phase 1 — Protect the existing project

1. Keep the original ZIP unchanged and extract a separate working copy.
2. Initialize or inspect Git and record the current commit and working-tree status.
3. Create a dedicated feature branch.
4. Install dependencies using the project's existing lockfiles and documented instructions.
5. Run existing backend tests and frontend checks before changes.
6. Record current URL routes, settings, migrations, and critical user workflows.
7. Back up the database and uploaded media before any production migration.

**Exit criteria:** baseline test results and backups are recorded; the original project remains untouched.

# Phase 2 — Source Code Marketplace

## User-facing workflow

- Browse published projects and open a project detail page.
- Submit a project with title, slug, description, notes, technology tags, screenshots, and YouTube video URL.
- Import source from a public GitHub repository or an explicitly authorized private repository.
- Alternatively upload a source ZIP from the user's computer.
- Configure frontend access (free or paid if enabled) and backend price.
- Save drafts, submit for review, and publish only after required checks.
- Buyers can view their purchases and download packages they are entitled to access.

## Suggested new Django app

```text
backend/apps/source_marketplace/
    __init__.py
    apps.py
    admin.py
    models.py
    serializers.py
    views.py
    urls.py
    permissions.py
    migrations/
    services/
        github.py
        uploads.py
        payments.py
```

Keep marketplace models separate from the existing `Story` model.

### Suggested models

- `SourceProject`: title, slug, description, creator, status, technologies, pricing settings.
- `SourcePackage`: frontend/backend type, storage reference, version, access rules.
- `SourcePurchase`: buyer, project/package, amount, currency, Paystack reference, verified status.
- `SourceProjectMedia`: screenshots and associated media.
- `SourceDownload`: authorized download audit records.

### Suggested frontend files

```text
frontend/src/pages/marketplace/
    MarketplacePage.jsx
    ProjectDetailPage.jsx
    PublishProjectPage.jsx
    EditProjectPage.jsx
    MyPurchasesPage.jsx

frontend/src/components/marketplace/
    ProjectCard.jsx
    SourceUploadForm.jsx
    GitHubImportForm.jsx
    ProjectGallery.jsx
    VideoPreview.jsx
    PurchaseButton.jsx
```

Reuse existing media components only where their interfaces fit. Build a marketplace-specific form and state management so marketplace changes cannot overwrite stories.

### Suggested API endpoints

These are proposals; verify URL conventions before implementation.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/marketplace/projects/` | Browse published projects |
| GET | `/api/v1/marketplace/projects/{slug}/` | View project details |
| POST | `/api/v1/marketplace/projects/` | Create a project |
| PATCH | `/api/v1/marketplace/projects/{id}/` | Update an authorized project |
| POST | `/api/v1/marketplace/projects/{id}/upload/` | Upload source package |
| POST | `/api/v1/marketplace/projects/{id}/github-import/` | Import authorized repository |
| POST | `/api/v1/marketplace/projects/{id}/checkout/` | Initiate purchase |
| POST | `/api/v1/marketplace/payments/verify/` | Verify payment |
| POST | `/api/v1/marketplace/payments/webhook/` | Process Paystack webhook |
| GET | `/api/v1/marketplace/purchases/` | List buyer purchases |
| GET | `/api/v1/marketplace/packages/{id}/download/` | Authorize a download |

## Paystack payment requirements

1. The server obtains price and currency from the database, never from a trusted client value.
2. Create a unique purchase and payment reference.
3. Initiate Paystack checkout server-side.
4. Verify transaction status, reference, amount and currency with Paystack server-side.
5. Validate webhook signatures according to current Paystack documentation.
6. Make processing idempotent so retries cannot duplicate purchases.
7. Grant package access only after verified success.
8. Use protected, expiring download links or an authorized download endpoint.
9. Keep secret keys in environment/server configuration, never in frontend code.
10. Test failed, pending, duplicate and forged callbacks.

Decide supported currency (for example NGN) based on the merchant account and Paystack configuration.

## Upload and GitHub security

- Enforce archive size limits, allowed file types and safe extraction.
- Defend against ZIP path traversal, archive bombs and malicious files.
- Never execute uploaded source code on the application server.
- Store packages outside the public static directory/private object storage.
- Use scoped GitHub authorization and never expose tokens to the browser.
- Check ownership/distribution rights before publishing.
- Avoid leaking `.env` files, credentials, private keys, or repository secrets.
- Add seller permissions and optional staff moderation; do not grant staff privileges to ordinary sellers.

**Marketplace exit criteria:** free package flow works; paid access is locked until server-side verification; users cannot edit another seller's project or download packages they have not purchased.

# Phase 3 — Video Tools

## User-facing workflow

1. User pastes a video URL.
2. Backend validates the URL and identifies the provider.
3. The system checks provider capabilities and authorization.
4. If a supported, permitted method exists, show available formats and request a download.
5. Show job progress and a clear completion/error message.
6. Expire and clean up temporary artifacts.

## Suggested new Django app

```text
backend/apps/video_tools/
    __init__.py
    apps.py
    admin.py
    models.py
    serializers.py
    views.py
    urls.py
    permissions.py
    tasks.py
    migrations/
    services/
        url_validation.py
        providers.py
        download_jobs.py
        storage.py
```

### Suggested models

- `DownloadJob`: requester, submitted URL, provider, processing status, timestamps.
- `DownloadArtifact`: stored output, permitted format, expiry, ownership.
- `ProviderCapability`: optional provider support/configuration records.

### Suggested frontend files

```text
frontend/src/pages/video-tools/
    VideoDownloaderPage.jsx

frontend/src/components/video-tools/
    VideoUrlForm.jsx
    ProviderBadge.jsx
    DownloadOptions.jsx
    DownloadProgress.jsx
```

### Suggested API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/video-tools/inspect/` | Validate URL and provider support |
| POST | `/api/v1/video-tools/downloads/` | Request authorized download |
| GET | `/api/v1/video-tools/downloads/{id}/` | Check job status |
| GET | `/api/v1/video-tools/downloads/{id}/file/` | Download authorized output |
| DELETE | `/api/v1/video-tools/downloads/{id}/` | Cancel/remove eligible job |

## Provider and watermark limitations

Support should be enabled per provider only after its current terms, API capabilities, and authorization requirements have been reviewed. YouTube, Facebook, Instagram, TikTok, and X do not all provide a universal, unrestricted download interface. A URL does not guarantee a downloadable file or a watermark-free copy.

Permitted sources can include the user's own original video, a creator-authorized file, or a provider's official download method. Do not bypass DRM, private-account restrictions, access controls, or technical protections, and do not remove attribution from content without authorization. Clearly explain when a platform does not support the requested action.

## Video service security

- Allowlist supported hostnames and parse URLs with a robust URL parser.
- Defend against SSRF, private/loopback/link-local IPs, unsafe redirects, DNS rebinding and arbitrary schemes.
- Never accept arbitrary local file paths.
- Enforce file-size, duration, timeout, concurrency and per-user/IP limits.
- Process larger jobs asynchronously if supported by the current stack.
- Keep temporary outputs private and expire them automatically.
- Log failures without storing unnecessary sensitive URLs or credentials.

**Video tools exit criteria:** URL inspection is safe; each enabled provider has a documented permitted download method; unsupported cases fail clearly; rate limits and cleanup are active.

# Phase 4 — Minimal integration

The following files may need small additive edits because they register apps or routes:

- `backend/config/settings/base.py`: register the two new Django apps using existing conventions.
- `backend/config/api_urls.py`: include the new API URL modules without removing or reordering existing routes unnecessarily.
- `frontend/src/App.jsx`: add new route declarations while preserving all existing route definitions and guards.
- Navigation/layout file(s): add links only after identifying the actual current navigation component.

Do not blindly overwrite these files. Inspect them first, then make a minimal patch. Do not change existing settings unless required by a verified dependency.

# Phase 5 — Regression testing

Run the project's actual commands from its existing documentation and package files. Do not assume command names without checking `package.json`, Django settings, or test configuration.

### Existing platform regression tests

- Existing public pages and URLs still resolve.
- Login, logout, sessions, CSRF, permissions and account workflows still work.
- Story create/edit/publish and revision history still work.
- Existing image uploads and media library still work.
- Comments, search, analytics, admin and other established workflows still work.
- Existing migrations apply cleanly and preserve existing records.

### Marketplace tests

- Valid and invalid ZIP uploads.
- Malicious ZIP path traversal and archive size limits.
- GitHub public/private access behavior and token protection.
- Seller ownership and staff permissions.
- Free downloads.
- Paid downloads blocked before payment verification.
- Paystack success, failure, amount mismatch, invalid signature and duplicate webhook.
- Expiring download links and purchase history.

### Video tests

- Valid, malformed and unsupported URLs.
- Unsafe hosts, redirects and private-network targets.
- Unsupported providers and unauthorized content.
- Rate limits, file-size limits, timeouts and cleanup.
- Only authorized users can access generated artifacts.

### Database and migration safety

- Back up the database and media.
- Add new tables through new migrations.
- Never use a database reset to install the features.
- Test rollback procedures in a staging copy.
- Review generated migration files before applying them to production.

# Phase 6 — Gradual release

1. Deploy to staging first.
2. Run migrations and the full regression suite.
3. Keep new navigation or functionality behind feature flags if practical.
4. Test marketplace purchases with Paystack test mode.
5. Enable only verified video provider capabilities.
6. Monitor errors, storage usage, payment reconciliation and download abuse.
7. Release to a small group before enabling for all users.
8. Keep a tested rollback plan and a fresh backup.

# Acceptance checklist

## Existing platform
- [ ] All existing pages and URLs work.
- [ ] Existing stories, media and accounts are preserved.
- [ ] Existing automated tests continue to pass.

## Marketplace
- [ ] GitHub import and local ZIP upload work.
- [ ] Notes, screenshots and video previews save correctly.
- [ ] Frontend access follows the project's pricing settings.
- [ ] Paystack is verified server-side.
- [ ] Unpaid buyers cannot download paid backend packages.
- [ ] Users cannot edit another seller's project.

## Video tools
- [ ] Five requested platform URL patterns are validated.
- [ ] Unsupported providers receive clear messages.
- [ ] Authorized downloads work for enabled providers.
- [ ] SSRF and excessive downloads are controlled.

## Release
- [ ] Migrations preserve current data.
- [ ] Secrets are not exposed in frontend code.
- [ ] Backup and rollback procedures are tested.

# Recommended implementation order

1. Protect and test the existing baseline.
2. Build the marketplace's free publishing and download workflow.
3. Add Paystack and protected paid downloads.
4. Add the video URL inspector and provider framework.
5. Enable provider integrations individually after review.
6. Run regression tests and deploy gradually.

**Final principle:** ResourceBoard remains the original application. These are isolated additions connected through the smallest required registration changes—not a rebuild or replacement of existing functionality.
