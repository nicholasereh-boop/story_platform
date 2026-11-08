# Source and Rights Policy

## Fundamental rule
An API key, RSS feed, public webpage, or accessible article does not itself grant rights to republish the complete article. Record rights for article text and every image/video separately, including ad-supported commercial use. This is an engineering policy, not legal advice; obtain qualified legal review.

## Candidates to evaluate
### The Conversation
Its republication guidance describes Creative Commons Attribution-NoDerivatives terms and conditions. Verify the current licence and individual article. Conditions can include preserving text, crediting author/institution and The Conversation, linking to the original, and including a page-view counter. Images, charts, and interactive media may have separate rights. Do not assume bulk API rights.
- https://theconversation.com/republishing-guidelines
- https://theconversation.com/au/republishing-and-media

### Wikinews
Wikinews has date-specific licence rules; material published after 16 December 2024 is stated to use CC BY 4.0, while older items may differ. Attribute and inspect every media asset separately.
- https://en.wikinews.org/wiki/Wikinews:COPYRIGHT

### Europeana
API metadata is CC0, but linked objects must be reused according to each object's rights statement. This is primarily a cultural-heritage source, not a breaking-news feed.
- https://europeana.atlassian.net/wiki/spaces/EF/pages/2360508417

## Conventional publishers
Keep BBC, CNN, Vanguard, Reuters, AP, ESPN, Sky Sports, Goal, and similar publishers unapproved for full-text republication until a licence/written permission covers hosting complete text, advertising, assets, territory, term, volume, editing/translation, caching/archives, attribution, reporting, and takedown.

Do not scrape publisher websites or reconstruct complete articles from headline APIs.

## Auto-publication gate
Publish only if the source and specific article are covered; full-text and commercial use are allowed; attribution/counters are implemented; each asset is cleared or omitted; rights are current; and editorial checks pass. If uncertain, hold for review or use original ResourceBoard reporting.

Content types: licensed full text, open-licensed full text, verified public domain, ResourceBoard original, metadata-only.

## Onboarding and takedown
Save terms/agreement; verify commercial and media rights; record attribution, expiry, renewal contact, and storage restrictions; review a sample before enabling. Provide a copyright contact. For credible complaints, unpublish disputed content, preserve audit records, notify the editor/source, and restore only after resolution.

## How the code enforces this policy
| Rule | Where it is enforced |
| --- | --- |
| A source must be approved and have an approved, in-force rights record before anything from it can go live | `services/rights.py` (`evaluate`), `services/articles.py` (`check_publishable`) |
| The source is a ceiling: a rights record may narrow what the source allows (full text, commercial use) but never widen it | `services/rights.py` |
| Approved rights records cannot be edited; to change terms, add a new record | `services/rights.py` |
| Conventional publishers (the list above) cannot get an approved record without written permission or a syndication agreement | `services/policy.py`, checked in `rights.approve_record` |
| Text and every image or video are cleared separately; only cleared, unexpired, commercially usable assets are shown | `NewsAsset.is_displayable` |
| Editing is blocked when the licence does not allow modification | `check_publishable` (`edits_not_permitted`) |
| A lapsed, revoked or suspended licence takes articles off the site (quarantine) and hides their comments; restoring goes to the review queue, never straight to public | `services/articles.py` (`quarantine`, `sweep_rights`, `restore`) |
| Readers' pages re-check rights on every read, so a stale cache cannot show lapsed content | `public_views.get_public_article_or_404` |
| Imports never scrape article pages; only the registered https feed is fetched, with SSRF protection; imports wait in the review queue | `providers/rss.py`, `services/netguard.py`, `services/ingest.py` |
| Duplicates are caught by external id, canonical URL and content hash | `services/ingest.py`, `services/articles.py` (`find_duplicate`) |
| Credible complaints put the article on hold at once; it is restored only after the complaint is dismissed, and then to review | `services/takedown.py` |
| Every decision is written to the audit log | `apps/audit` (`news.*` actions) |

## Running it day to day
- **Before enabling a source:** save the agreement, record the rights record (licence, basis, what is allowed, end date, evidence link or where the paper copy is kept), check a sample of articles, then approve the record and the source, in that order.
- **Renewals:** the health strip and the hourly monitor warn `NEWS_RIGHTS_WARNING_DAYS` (default 14) days before a record ends. Add the new record before the old one ends. When it ends, the daily maintenance task quarantines the articles.
- **Complaints:** answer within one working day. Put the article on hold first, then decide: uphold (withdraw) or dismiss (back to review). Write a resolution note either way.
- **Copyright contact:** set `NEWS_COPYRIGHT_CONTACT`. It appears on every article page and on the report form.