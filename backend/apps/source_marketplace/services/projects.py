"""Small helpers for creating and changing projects."""
import re

from django.utils.text import slugify

from apps.core.utils import unique_slug

from ..models import SourceProject, Technology

TECH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .+#/_-]{0,29}$")
MAX_TECHNOLOGIES = 12
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def make_slug(title, instance=None):
    """A unique slug that always contains a letter, so it can never be mistaken for a numeric id in a URL."""
    slug = unique_slug(SourceProject, title, instance=instance, fallback="project")
    if slug.isdigit():
        slug = unique_slug(SourceProject, f"project-{slug}", instance=instance, fallback="project")
    return slug


def valid_custom_slug(value):
    return bool(SLUG_RE.match(value)) and len(value) <= 90 and not value.isdigit()


def clean_technologies(values):
    """Deduplicated (case-insensitive) names. Returns (names, error_message_or_None)."""
    names, seen = [], set()
    for raw in values or []:
        name = re.sub(r"\s+", " ", str(raw or "")).strip()
        if not name:
            continue
        if not TECH_RE.match(name):
            return [], f"\"{name[:30]}\" is not a valid technology name (letters, numbers, spaces and . + # / _ - only)."
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    if len(names) > MAX_TECHNOLOGIES:
        return [], f"Use at most {MAX_TECHNOLOGIES} technologies."
    return names, None


def set_technologies(project, names):
    techs = []
    for name in names:
        slug = slugify(name.replace("+", " plus ").replace("#", " sharp "))[:40] or "tech"
        tech = Technology.objects.filter(slug=slug).first() or Technology.objects.create(name=name, slug=slug)
        techs.append(tech)
    project.technologies.set(techs)
