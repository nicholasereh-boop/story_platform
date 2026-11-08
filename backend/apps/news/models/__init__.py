"""News models. Isolated from Stories, Academy and Marketplace on purpose (docs: News roadmap, rule 1): nothing here changes them."""
from .article import NewsArticle, NewsAsset, NewsCategory, NewsRevision, NewsViewCount
from .comment import NewsComment
from .ingest import NewsIngestionRun
from .takedown import NewsTakedown
from .source import NewsRightsRecord, NewsSource

__all__ = ["NewsArticle", "NewsAsset", "NewsCategory", "NewsComment", "NewsIngestionRun", "NewsRevision", "NewsRightsRecord", "NewsSource", "NewsTakedown", "NewsViewCount"]
