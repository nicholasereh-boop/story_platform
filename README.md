# Story Publishing Platform (Django + React)

Roadmap progress: **Phase 2** (Django foundation), **Phase 3** (accounts, auth, permissions, rate limiting) and **Phase 4** (Story CMS backend).
The React frontend arrives in later phases.

## What is here
- `backend/` Django 5.2 + DRF, project `config` (split settings: base / development / production)
- `backend/apps/accounts` custom email-based `User`, `Profile`, auth API, django-allauth (Google), lockout throttle
- `backend/apps/core` response envelope, permissions, health + admin ping endpoints
- `backend/apps/stories` stories, categories, tags, revisions, content schema, admin API (Phase 4)
- `backend/apps/{comments,reactions,media,analytics,audit}` empty skeletons for later phases
- `deployment/compose/docker-compose.yml` PostgreSQL + Redis for local development

## First time setup

```bash
# 1. PostgreSQL + Redis (needs Docker)
cd deployment/compose && docker compose up -d && cd ../..

# 2. Python environment
cd backend
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # Windows: copy .env.example .env

# 3. Database
python manage.py migrate
python manage.py create_admin you@example.com    # asks for the password (hidden)

# 4. Run
python manage.py runserver
```

### Reset the database (needed once when upgrading from Phase 2: the user table changed)
```bash
cd deployment/compose && docker compose down -v && docker compose up -d && cd ../../backend
# SQLite instead:  rm db.sqlite3
python manage.py migrate
python manage.py create_admin you@example.com
```

### After changing models
```bash
python manage.py makemigrations
python manage.py migrate
```

### Tests (no Redis, Postgres, Google or SMTP needed)
```bash
pytest
```

## Environment variables (backend/.env)

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` | core Django |
| `DATABASE_URL` or `DB_*` | PostgreSQL (empty in development = SQLite) |
| `REDIS_URL` | cache (throttle counters) + Celery broker |
| `FRONTEND_URL` | CORS/CSRF origin, email links, Google redirects |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google login (empty = Google login disabled, nothing crashes) |
| `SITE_NAME`, `DEFAULT_FROM_EMAIL` | email text |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | production email (development prints emails in the terminal) |
| `NUM_PROXIES` | reverse proxies in front of Django. **Set to 1 behind Nginx**, otherwise every visitor shares one IP in rate limits |
| `THROTTLE_LOGIN` etc. | optional rate overrides, e.g. `THROTTLE_LOGIN=20/min` |

## Google Cloud setup
1. Google Cloud Console -> **APIs & Services -> Credentials -> Create credentials -> OAuth client ID -> Web application**.
2. **Authorized JavaScript origins:** `http://localhost:5173`
3. **Authorized redirect URI:** `http://localhost:8000/accounts/google/login/callback/`
   (in production use your real API domain with the same path).
4. Put the client ID and secret in `backend/.env`.

### Starting Google login from React
allauth requires a **POST**. The React app submits a real HTML form so the browser follows the redirects:

```js
function loginWithGoogle() {
  const csrf = document.cookie.split("; ").find((c) => c.startsWith("csrftoken="))?.split("=")[1];
  const form = document.createElement("form");
  form.method = "POST";
  form.action = "/accounts/google/login/";   // proxied to Django in development
  for (const [name, value] of [["csrfmiddlewaretoken", csrf], ["process", "login"]]) {
    const input = document.createElement("input");
    input.type = "hidden"; input.name = name; input.value = value;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  form.submit();
}
```
After Google, the browser returns to `FRONTEND_URL`; on failure to `FRONTEND_URL/login?error=google`.
Call `GET /api/v1/auth/csrf/` once on app start so the `csrftoken` cookie exists.
In development the Vite dev server must proxy both `/api` and `/accounts` to `http://localhost:8000`.

## API (all under /api/v1/, every response is `{data, pagination, errors, message}`)

| Method + path | Auth | What it does |
|---|---|---|
| GET `auth/csrf/` | none | sets the CSRF cookie |
| POST `auth/register/` | none | email, password (min 10), display_name -> creates user, logs in, sends verification email |
| POST `auth/login/` | none | email, password. Same error for unknown email and wrong password |
| POST `auth/logout/` | session + CSRF | ends the session |
| GET `auth/me/` | none | the user, or `{"data": null}` |
| PATCH `auth/me/` | login | `display_name`, `bio` only |
| POST `auth/email/verify/` | none | `{key}` from the email link |
| POST `auth/email/resend/` | login | resend verification |
| POST `auth/password/reset/` | none | `{email}`; identical answer for any email |
| POST `auth/password/reset/confirm/` | none | `{uid, token, password}` |
| GET `admin/ping/` | staff | permission smoke test |

## Security notes
- Session cookie (HttpOnly, SameSite=Lax, 14 days) + CSRF token. No JWT, nothing in localStorage.
- Failed logins: after 5 failures per email+IP in 15 minutes -> 429 with `Retry-After`. A good login clears it.
- Other limits: login 10/min, register 10/hour, password reset 5/hour, email resend 5/hour, profile update 30/hour.
- Only superusers may create staff (`create_admin`; the Phase 10 user manager will use `IsSuperUser`). Public sign-up never creates staff.
- Never commit `.env`. Never log passwords, tokens or reset links.

## Phase 4: Story CMS (admin API)

Stories are TipTap JSON, validated by an allowlist (`docs/CONTENT_SCHEMA.md`). Only staff can use these endpoints.

```bash
cd backend
python manage.py makemigrations stories     # no-op if the shipped 0001 migration already matches
python manage.py migrate
python manage.py runserver
pytest
```
No database reset is needed. Optional: `python manage.py publish_scheduled` (also runs as a Celery beat task every minute).

| Method + path (under `/api/v1/admin/`) | What it does |
|---|---|
| GET `stories/` | paginated list (12), no content. Filters `status`, `q`, `category` (slug), `tag` (slug), `featured=1`, `ordering` |
| POST `stories/` | create a **draft** (revision 1) |
| GET / PATCH / DELETE `stories/{id}/` | read, partial update (`?autosave=1` limits revisions), hard delete |
| POST `stories/{id}/publish/` `unpublish/` `archive/` | status changes (publish refuses empty stories) |
| POST `stories/{id}/schedule/` | `{"scheduled_at": "<future ISO datetime>"}` |
| GET `stories/{id}/revisions/` | revision history, newest first |
| POST `stories/{id}/revisions/{rev}/restore/` | copy an old revision back (as a new revision) |
| GET / POST `categories/`, `tags/` | lists with `story_count` (not paginated); tags accept `?q=` |
| GET / PATCH / DELETE `categories/{id}/`, `tags/{id}/` | deleting only unlinks stories |

Rules: `status`, `published_at`, `scheduled_at` and the counters can never be set through create or PATCH; slugs are
unique and stay stable when the title changes; category and tag names are unique ignoring case.
