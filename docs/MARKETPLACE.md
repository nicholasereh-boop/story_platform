# Source code marketplace

Members can list the source code of a website (a **frontend** package, a **backend** package, or both), add screenshots and a
YouTube demo, and sell or give it away. Buyers download it from an authorised endpoint after paying through Paystack.

Code: `backend/apps/source_marketplace/` · `frontend/src/pages/marketplace/` · `frontend/src/components/marketplace/`
Tests: `backend/tests/test_marketplace_*.py` · `frontend/src/__tests__/marketplacePages.test.jsx`

## How it works

1. A signed-in member creates a **draft** (title, description, technologies, prices, "I have the right to distribute this").
2. They add screenshots and upload a ZIP (or import from GitHub) for the frontend and/or backend.
3. They **submit**. With `MARKETPLACE_REQUIRE_REVIEW=true` (default) the project waits in **Marketplace review** (admin sidebar);
   staff approve or reject with a note. Changing the text or files of a live project sends it back to review. Price changes do not.
4. A published project appears in `/marketplace`. Free packages need a signed-in account; paid ones need a verified payment.

Sellers can only ever edit their own projects (everything else is a 404). Staff moderate (approve, reject, archive) but do not edit sellers' content.

## Settings (server environment)

| Setting | Default | Meaning |
| --- | --- | --- |
| `MARKETPLACE_ENABLED` | `true` | `false` makes every marketplace endpoint answer 404 |
| `MARKETPLACE_REQUIRE_REVIEW` | `true` | staff approval before projects go live |
| `MARKETPLACE_CURRENCY` | `NGN` | currency of all prices (sellers cannot choose) |
| `MARKETPLACE_MAX_PRICE` | `5000000` | highest price per package, in major units |
| `MARKETPLACE_PRIVATE_ROOT` | `backend/private_media/marketplace` | where packages are stored (never served as static/media) |
| `MARKETPLACE_MAX_ARCHIVE_BYTES` | 50 MB | largest ZIP accepted |
| `MARKETPLACE_MAX_UNPACKED_BYTES` | 300 MB | archive-bomb limit (bytes actually read) |
| `MARKETPLACE_MAX_FILE_BYTES` / `_MAX_FILES` | 50 MB / 5000 | per-file size and file count |
| `MARKETPLACE_GITHUB_ENABLED` / `_TIMEOUT` | `true` / 30 s | GitHub import |
| `PAYSTACK_SECRET_KEY` | empty | **server only.** Empty = payments off (checkout says "not available"); free packages still work |
| `PAYSTACK_API_BASE` / `PAYSTACK_TIMEOUT` | `https://api.paystack.co` / 20 | |
| `THROTTLE_MARKETPLACE_*` | see `settings/base.py` | per-scope rate limits (`read`, `write`, `upload`, `checkout`, `verify`, `download`, `webhook`) |

Frontend: `VITE_FEATURE_MARKETPLACE=false` hides the pages and links.

## Paystack setup

1. Put your **test** secret key in `PAYSTACK_SECRET_KEY` on the server. It must never appear in the frontend or in Git.
2. In the Paystack dashboard set the webhook URL to `https://YOUR-DOMAIN/api/v1/marketplace/payments/webhook/`.
3. Make one test purchase end to end (test cards are in Paystack's docs), then switch to the live key.

What the code guarantees (all covered by tests): the price and currency come from the database, never from the browser; every
purchase has its own unique reference; the **server** asks Paystack and only accepts a payment when status, reference, amount and
currency all match; webhooks must carry a valid HMAC-SHA512 signature and are re-verified with Paystack before anything changes;
processing is idempotent (retries, duplicates and the browser-vs-webhook race cannot grant twice or log twice); if Paystack
cannot be reached the webhook answers 503 so Paystack retries; a payment with the wrong amount grants nothing and is logged.

The webhook is the one marketplace endpoint that is CSRF-exempt (Paystack cannot send a CSRF token). Its protection is the
signature. The existing allow-list test (`test_security_settings.py`) names it explicitly.

## What the upload check does

Archives are **read and rebuilt**, never extracted to disk, never executed. Rejected outright: path traversal (`../`, absolute
paths), password-protected archives, duplicate names, too many files, archive bombs, anything that expands past the limits, and any
text file containing a private key, AWS key, GitHub token, live payment key, Slack token or Google API key (the message names the
**file**, never the value; the seller must remove and rotate the secret). Silently left out and reported to the seller: `.env*`
(except `.env.example`), key and certificate files, databases, `node_modules`, `.git`, caches, symlinks.

This is a structural and secrets check, **not a malware scan**. Review high-value listings, or add a scanner (for example ClamAV) at `services/uploads.py`.

## GitHub import

Server-side only, from `api.github.com`, following redirects by hand to `codeload.github.com` and nowhere else. Public repositories
need no token. For a private repository the seller pastes a **read-only token limited to that repository**; it is sent once to
`api.github.com` only, never stored, logged or returned, and the form clears it immediately. The token proves read access, not
ownership, which is why publishing requires the "I have the right to distribute this" confirmation (stored with a timestamp).

## Operations

* **Back up `MARKETPLACE_PRIVATE_ROOT`** together with the database. Sold packages cannot be recreated.
* Storage is a local folder, which suits one server. For several servers use a shared volume (or add a private object-storage backend in `storage.py`).
* The web server must allow uploads up to `MARKETPLACE_MAX_ARCHIVE_BYTES` (for nginx: `client_max_body_size 55m;` on `/api/`).
* Every download is recorded in `SourceDownload` (who, which package, free/purchase/owner/staff, a keyed hash of the IP). Marketplace review decisions and verified purchases are in the audit log (`marketplace.*`).

## Known limits (not built)

* **Seller payouts.** The platform receives all payments. Paying sellers (Paystack subaccounts/splits or manual payouts) is a separate decision.
* Refunds and chargebacks are not handled; a staff **reject** blocks further downloads for buyers.
* No webhook IP allow-list (the signature is the control).
* The privacy policy page should name Paystack as a processor: the buyer's email address is sent to it at checkout.
