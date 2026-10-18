"""Welcome email at sign-up and the automatic "new story" email to every member."""
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.accounts.services import get_profile
from apps.stories import notifications
from apps.stories.models import Story
from apps.stories.notifications import send_new_story_emails
from apps.stories.services import publish_due

from .engagement_helpers import make_story, make_user

pytestmark = pytest.mark.django_db


def fresh_story():
    story = make_story(status="draft", title="Moonlight")
    story.status = "published"
    story.published_at = timezone.now()
    story.save()
    return story


def test_every_active_member_gets_the_story_once():
    make_user("a@example.com")
    make_user("b@example.com")
    gone = make_user("gone@example.com")
    gone.is_active = False
    gone.save()
    story = fresh_story()
    assert send_new_story_emails(story.pk) == 2
    assert sorted(m.to[0] for m in mail.outbox) == ["a@example.com", "b@example.com"]
    assert all(len(m.to) == 1 and "Moonlight" in m.subject and f"/stories/{story.slug}" in m.body for m in mail.outbox)
    assert send_new_story_emails(story.pk) == 0  # never twice
    assert len(mail.outbox) == 2


def test_a_member_can_turn_the_emails_off():
    quiet = make_user("quiet@example.com")
    profile = get_profile(quiet)
    profile.email_new_stories = False
    profile.save()
    make_user("loud@example.com")
    assert send_new_story_emails(fresh_story().pk) == 1
    assert mail.outbox[0].to == ["loud@example.com"]


def test_drafts_are_not_emailed():
    make_user("a@example.com")
    story = make_story(status="draft")
    assert send_new_story_emails(story.pk) == 0 and mail.outbox == []


def test_scheduled_story_is_queued_when_it_goes_live(monkeypatch):
    queued = []
    monkeypatch.setattr("apps.stories.services.queue_new_story_email", queued.append)
    story = make_story(status="draft")
    Story.objects.filter(pk=story.pk).update(status="scheduled", scheduled_at=timezone.now() - timedelta(minutes=1))
    assert publish_due() == 1
    assert queued == [story.pk]
    assert publish_due() == 0 and queued == [story.pk]


def test_queueing_never_breaks_publishing(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("broker down")

    monkeypatch.setattr("apps.stories.tasks.notify_new_story.delay", boom)
    notifications.queue_new_story_email(1)  # must not raise
