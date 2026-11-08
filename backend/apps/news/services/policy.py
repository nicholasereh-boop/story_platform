"""Publishers that must stay unapproved for full-text republication until written permission is on file
(docs/SOURCE_AND_RIGHTS_POLICY.md: "Conventional publishers"). rights.approve_record checks this list; adding a name here
is the safe direction (more caution)."""
from urllib.parse import urlsplit

DENYLIST_HOSTS = (
    "bbc.com", "bbc.co.uk", "cnn.com", "vanguardngr.com", "reuters.com", "reutersagency.com", "apnews.com", "ap.org",
    "espn.com", "skysports.com", "goal.com", "nytimes.com", "theguardian.com", "washingtonpost.com", "aljazeera.com",
)
PERMISSION_BASES = ("written_permission", "syndication_agreement")


def host_of(url):
    host = (urlsplit(str(url or "")).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_denylisted(url):
    host = host_of(url)
    return any(host == d or host.endswith("." + d) for d in DENYLIST_HOSTS)


def source_is_denylisted(source):
    return any(is_denylisted(u) for u in (source.website_url, source.feed_url, source.terms_url))
