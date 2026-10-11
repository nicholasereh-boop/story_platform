from django.utils.text import slugify


def unique_slug(model, value, instance=None, field="slug", max_length=90, fallback="item"):
    """slugify(value), made unique for `model`: "my-story", "my-story-2", "my-story-3", ...

    Never returns an empty string (uses `fallback`) and never exceeds `max_length`.
    """
    base = slugify(value)[: max_length - 6].strip("-") or fallback
    slug, n = base, 2
    qs = model.objects.all()
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(**{field: slug}).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug
