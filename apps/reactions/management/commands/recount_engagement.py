from django.core.management.base import BaseCommand
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce

from apps.comments.models import Comment
from apps.reactions.models import Like
from apps.stories.models import Story


def _per_story(queryset):
    """Subquery: number of rows per story (NULL when there are none)."""
    return Subquery(queryset.filter(story=OuterRef("pk")).order_by().values("story").annotate(c=Count("pk")).values("c"))


class Command(BaseCommand):
    help = "Recompute Story.like_count and Story.comment_count from the real rows (repairs any drift). Safe to run any time."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report how many stories are wrong.")

    def handle(self, *args, **options):
        likes = Coalesce(_per_story(Like.objects.all()), 0)
        # Same rule as the live counter: approved comments, except replies whose parent is hidden.
        visible = Comment.objects.filter(Q(status=Comment.Status.APPROVED) & ~Q(parent__status=Comment.Status.HIDDEN))
        comments = Coalesce(_per_story(visible), 0)

        wrong = (
            Story.objects.annotate(real_likes=likes, real_comments=comments)
            .exclude(like_count=F("real_likes"), comment_count=F("real_comments"))
            .count()
        )
        if not options["dry_run"]:
            Story.objects.update(like_count=likes, comment_count=comments)  # update() does not touch updated_at
        verb = "would fix" if options["dry_run"] else "fixed"
        self.stdout.write(self.style.SUCCESS(f"Counters checked: {verb} {wrong} stor{'y' if wrong == 1 else 'ies'}."))
