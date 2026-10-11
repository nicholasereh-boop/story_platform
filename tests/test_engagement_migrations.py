"""Guard: the hand-written Phase 8 migrations must match the models (no model change is missing a migration)."""
import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_comments_reactions_analytics_migrations_match_models():
    # --check exits with an error (SystemExit) when makemigrations would create a new migration.
    call_command("makemigrations", "comments", "reactions", "analytics", "--check", "--dry-run", verbosity=0)
