# Security and privacy (Phase 10)

This is the production security baseline for the platform. It describes what the code does, why, how to turn the
optional parts on, and what is still the site owner's job. Nothing here replaces a legal review (see the last section).

Contents: threat model, audit findings, controls table, headers and the Nginx CSP, cookies and storage, rate limits,
endpoint inventory, two-step verification (MFA), audit events, retention, pre-deployment checklist, known limits.

---

## 1. Threat model in one page

| Who / what | What they might try | Main defences |
|---|---|---|
| Anonymous visitor | Guess accounts, brute-force logins, spam comments, scrape | Same answer for every auth failure, lockout (5 failures / 15 min per email + IP), throttles on every anonymous write, spam filter |
| Reader with an account | Read admin data, change someone else's data, escalate to staff | `permission_classes` on every view, object-level ownership checks, no API can set `is_superuser`, staff can only be granted by a superuser |
| Malicious author or stolen staff session | Plant script in a story, upload a booby-trapped file | Stories are validated JSON (never HTML), URL protocol allowlist, uploads are decoded and re-encoded, two-step verification enforced in the permission layer |
| Attacker on another website | CSRF, clickjacking, cross-site data theft | CSRF token on every unsafe request, `SameSite=Lax`, exact CORS allowlist, `X-Frame-Options: DENY`, `frame-ancestors 'none'` |
| Curious or compromised administrator | Act without a trace, read secrets | Append-only audit log, secrets never returned by any endpoint, IPs stored only as keyed hashes |
| Someone with the database or a log file | Read passwords, tokens, personal data | Django password hashing, MFA secrets encrypted at rest, recovery codes hashed, analytics ids hashed, log redaction |

Out of scope for this phase (see section 12): network and server hardening, backups, monitoring (Phase 12), the full
test pass and load testing (Phases 11 and 13).

---

## 2. Audit findings

The audit was done first, against the Phase 9 code. "Fixed" means changed in Phase 10, "Fine" means it already met the
rule (a test now pins it down), "Left" means a deliberate decision.

| Area | Finding | Status |
|---|---|---|
| Account enumeration, register | The sign-up form answered "an account with this email already exists" (400) for taken addresses. | Fixed: always 202 "check your email"; an existing owner gets a "someone tried to sign up" notice instead. Nobody is logged in by registering. |
| Account enumeration, login | One message for unknown email, wrong password and inactive account; unknown emails burn the same hashing time. | Fine (test added) |
| Account enumeration, reset and resend | Reset request answers the same for known and unknown addresses; resend needs a login. | Fine (test added) |
| Google linking | Google sign-in joins an existing account by e-mail through django-allauth and our adapter; no endpoint tells a visitor whether an address has an account. | Fine (reviewed, not changed) |
| `permission_classes` | Every view declared them, but nothing enforced it. | Fixed: an inventory test walks the URL configuration and fails if a view relies on a default. |
| `csrf_exempt` / `authentication_classes = []` | Only the analytics collect endpoint (anonymous, writes anonymous data). | Fine. The new CSP report receiver is the second and last exemption; a test fails if a third appears. |
| `dangerouslySetInnerHTML` / `innerHTML` | None in the frontend since Phase 6. | Fine. A Vitest now scans `src/` and fails on any use. |
| JSON-LD in the page head | Built with `JSON.stringify` and set with `textContent`. | Fine. `safeJsonLd` also escapes `<`, `>`, `&`, U+2028 and U+2029 (tested). |
| Uploads | Pillow decode, size limit, uuid names, EXIF stripped for still images. Animated files kept byte-for-byte (so hidden bytes could survive); no pixel or frame cap beyond Pillow's default; no per-user quota. | Fixed: every file is re-encoded from pixels (animations frame by frame), frame and pixel caps, upload quota per user per hour, sanitised display name, alt text and caption are plain text with limits. |
| Logging | Default Django logging: a failing request or form could write a password, token, cookie or email address to the console. | Fixed: a redacting filter on every handler. |
| 500 responses | In production Django answered with its generic HTML page; API clients got no envelope. | Fixed: standard envelope, generic message and a short error id (the traceback goes to the redacted log). |
| Token lifetimes | Django's default reset link lifetime is 3 days. | Fixed: password reset 1 hour, e-mail verification 3 days. Reuse and expiry are tested. |
| Sessions | Session id rotated by Django's `login()`; no idle timeout, no device list, no "sign out everywhere". | Fixed: staff idle timeout, session list (no IP, no browser text), revoke-all, password change signs out other devices. |
| Staff authentication | Password only. | Added: optional TOTP, enforced in the permission layer; `STAFF_MFA_REQUIRED` makes it mandatory. |
| Audit trail | The `audit` app was an empty skeleton. | Added: append-only audit log, admin viewer, retention command and monthly Celery job. |
| User management | Only a command (`create_admin`). | Added: admin users API and screen with safeguards (no self-demotion, last-superuser protection). |
| Privacy rights | None. | Added: download my data, delete (anonymise) my account. |
| Django admin | At `/admin/`, which clashes in name with the React admin and is the first thing scanners try. | Fixed: `DJANGO_ADMIN_URL` (default `django-admin/`) and `DJANGO_ADMIN_ENABLED`. |
| Secrets in the repository | `.env.example` only. | Fine. Tests now scan the repository and the frontend for secrets and secret variable names. |
| Left on purpose | Comment text and story bodies are not scanned for profanity or malware links beyond the spam filter. Rate limits are per IP and per user, not per device fingerprint. No CAPTCHA (it would add a third-party service). | Left |

---

## 3. Controls mapped to the roadmap checklist

| Roadmap item (Phase 10) | What implements it | Where it is tested |
|---|---|---|
| Secure cookies / tokens | Session cookie `HttpOnly`, `Secure` in production, `SameSite=Lax`; CSRF cookie readable by JavaScript only because React must send it; no token, password or secret ever in web storage; reset links 1 h, verification links 3 days; session id rotates on login, logout and password change | `test_security_settings` (cookie flags, token lifetimes, expiry and reuse), `test_privacy_rights` (rotation), `securityScan.test.js` (no tokens in storage) |
| CORS restrictions | Exact allowlist (`FRONTEND_URL`), never `*`, hostile origins get no CORS headers | `test_security_settings` |
| CSRF where relevant | Enforced on every unsafe request except two anonymous collectors | `test_security_settings` (exempt inventory) |
| Upload hardening | `apps/media/images.py`: decode, allowlist, re-encode, caps, random names, quota, sandboxed serving | `test_content_hardening`, `test_media` |
| XSS / content sanitisation | Validated JSON content, URL protocol allowlist, plain-text fields, React escaping, scan test | `test_content_hardening`, `test_xss_corpus`, `securityScan.test.js` |
| Rate limits | Table in section 6 | `test_security_settings`, per-feature tests |
| Audit logs | `apps/audit`, section 9 | `test_audit` |
| Privacy policy / cookie controls | `/privacy` page built from settings, consent banner and public config | `PrivacyPage.test.jsx`, `ConsentBanner.test.jsx`, `privacyTables.test.js`, `test_security_settings` (cookie table) |
| Admin security (blueprint) | MFA, audit log, admin URL, staff idle timeout, user manager | `test_mfa`, `test_audit`, `test_users_admin` |
| Anonymous visitors (blueprint) | Hashed ids, no raw IP, retention, notice, opt-out, optional consent | Phase 9 tests plus `test_privacy_rights` (consent in collect) |

---

## 4. Production settings guard

`config/settings/production.py` refuses to start (`ImproperlyConfigured`, every problem listed at once) unless:

- `DJANGO_SECRET_KEY` is at least 50 characters, not repetitive and not a placeholder from `.env.example`
- `DEBUG` is off
- `DJANGO_ALLOWED_HOSTS` names real domains (no `*`)
- `FRONTEND_URL`, CORS origins and CSRF trusted origins all start with `https://`
- PostgreSQL is configured

`python manage.py check --deploy` must report no warnings under the production settings (a test runs it).
Generate a key with `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

---

## 5. Headers and Content-Security-Policy

Every response from Django carries:

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()` |
| `Cross-Origin-Opener-Policy` | `same-origin-allow-popups` (`same-origin` would break the Google login popup) |
| `X-Frame-Options` | `DENY` |
| `Strict-Transport-Security` | production only: one year, include subdomains, preload |
| `Content-Security-Policy` | by path, see below |

Content-Security-Policy for what Django serves:

| Path | Policy |
|---|---|
| API and everything else | `default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'` |
| Django admin (`DJANGO_ADMIN_URL`) | own origin only, inline styles allowed, no framing |
| Uploaded media (`/media/`, development only; Nginx or the CDN serves it in production) | `default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox; frame-ancestors 'none'` |
| `/api/v1/docs/` (Swagger) | allows `cdn.jsdelivr.net` for its scripts and styles |

Every policy ends with `report-uri /api/v1/csp-report/`. Set `CSP_REPORT_ONLY=true` to send
`Content-Security-Policy-Report-Only` instead while you roll out a stricter policy. The receiver logs a trimmed report
(blocked directive, blocked host, document path, no query strings, no IP), is rate limited and never fails on bad input.

### CSP for the React app (paste into Nginx, Phase 12)

Django never sees the static React files, so the policy for the website itself belongs in the web server. Replace
`MEDIA_HOST` with the host that serves your images (your CDN, or your own domain if Nginx serves `/media/`).

```nginx
# inside the server { } block that serves the built frontend (frontend/dist)
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https://MEDIA_HOST; font-src 'self'; frame-src https://www.youtube-nocookie.com; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self' https://accounts.google.com; frame-ancestors 'none'; report-uri /api/v1/csp-report/" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
add_header Cross-Origin-Opener-Policy "same-origin-allow-popups" always;
add_header X-Frame-Options "DENY" always;
```

Notes: the app ships one CSS file and no inline `<script>` or `<style>` blocks, so this policy is written without
`'unsafe-inline'`. It could not be exercised in a real browser in the build environment, so deploy it first as
`Content-Security-Policy-Report-Only`, click through the site (including the editor, charts and YouTube embeds as staff),
read the reports and only then switch to the enforcing header. If you serve the API from another origin, add it to
`connect-src`.

---

## 6. Rate limits

All rates can be overridden with `THROTTLE_<SCOPE>` (for example `THROTTLE_LOGIN=20/min`).

| Scope | Default | Counted per | Used for |
|---|---|---|---|
| `anon` | 100/hour | IP | fallback for anonymous requests |
| `user` | 1000/hour | user | fallback for logged-in requests |
| `login` | 10/min | IP | login (plus the failed-login lockout below) |
| `register` | 10/hour | IP | sign-up |
| `password_reset` | 5/hour | IP | reset requests and confirmation |
| `email_resend` | 5/hour | user | resend verification |
| `email_verify` | 30/hour | IP | confirming an e-mail link |
| `password_change` | 10/hour | user | change password |
| `logout` | 60/min | IP | logout |
| `profile_update` | 30/hour | user | profile edits |
| `media_upload` | 60/hour | user | upload requests (plus `MEDIA_UPLOAD_QUOTA_PER_HOUR`, default 100 files) |
| `public_read` | 120/min | IP | public website read API |
| `like` | 60/min | user | like and unlike |
| `comment` | 10/hour | user | posting comments |
| `report` | 20/hour | user | reporting comments |
| `analytics` | 120/min | IP | page-view events |
| `admin_write` | 300/min | staff user | every admin write |
| `mfa` | 10/10min | user | two-step verification attempts |
| `data_export` | 3/hour | user | download my data |
| `account_delete` | 3/hour | user | delete my account |
| `csp_report` | 30/min | IP | browser CSP reports |

Failed-login lockout: 5 failures in 15 minutes for the same email and IP gives 429 with `Retry-After`; a success clears it.
Behind Nginx set `NUM_PROXIES=1` so the real client address is used (otherwise every visitor shares the proxy's address).

---

## 7. Cookies and browser storage

Only strictly necessary cookies exist. Nothing else sets a cookie: not the analytics, not the consent banner, no third party.

| Name | Type | Purpose | Lifetime | Necessary |
|---|---|---|---|---|
| `sessionid` | cookie | keeps you logged in (`HttpOnly`, `SameSite=Lax`, `Secure` in production) | 14 days (staff: also ends after `STAFF_SESSION_IDLE_MINUTES` idle) | yes |
| `csrftoken` | cookie | protects forms and requests from other sites (readable by JavaScript on purpose) | about 1 year | yes |
| `sb.visitor-id` | localStorage | random code for counting visitors; only a keyed hash reaches the server | until cleared | no |
| `sb.session-id` | sessionStorage | groups pages of one visit | until the tab closes | no |
| `sb.analytics-off` | localStorage | remembers the opt-out | until cleared | no |
| `sb.consent` | localStorage | remembers the banner answer | 6 months | no |
| `sb.signup-prompt.quiet-until` | localStorage | quiet period after closing the sign-up invitation | 14 days | no |
| `sb.page-views` | sessionStorage | counts pages in this visit (never sent) | until the tab closes | no |
| `storyboard:draft:<id>` | sessionStorage | staff: crash copy of an unsaved story | until the tab closes | yes |

The privacy page prints this table from the same source as the code (`/api/v1/privacy-policy/` for cookies,
`frontend/src/privacy/storageKeys.js` for storage), and tests fail if the table and the code disagree.

---

## 8. Endpoint inventory

Generated from the URL configuration. A test (`test_every_api_view_declares_its_permissions` and friends) walks the real
URL conf and fails if a view has no explicit `permission_classes`, if an `/admin/` view is not staff-only, or if an
unauthenticated write has no throttle scope. All paths are under `/api/v1/`.

| Group | Paths | Who | Notes |
|---|---|---|---|
| Public read | `stories/`, `stories/{slug}/`, `stories/{slug}/related/`, `categories/`, `categories/{slug}/stories/`, `tags/`, `search/`, `sitemap-data/`, `stories/{slug}/comments/` (GET), `stories/{slug}/likes/` | anyone | `public_read` throttle; public serializers with explicit field lists |
| Public info | `health/`, `public-config/`, `privacy-policy/`, `auth/csrf/`, `auth/providers/` | anyone | no secrets |
| Anonymous writes | `analytics/collect/` (no CSRF), `csp-report/` (no CSRF), `auth/register/`, `auth/login/`, `auth/password/reset/`, `auth/password/reset/confirm/`, `auth/email/verify/`, `auth/logout/` | anyone | all throttled; the two collectors write only anonymous data |
| Reader (logged in) | `auth/me/` (GET, PATCH, DELETE), `auth/me/export/`, `auth/password/change/`, `auth/email/resend/`, `auth/sessions/`, `auth/sessions/revoke-all/`, `stories/{slug}/like/`, `stories/{slug}/comments/` (POST), `comments/{id}/` (edit, delete own), `comments/{id}/report/` | authenticated | object ownership checked; throttled |
| Two-step (staff) | `auth/mfa/status/`, `setup/`, `confirm/`, `verify/`, `disable/`, `recovery-codes/` | staff | `mfa` throttle |
| Admin content | `admin/stories/...`, `admin/categories/...`, `admin/tags/...`, `admin/media/...`, `admin/comments/...`, `admin/comment-settings/` | staff (+ MFA when on) | `admin_write` throttle on writes; audited |
| Admin analytics | `admin/analytics/overview|daily|stories|traffic/` | staff | read only |
| Admin users | `admin/users/`, `admin/users/{id}/` (PATCH only `is_active`, `is_staff`), `.../revoke-sessions/`, `.../resend-verification/` | staff; `is_staff` changes superuser only | audited; self and last-superuser rules |
| Admin audit | `admin/audit-logs/` | staff | read only (PATCH and DELETE give 405) |
| Admin misc | `admin/ping/` | staff | used by the frontend guard |
| Docs | `schema/`, `docs/` | anyone | API description only |
| Allauth | `/accounts/google/login/` and callback | anyone | Google OAuth through django-allauth |

---

## 9. Audit log

`apps/audit` records who did what, when and to which object. It is append-only: the model and its queryset refuse updates
and deletes, there is no API to change or remove an entry (the only removal is retention, below).

Each entry: actor (kept as a link while the account exists), `actor_label` (the display name at that time, replaced by
"Deleted user" when the account is anonymised), `action`, `object_type`, `object_id`, `metadata` (ids, titles, changed
field names, old and new status; never passwords, tokens, story bodies or comment text), `ip_hash` (an HMAC of the IP
with `AUDIT_HASH_SECRET`; the raw address is never stored) and `created_at`.

Writing an entry never breaks the action it records (failures are logged and swallowed) and is part of the same
transaction: if the action fails or rolls back, so does its entry.

### Event catalog

| Action | When |
|---|---|
| `story.create`, `story.update`, `story.publish`, `story.unpublish`, `story.archive`, `story.schedule`, `story.delete`, `story.restore_revision` | story changes |
| `category.create|update|delete`, `tag.create|update|delete` | taxonomy changes |
| `media.upload`, `media.replace`, `media.update`, `media.delete` | image library |
| `comment.status`, `comment.reports_dismissed`, `settings.comment_moderation` | moderation |
| `analytics.purge`, `audit.purge` | retention jobs (command and Celery task) |
| `user.update`, `user.sessions_revoked`, `user.verification_resent`, `user.anonymised` | user management and account deletion |
| `auth.staff_login`, `auth.staff_login_failed`, `auth.password_changed` | staff authentication (reader logins are not logged) |
| `mfa.enabled`, `mfa.disabled`, `mfa.recovery_used`, `mfa.recovery_regenerated`, `mfa.verify_failed` | two-step verification |

The catalog lives in `apps/audit/actions.py`; a test checks that every listed action is written by real code.
View the log at `/admin/audit-logs` (filters: action family, actor, type, object id, dates, search) or
`GET /api/v1/admin/audit-logs/`.

---

## 10. Two-step verification (MFA) for staff

Standard TOTP (RFC 6238): HMAC-SHA1, 30 second step, 6 digits, one step of clock drift accepted, constant-time compare.
A code can be used once (replay protection). Implemented with the standard library only, no QR code library: the setup
screen shows the key to type and an `otpauth://` link.

Where the secret lives: encrypted at rest with a key derived from `MFA_ENCRYPTION_KEY` (or from `DJANGO_SECRET_KEY` when
empty). Recovery codes: 10, shown once, stored hashed, each works once.

Enforcement is in the permission layer (`IsStaffUser` and `IsSuperUser`), on every request, so a Google login or a stolen
session cookie cannot skip it:

- staff with a confirmed device need `session["mfa_verified"]`, otherwise 403 with `code: "mfa_required"`
- with `STAFF_MFA_REQUIRED=true`, staff without a device get 403 with `code: "mfa_setup_required"`
- turning it off, creating new recovery codes, changing the password and deleting the account each need a fresh code

### Setting it up

1. Log in as staff, open **Account → Security → Set up two-step verification**.
2. Type the key into an authenticator app (or open the link on the phone), enter the 6-digit code.
3. Save the 10 recovery codes (the "I saved them" box unlocks the Done button). They are not shown again.

### When a staff member loses their phone

1. They log in and choose "Use a recovery code instead" on the code screen.
2. No recovery codes left: a **superuser** on the server runs
   `python manage.py shell -c "from apps.accounts.models import MFADevice; MFADevice.objects.filter(user__email='person@example.com').delete()"`
   and the person sets it up again. This is a server action on purpose: no web screen can switch MFA off for someone else.
   Their next login and the new setup are audited like any other.
3. If the only superuser loses access, the same command on the server restores it.

---

## 11. Retention

| Data | Kept | Setting | Cleaned by |
|---|---|---|---|
| Raw analytics events | 90 days (minimum 35) | `ANALYTICS_RETENTION_DAYS` | `manage.py purge_analytics`, daily Celery job |
| Daily analytics totals | kept (no personal data) | none | none |
| Audit log | 365 days (minimum 30) | `AUDIT_RETENTION_DAYS` | `manage.py purge_audit_logs` (`--dry-run` available), monthly Celery job; the purge writes one summary entry |
| Comments | until deleted | none | readers delete their own; account deletion marks them deleted |
| Deleted accounts | the account row stays, anonymised (email `deleted-<id>@invalid.invalid`, name "Deleted user", no bio, picture or links) so counters and history stay correct | none | n/a |
| Sessions | `SESSION_COOKIE_AGE` (14 days); staff idle limit | `STAFF_SESSION_IDLE_MINUTES` | run `python manage.py clearsessions` daily (cron) to drop expired rows |

The privacy page quotes these numbers from the live settings, not from text.

---

## 12. Pre-deployment checklist

- [ ] `DJANGO_SECRET_KEY` generated, 50+ characters, different from every other environment
- [ ] `DEBUG` off; `DJANGO_ALLOWED_HOSTS`, `FRONTEND_URL`, CORS and CSRF origins are your real `https://` names
- [ ] PostgreSQL and Redis are not reachable from the internet; strong database password
- [ ] HTTPS everywhere (certificate renewed automatically); `NUM_PROXIES=1` behind Nginx
- [ ] `DJANGO_ADMIN_URL` changed, or `DJANGO_ADMIN_ENABLED=false`
- [ ] Every staff account has two-step verification; consider `STAFF_MFA_REQUIRED=true`
- [ ] `create_admin` run once; no shared accounts
- [ ] `SITE_CONTACT_EMAIL`, `SITE_OPERATOR_NAME` and `PRIVACY_POLICY_DATE` filled in; privacy text reviewed (below)
- [ ] `PRIVACY_CONSENT_MODE` chosen for your visitors (`notice`, `opt_in` or `opt_out`)
- [ ] Nginx adds the CSP and headers from section 5; test with `CSP_REPORT_ONLY=true` first
- [ ] Email works (verification and reset links), `DEFAULT_FROM_EMAIL` has SPF and DKIM
- [ ] Media storage bucket is private for writes, public read only; CDN host added to the CSP `img-src`
- [ ] Celery worker and beat running (scheduled stories, analytics aggregation and purge, audit purge)
- [ ] A daily `python manage.py clearsessions` (cron) so expired sessions are removed
- [ ] Backups of the database and media, tested restore (Phase 12)
- [ ] Run `pip-audit` (backend) and `npm audit` (frontend) and update vulnerable packages
- [ ] Run the full test suites (commands in the README)
- [ ] `python manage.py check --deploy` shows no warnings with `DJANGO_SETTINGS_MODULE=config.settings.production`

---

## 13. Known limits and what needs the site owner

- Tests were written and statically checked but the development sandbox could not install Django or npm packages, so the
  suites should be run on your machine before launch (see the README).
- Rate limits depend on the real client IP: wrong `NUM_PROXIES` makes limits too strict or too loose.
- TOTP protects against stolen passwords and sessions, not against malware on the staff member's own device.
- The audit log can be deleted by someone with database access; ship it to external storage if you need tamper evidence.
- Account deletion anonymises; comments are marked deleted but the rows stay (needed for counters and replies).
- No CAPTCHA and no IP reputation service (no third-party services were allowed in this phase).
- **Legal review needed (not legal advice):** the privacy page is generated from your settings and states facts about the
  software. The "legal basis" wording is generic and marked "to be confirmed by the site owner". Whether you need a consent
  banner (`opt_in`), a data processing agreement with your host, an age limit, a data-protection contact, an international
  transfer notice or specific retention periods depends on your country and visitors. Have a qualified person review the
  text before you launch.
