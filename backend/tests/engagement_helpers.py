"""Shared helpers for the Phase 8 (likes and comments) tests."""
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.stories.models import Story

BASE = "/api/v1/"
PASSWORD = "Correct-horse-battery-9"


def make_story(title="A story", status="published", **extra):
    story = Story.objects.create(
        title=title,
        content_json={"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Body"}]}]},
        status=status,
        **extra,
    )
    if status == "published":
        story.published_at = timezone.now() - timedelta(days=1)
        story.save()
    return story


def make_user(email="reader@example.com", verified=True, staff=False):
    user = get_user_model().objects.create_user(email=email, password=PASSWORD, is_staff=staff)
    EmailAddress.objects.create(user=user, email=user.email, verified=verified, primary=True)
    return user


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def comments_url(story):
    return f"{BASE}stories/{story.slug}/comments/"


def post_comment(client, story, body="Nice story", **extra):
    return client.post(comments_url(story), {"body": body, **extra}, format="json")


def add_comment(story, user, body="hello", status="approved", parent=None):
    """Create a comment through the service layer so Story.comment_count stays correct."""
    from apps.comments import services

    comment = Comment.objects.create(story=story, user=user, body=body, status=Comment.Status.PENDING, parent=parent)
    services.set_status(comment, status)  # moves it to `status` and updates Story.comment_count
    comment.refresh_from_db()
    return comment


def list_comments(client, story, **params):
    return client.get(comments_url(story), params)


def ids(response):
    """Comment ids of a list response, top level only."""
    return [c["id"] for c in response.json()["data"]]


def reload_counts(story):
    story.refresh_from_db()
    return story.like_count, story.comment_count
