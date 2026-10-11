"""The audit event catalog: every action name that audit.log() may record, with a plain-language description.

The admin UI shows these descriptions, docs/SECURITY.md lists them, and a test checks that each one is written by
real code. Add new events here first.
"""
ACTIONS = {
    # stories
    "story.create": "Story created",
    "story.update": "Story saved",
    "story.publish": "Story published",
    "story.unpublish": "Story unpublished (back to draft)",
    "story.archive": "Story archived",
    "story.schedule": "Story scheduled",
    "story.delete": "Story deleted",
    "story.restore_revision": "Story restored from an earlier version",
    # taxonomy
    "category.create": "Category created",
    "category.update": "Category changed",
    "category.delete": "Category deleted",
    "tag.create": "Tag created",
    "tag.update": "Tag changed",
    "tag.delete": "Tag deleted",
    # media
    "media.upload": "Image uploaded",
    "media.replace": "Image file replaced",
    "media.update": "Image details changed",
    "media.delete": "Image deleted",
    # comments and settings
    "comment.status": "Comment status changed",
    "comment.reports_dismissed": "Comment reports dismissed",
    "settings.comment_moderation": "Comment moderation mode changed",
    # analytics and audit retention
    "analytics.purge": "Old analytics events purged",
    "audit.purge": "Old audit entries purged",
    # users
    "user.update": "User account changed (active / staff)",
    "user.sessions_revoked": "User signed out of all devices by an administrator",
    "user.verification_resent": "Verification email re-sent by an administrator",
    "user.anonymised": "Account deleted (anonymised) at the owner's request",
    # authentication and MFA
    "auth.staff_login": "Staff member logged in",
    "auth.staff_login_failed": "Failed login for a staff account",
    "auth.password_changed": "Staff member changed their password",
    "mfa.enabled": "Two-step verification turned on",
    "mfa.disabled": "Two-step verification turned off",
    "mfa.recovery_used": "A recovery code was used",
    "mfa.recovery_regenerated": "Recovery codes regenerated",
    "mfa.verify_failed": "A two-step verification code was rejected",
}
