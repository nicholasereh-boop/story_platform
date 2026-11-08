# Implementation checklist

## Before coding
- [x] Preserve the original ZIP. _(original archive left untouched; work was done in a separate extracted copy)_
- [x] Extract a separate working copy.
- [ ] Inspect Git status and create a feature branch. _(the archive has no usable Git history; create the branch when you copy this into your repository)_
- [x] Read existing frontend package scripts and backend test configuration.
- [x] Run baseline tests and save results. _(backend 603 pass / 143 fail, frontend 310 pass / 6 fail, all failures pre-existing; see docs/EXTENSIONS_RELEASE_NOTES.md)_
- [x] Record existing routes, settings and migrations.
- [ ] Back up database and uploaded media.

## Marketplace
- [x] Add `source_marketplace` app.
- [x] Add isolated marketplace models and migrations.
- [x] Add serializers, views, permissions and URLs.
- [x] Add private source package storage and safe upload validation.
- [x] Add authorized GitHub import. _(public repos need no token; private repos use a one-time read-only token, see docs/MARKETPLACE.md)_
- [x] Add React listing, detail, publish, edit and purchases pages.
- [x] Add screenshots and safe YouTube embeds.
- [x] Add free frontend download authorization.
- [x] Add Paystack checkout, server verification and idempotent webhook processing. _(implemented and tested against a fake Paystack; still needs a real test-mode run (see Before release))_
- [x] Add paid backend package authorization.
- [x] Add tests for ownership, uploads, payments and downloads.

## Video tools
- [x] Add `video_tools` app.
- [x] Add job/artifact models and migrations.
- [x] Add URL validation and provider capability registry.
- [x] Add SSRF defenses, limits, timeouts and cleanup.
- [x] Add React URL submission and status UI.
- [ ] Enable only reviewed, permitted provider integrations. _(the gate is built and ships CLOSED: every provider is link-check only until a reviewed adapter is configured and staff switch it on; see docs/VIDEO_TOOLS.md)_
- [x] Add tests for invalid URLs, unsupported providers and artifact access.

## Minimal integration
- [x] Add app registrations to Django settings.
- [x] Include new API URL modules.
- [x] Add React routes without removing existing routes.
- [x] Add navigation links without redesigning existing navigation.
- [x] Review the diff to confirm existing business logic is untouched. _(edits to existing files are listed in docs/EXTENSIONS_RELEASE_NOTES.md)_

## Before release
- [x] Run all existing regression tests. _(no new failures versus the baseline; the pre-existing failures remain (see release notes))_
- [x] Run all new feature tests.
- [ ] Apply migrations to staging first.
- [ ] Test Paystack in test mode.
- [ ] Verify file storage and secret configuration.
- [ ] Test backup and rollback.
- [ ] Release gradually and monitor.
