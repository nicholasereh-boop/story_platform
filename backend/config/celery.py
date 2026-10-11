"""Celery application. Redis is the broker (see CELERY_BROKER_URL in settings/base.py)."""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("config")
# Every setting that starts with CELERY_ is read from Django settings.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Periodic jobs (needs a running `celery -A config beat`).
app.conf.beat_schedule = {
    "publish-scheduled-stories": {"task": "apps.stories.tasks.publish_scheduled", "schedule": 60.0},
    # Analytics (Phase 9): keep today's numbers fresh, close yesterday/last week/last month, purge old raw events.
    "analytics-aggregate-today": {"task": "apps.analytics.tasks.aggregate_recent", "schedule": 15 * 60.0},
    "analytics-finalise-yesterday": {"task": "apps.analytics.tasks.aggregate_recent", "schedule": crontab(hour=0, minute=10)},
    "analytics-purge-old": {"task": "apps.analytics.tasks.purge_old", "schedule": crontab(hour=3, minute=30)},
    # Audit log retention (Phase 10): monthly, 04:15 UTC on the 1st.
    "audit-purge-old": {"task": "apps.audit.tasks.purge_old_entries", "schedule": crontab(day_of_month="1", hour=4, minute=15)},
}
