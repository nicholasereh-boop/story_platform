"""The rights gate. Every path that can show news text to the public (manual publish, import review, API read) asks this
module first; nothing else decides what ResourceBoard may republish (docs/SOURCE_AND_RIGHTS_POLICY.md).

Rules, in plain words:
  * A source must be approved AND active, and have an approved rights record that is in force right now.
  * The source is a ceiling: a rights record can narrow it (no full text, no commercial use), never widen it.
  * "Headlines and links only" sources never allow article text.
  * Approving a record needs evidence (a link or a note). Approved records are not edited; a new licence version is a new record.
  * When rights end (revoked, expired, source suspended) everything already published from that source is quarantined by the
    handlers registered in LOSS_HANDLERS (the article service registers one in Phase 3).
"""
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from ..models import NewsRightsRecord, NewsSource
from . import policy

# Callables taking (source, reason). Phase 3 registers the one that moves published articles to "quarantined".
LOSS_HANDLERS = []
# Callables taking (record, reason), called whenever an APPROVED record is revoked or expires, even if the source has another valid record:
# articles published under that record must be re-checked. The article service registers one.
RECORD_HANDLERS = []


class RightsError(ValueError):
    """A rights or approval action that is not allowed in the current state. The message is safe to show to staff."""


@dataclass
class RightsDecision:
    allowed: bool = False
    record: object = None
    full_text: bool = False
    commercial: bool = False
    modification: bool = False
    attribution_required: bool = True
    counter_required: bool = False
    caching: bool = False
    archive: bool = False
    reasons: list = field(default_factory=list)

    def as_dict(self):
        return {
            "allowed": self.allowed,
            "record_id": self.record.pk if self.record else None,
            "full_text": self.full_text,
            "commercial": self.commercial,
            "modification": self.modification,
            "attribution_required": self.attribution_required,
            "counter_required": self.counter_required,
            "caching": self.caching,
            "archive": self.archive,
            "reasons": list(self.reasons),
        }


def record_in_force(record, now=None):
    now = now or timezone.now()
    if record.status != NewsRightsRecord.Status.APPROVED:
        return False
    if record.effective_from and record.effective_from > now:
        return False
    return not (record.effective_until and record.effective_until <= now)


def current_record(source, now=None):
    """The newest approved record that is in force, or None. Newest first, so a renewed licence wins over an old one."""
    now = now or timezone.now()
    for record in source.rights_records.filter(status=NewsRightsRecord.Status.APPROVED).order_by("-effective_from", "-id"):
        if record_in_force(record, now):
            return record
    return None


def evaluate(source, record=None, now=None):
    """What may ResourceBoard do with this source's text right now? `record` pins a specific record (an article keeps the
    record it was imported under); without it the newest record in force is used."""
    now = now or timezone.now()
    decision = RightsDecision()
    if source.approval_state != NewsSource.Approval.APPROVED:
        decision.reasons.append("source_not_approved")
    if not source.is_active:
        decision.reasons.append("source_inactive")
    if record is None:
        record = current_record(source, now)
    if record is None:
        decision.reasons.append("no_rights_record")
    elif record.source_id != source.pk:
        decision.reasons.append("record_belongs_to_another_source")
    elif not record_in_force(record, now):
        decision.reasons.append("rights_not_in_force")
    if source.source_type == NewsSource.SourceType.METADATA_ONLY:
        decision.reasons.append("metadata_only_source")
    # "metadata_only_source" blocks article text but is not an approval problem; keep the two apart.
    blocking = [r for r in decision.reasons if r != "metadata_only_source"]
    if blocking or record is None:
        return decision
    decision.record = record
    decision.allowed = source.source_type != NewsSource.SourceType.METADATA_ONLY
    decision.full_text = decision.allowed and source.allows_full_text and record.allows_full_text
    decision.commercial = decision.allowed and source.allows_commercial_use and record.allows_commercial_use
    decision.modification = decision.allowed and record.allows_modification
    decision.attribution_required = record.requires_attribution or source.source_type != NewsSource.SourceType.ORIGINAL
    decision.counter_required = record.requires_counter
    decision.caching = decision.allowed and record.allows_caching
    decision.archive = decision.allowed and record.allows_archive
    if source.allows_full_text and not record.allows_full_text:
        decision.reasons.append("record_narrows_full_text")
    if source.allows_commercial_use and not record.allows_commercial_use:
        decision.reasons.append("record_narrows_commercial_use")
    return decision


def render_attribution(source, record=None, *, author="", original_url="", published=""):
    """The credit line shown with an article, from the source's template. Unknown tokens are left out, never executed."""
    template = source.attribution_template or "Source: {source}"
    values = {
        "author": author or "",
        "source": source.name,
        "original_url": original_url or source.website_url or "",
        "licence": (record.licence if record else "") or "",
        "published": published or "",
    }
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", str(value))
    return " ".join(out.split())[:400]


# ---- state changes ---------------------------------------------------------------------------------------------
def _notify_loss(source, reason):
    for handler in LOSS_HANDLERS:
        handler(source, reason)


def _notify_record(record, reason):
    for handler in RECORD_HANDLERS:
        handler(record, reason)


def approve_record(record, user, now=None):
    if record.status != NewsRightsRecord.Status.DRAFT:
        raise RightsError("Only a draft rights record can be approved.")
    if not (record.evidence_url or record.evidence_note.strip()):
        raise RightsError("Add evidence (a link or a note about where the agreement is kept) before approving.")
    now = now or timezone.now()
    if record.effective_until and record.effective_until <= now:
        raise RightsError("This record has already ended. Create a new one.")
    if record.source.source_type == NewsSource.SourceType.METADATA_ONLY:
        raise RightsError("A headlines-and-links source does not need a rights record for text. Change the source type first.")
    if policy.source_is_denylisted(record.source) and record.basis not in policy.PERMISSION_BASES:
        raise RightsError("This publisher stays unapproved until a written permission or syndication agreement is recorded as the rights basis.")
    record.status = NewsRightsRecord.Status.APPROVED
    record.reviewed_by = user
    record.reviewed_at = now
    record.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    return record


def revoke_record(record, user, reason, now=None):
    if record.status not in (NewsRightsRecord.Status.APPROVED, NewsRightsRecord.Status.DRAFT):
        raise RightsError("This record is already closed.")
    reason = (reason or "").strip()
    if not reason:
        raise RightsError("Say why the rights are being revoked.")
    now = now or timezone.now()
    was_approved = record.status == NewsRightsRecord.Status.APPROVED
    with transaction.atomic():
        record.status = NewsRightsRecord.Status.REVOKED
        record.revoked_at = now
        record.revoked_reason = reason[:300]
        record.reviewed_by = user
        record.save(update_fields=["status", "revoked_at", "revoked_reason", "reviewed_by", "updated_at"])
        if was_approved:
            _notify_record(record, "rights_revoked")
            if current_record(record.source, now) is None:
                _notify_loss(record.source, "rights_revoked")
    return record


def approve_source(source, user, now=None):
    if source.approval_state not in (NewsSource.Approval.PENDING, NewsSource.Approval.SUSPENDED):
        raise RightsError("Only a pending or suspended source can be approved.")
    if not (source.evidence_ref.strip() or source.terms_url):
        raise RightsError("Record where the agreement or terms are kept (evidence reference or terms link) before approving.")
    source.approval_state = NewsSource.Approval.APPROVED
    source.reviewed_by = user
    source.reviewed_at = now or timezone.now()
    source.save(update_fields=["approval_state", "reviewed_by", "reviewed_at", "updated_at"])
    return source


def suspend_source(source, user, reason="", now=None):
    if source.approval_state != NewsSource.Approval.APPROVED:
        raise RightsError("Only an approved source can be suspended.")
    with transaction.atomic():
        source.approval_state = NewsSource.Approval.SUSPENDED
        source.is_active = False
        source.reviewed_by = user
        source.reviewed_at = now or timezone.now()
        source.save(update_fields=["approval_state", "is_active", "reviewed_by", "reviewed_at", "updated_at"])
        _notify_loss(source, "source_suspended")
    return source


def reject_source(source, user, now=None):
    if source.approval_state == NewsSource.Approval.APPROVED:
        raise RightsError("Suspend an approved source before rejecting it.")
    source.approval_state = NewsSource.Approval.REJECTED
    source.is_active = False
    source.reviewed_by = user
    source.reviewed_at = now or timezone.now()
    source.save(update_fields=["approval_state", "is_active", "reviewed_by", "reviewed_at", "updated_at"])
    return source


def expire_due_records(now=None):
    """Close approved records whose end date has passed; quarantine sources that are left with no valid record.
    Run daily by the scheduled task added in Phase 4. Returns the number of records expired."""
    now = now or timezone.now()
    due = list(NewsRightsRecord.objects.filter(status=NewsRightsRecord.Status.APPROVED, effective_until__isnull=False, effective_until__lte=now).select_related("source"))
    sources = {}
    for record in due:
        with transaction.atomic():
            record.status = NewsRightsRecord.Status.EXPIRED
            record.save(update_fields=["status", "updated_at"])
            _notify_record(record, "rights_expired")
        sources[record.source_id] = record.source
    for source in sources.values():
        if current_record(source, now) is None:
            _notify_loss(source, "rights_expired")
    return len(due)
