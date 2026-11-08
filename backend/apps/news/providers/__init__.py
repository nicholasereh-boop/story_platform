"""Registered adapters. Adding one here is not enough to use it: a source must also be approved with a rights record."""
from .base import AdapterError, BaseAdapter, RawItem
from .rss import RssAdapter

ADAPTERS = {"rss": RssAdapter}


def get_adapter(name):
    cls = ADAPTERS.get(name)
    return cls() if cls else None


__all__ = ["ADAPTERS", "AdapterError", "BaseAdapter", "RawItem", "get_adapter"]
