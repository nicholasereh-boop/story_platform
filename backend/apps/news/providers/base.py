"""The adapter interface. An adapter only PARSES what the netguard fetched; it never makes network calls itself, never follows links to
article pages and never scrapes (docs/SOURCE_AND_RIGHTS_POLICY.md). Whether an item may be published is decided later by the rights gate."""
from dataclasses import dataclass


@dataclass
class RawItem:
    external_id: str
    title: str
    canonical_url: str = ""
    standfirst: str = ""   # plain-text summary
    body: str = ""         # html from the feed's own full-text field, or "" when the feed only has a summary
    author: str = ""
    published_at: object = None
    language: str = ""


class AdapterError(ValueError):
    """The feed could not be understood. The message is safe to show to staff."""


class BaseAdapter:
    name = ""

    def parse(self, payload: bytes, source) -> list:
        raise NotImplementedError
