# Story content schema

Stories are stored in `Story.content_json` as **TipTap / ProseMirror JSON**. HTML is never stored.
Every write goes through `apps/stories/content.py::clean_content()`, which **rebuilds** the document from the
allowlist below and rejects anything else. React renders the JSON itself (no `dangerouslySetInnerHTML`).

```json
{
  "type": "doc",
  "content": [
    { "type": "heading", "attrs": { "level": 2 }, "content": [{ "type": "text", "text": "Chapter one" }] },
    { "type": "paragraph", "content": [
        { "type": "text", "text": "Hello " },
        { "type": "text", "text": "world", "marks": [{ "type": "bold" }, { "type": "link", "attrs": { "href": "https://example.com" } }] }
    ] },
    { "type": "image", "attrs": { "assetId": 12, "alt": "A lighthouse", "caption": "At dusk", "align": "center", "size": "full" } },
    { "type": "youtube", "attrs": { "videoId": "dQw4w9WgXcQ" } }
  ]
}
```

## Nodes

| Node | Kept attributes | Notes |
|---|---|---|
| `doc` | none | root, `content` is always a list |
| `paragraph` | `textAlign` | `left` (default, not stored), `center`, `right`, `justify` |
| `heading` | `level` (1-6, default 2), `textAlign` | |
| `text` | `text`, `marks` | non-empty, max 20000 characters |
| `hardBreak`, `horizontalRule` | none | |
| `bulletList`, `listItem`, `blockquote` | none | |
| `orderedList` | `start` (integer >= 1) | |
| `image` | `assetId` (positive integer, **required**), `alt` (<= 300), `caption` (<= 500), `align` (`left`/`center`/`right`, default `center`), `size` (`small`/`medium`/`full`, default `full`) | `src`, `style`, `onclick` and everything else is dropped. The asset's existence is checked in the media phase |
| `youtube` | `videoId` (11 characters) | input may be `videoId` or `src`; only the ID is stored |

## Marks
`bold`, `italic`, `underline`, `strike`, `link` (`href` only).

**Links** must start with `http://`, `https://` or `mailto:` (any letter case), be at most 2000 characters and contain no
whitespace or control characters. `javascript:`, `data:` and similar are **rejected with an error**, not silently dropped.

## YouTube
Accepted (https only, `www.` / `m.` allowed): `youtube.com/watch?v=ID`, `youtu.be/ID`, `youtube.com/embed/ID`,
`youtube.com/shorts/ID`, `youtube-nocookie.com/embed/ID`. Any other host is rejected. Arbitrary iframes do not exist.

## Rejected / dropped
- Unknown node types and unknown marks: **rejected**.
- Unknown attributes: **dropped**.
- Limits: depth 12, 5000 nodes, 20000 characters per text node, 1 MB serialized.

## Helpers
`clean_content(doc)`, `plain_text(doc)` (excerpts and `search_text`), `has_content(doc)` (publish check),
`asset_ids(doc)` (media phase), `empty_doc()`, `youtube_id(value)`.
