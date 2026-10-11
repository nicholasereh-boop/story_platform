# Media system

An image library for stories. Stories reference images by **id** (`assetId`), never by URL, so an image can be
replaced or moved to a CDN without editing any story.

## Upload rules (enforced in `apps/media/images.py`)

| Rule | Value |
|---|---|
| Formats | JPEG, PNG, WebP, GIF. SVG, HEIC, PDF and everything else are rejected |
| How the format is decided | by decoding the file with Pillow. The file's bytes decide |
| Name and type cross-check | extension (`.jpg .jpeg .png .webp .gif`) **and** Content-Type must both match the detected format. A PNG named `.jpg` is rejected |
| Max size per file | `MEDIA_MAX_UPLOAD_BYTES` (default 5 MB) |
| Max pixels / side | 40,000,000 pixels, 12,000 px on the longest side |
| Files per request | 10, validated all-or-nothing |
| Stored filename | `uploads/YYYY/MM/<uuid4 hex><detected extension>`; the client's name is never used |
| Metadata | EXIF orientation is applied, then JPEG/PNG/WebP are re-encoded **without** EXIF/GPS/XMP |
| Animated images | animated GIF/WebP/PNG are stored unchanged (re-encoding would stop the animation). They are fully decoded and validated, but their metadata is not stripped |
| Rate limit | uploads: 60/hour per user (`THROTTLE_MEDIA_UPLOAD`) |

## API (staff only, `/api/v1/admin/media/`)

| Method + path | What it does |
|---|---|
| POST `media/` | multipart `files` (or `file`); optional `alt_text` when one file is sent; returns 201 + list |
| GET `media/` | gallery, 24 per page, newest first; `?q=` searches alt text and caption; `?ordering=` `created_at`, `size_bytes` (+ `-`) |
| GET `media/{id}/` | one asset plus `used_in` (stories using it as cover or in content) |
| PATCH `media/{id}/` | only `alt_text` and `caption` |
| POST `media/{id}/replace/` | multipart `file`: new file, same id |
| DELETE `media/{id}/` | refused (400, with `used_in`) while in use; `?force=1` deletes anyway |

Stories: `cover_image` (id, nullable) is writable; responses include `cover` (`id, url, alt_text, width, height`).
Saving content that references a missing image is rejected. Admin story detail and revisions return image nodes with
read-only `src`, `width` and `height` added (`resolve_media`).

## Storage

**Local disk (default)**: files go to `backend/media/` and Django serves them only when `DEBUG=True`.

**S3-compatible object storage**: set `MEDIA_STORAGE_BUCKET` (and the related variables in `backend/.env`).
Works with AWS S3, Cloudflare R2, MinIO and DigitalOcean Spaces. Leave everything empty to stay on local disk.

| Variable | Notes |
|---|---|
| `MEDIA_STORAGE_BUCKET` | turns object storage on |
| `MEDIA_STORAGE_REGION` | e.g. `eu-west-1`, `auto` for R2 |
| `MEDIA_STORAGE_ACCESS_KEY` / `MEDIA_STORAGE_SECRET_KEY` | credentials (never commit them) |
| `MEDIA_STORAGE_ENDPOINT` | R2 / MinIO / Spaces endpoint; leave empty for AWS |
| `MEDIA_CDN_DOMAIN` | public domain in front of the bucket, if any |

Objects are public-read through the bucket policy (no signed URLs) and are sent with
`Cache-Control: public, max-age=31536000, immutable`, which is safe because every filename is unique.

### Try it locally with MinIO
Install MinIO on your machine (<https://min.io/download>, or `brew install minio/stable/minio` on macOS) and start it:
```bash
minio server ./minio-data --console-address ":9001"
```
1. Open http://localhost:9001 and sign in with `minioadmin` / `minioadmin`.
2. Create a bucket called `story-media`, then open it -> **Access Policy** -> **Public** (read access).
3. In `backend/.env`:
```
MEDIA_STORAGE_BUCKET=story-media
MEDIA_STORAGE_REGION=us-east-1
MEDIA_STORAGE_ACCESS_KEY=minioadmin
MEDIA_STORAGE_SECRET_KEY=minioadmin
MEDIA_STORAGE_ENDPOINT=http://localhost:9000
```
4. Restart the Django server and upload an image; its `url` now starts with `http://localhost:9000/story-media/`.

## Production notes
- **Never serve `/media/` from Django.** Use Nginx or a CDN/object storage domain.
- Send these headers for everything under the media path:
  `X-Content-Type-Options: nosniff` and `Content-Security-Policy: default-src 'none'`.
- Raise the request size limit above the largest upload request, e.g. Nginx `client_max_body_size 60m;`
  (10 files x 5 MB = 50 MB).
- Uploaded files are never executed: no script handlers on the media path.
- Behind Nginx set `NUM_PROXIES=1` so upload throttling sees real client addresses.
```nginx
location /media/ {
    alias /srv/story-platform/media/;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Content-Security-Policy "default-src 'none'" always;
    expires 1y;
}
```
