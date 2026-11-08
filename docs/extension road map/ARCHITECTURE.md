# Proposed architecture and interfaces

This document lists proposed additions only. Confirm current conventions and naming before implementation.

## New backend apps

- `backend/apps/source_marketplace/`
- `backend/apps/video_tools/`

## Minimal integration points to inspect before editing

- `backend/config/settings/base.py`
- `backend/config/api_urls.py`
- `frontend/src/App.jsx`
- The actual existing navigation component (locate before changing).

## Marketplace endpoint proposal

- `GET /api/v1/marketplace/projects/`
- `GET /api/v1/marketplace/projects/{slug}/`
- `POST /api/v1/marketplace/projects/`
- `PATCH /api/v1/marketplace/projects/{id}/`
- `POST /api/v1/marketplace/projects/{id}/upload/`
- `POST /api/v1/marketplace/projects/{id}/github-import/`
- `POST /api/v1/marketplace/projects/{id}/checkout/`
- `POST /api/v1/marketplace/payments/verify/`
- `POST /api/v1/marketplace/payments/webhook/`
- `GET /api/v1/marketplace/purchases/`
- `GET /api/v1/marketplace/packages/{id}/download/`

## Video endpoint proposal

- `POST /api/v1/video-tools/inspect/`
- `POST /api/v1/video-tools/downloads/`
- `GET /api/v1/video-tools/downloads/{id}/`
- `GET /api/v1/video-tools/downloads/{id}/file/`
- `DELETE /api/v1/video-tools/downloads/{id}/`

## Important contracts

- Public APIs expose only published project metadata.
- Sellers can edit only their own projects unless a staff permission allows otherwise.
- Server-side package access checks are required on every download.
- Payment amount and currency come from server-side project/package data.
- Paystack callbacks must be verified and processed idempotently.
- Source packages remain private unless explicitly designated as free and authorized.
- Video providers must be individually enabled based on lawful and technically supported methods.
- User-submitted URLs must be protected against SSRF and unsafe redirects.
- Do not execute uploaded source code on the ResourceBoard application server.
- Never place Paystack secrets or GitHub tokens in frontend code.
