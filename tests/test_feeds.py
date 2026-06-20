import pytest

from tt_engine.feeds import EchoTikFeed, KalodataFeed, MockFeed, get_feed


def test_mock_feed_shapes():
    records = MockFeed().fetch(lookback_days=35)
    assert len(records) >= 5
    rec = records[0]
    assert len(rec.metrics) == 35
    # Metrics are sorted oldest → newest and carry every detection field.
    dates = [m.date for m in rec.metrics]
    assert dates == sorted(dates)
    m = rec.metrics[-1]
    for attr in ("units", "gmv", "price", "sellers", "promo_videos", "ads", "avg_ad_age"):
        assert getattr(m, attr) is not None
    assert rec.reviews  # the scalp massager carries a review corpus


def test_mock_feed_is_deterministic():
    a = MockFeed(seed=7).fetch()
    b = MockFeed(seed=7).fetch()
    assert [m.units for m in a[0].metrics] == [m.units for m in b[0].metrics]


def test_get_feed_resolves_mock():
    assert isinstance(get_feed("mock"), MockFeed)


def test_get_feed_unknown_raises():
    with pytest.raises(ValueError):
        get_feed("nope")


def test_vendor_feeds_fail_loud_without_keys():
    # Stubs must raise (never silently serve stale data) when unconfigured.
    with pytest.raises(RuntimeError):
        KalodataFeed(api_key="").fetch()
    with pytest.raises(RuntimeError):
        EchoTikFeed(api_key="").fetch()
