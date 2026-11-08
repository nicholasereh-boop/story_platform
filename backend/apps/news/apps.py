from django.apps import AppConfig


class NewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.news"
    verbose_name = "News"

    def ready(self):
        # Registers the handlers that quarantine live articles when rights end (services/articles.py, bottom of the file).
        from .services import articles  # noqa: F401
