"""Part 2 — Market Intelligence data feeds.

The feeds are the *rented* part of the stack (Part 0, truth #4): anyone can buy them,
so they are not the moat. They are swappable adapters behind one interface. Stack two
velocity sources (e.g. Kalodata + EchoTik) and cross-confirm a trigger before trusting it.
"""

from .base import DataFeed, FeedRecord
from .mock_feed import MockFeed
from .kalodata import KalodataFeed
from .echotik import EchoTikFeed

_REGISTRY = {
    "mock": MockFeed,
    "kalodata": KalodataFeed,
    "echotik": EchoTikFeed,
}


def get_feed(name: str) -> DataFeed:
    """Resolve a feed adapter by name (TT_PRIMARY_FEED)."""
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise ValueError(f"unknown feed '{name}'. options: {sorted(_REGISTRY)}")


__all__ = ["DataFeed", "FeedRecord", "MockFeed", "KalodataFeed", "EchoTikFeed", "get_feed"]
