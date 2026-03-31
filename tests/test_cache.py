"""Tests for the local SQLite cache."""

import time

from namera.cache import ResultCache
from namera.providers.base import Availability, CheckType, ProviderResult


def _make_result(provider="dns", query="test.com"):
    return ProviderResult(
        check_type=CheckType.DOMAIN,
        provider_name=provider,
        query=query,
        available=Availability.AVAILABLE,
        details={"domains": [{"domain": query, "available": "available"}]},
    )


class TestResultCache:
    def test_set_and_get(self, tmp_path):
        cache = ResultCache(db_path=tmp_path / "test.db")
        result = _make_result()
        cache.set(result, ttl=3600)
        cached = cache.get("dns", "test.com")
        assert cached is not None
        assert cached.available == Availability.AVAILABLE
        assert cached.provider_name == "dns"
        cache.close()

    def test_miss_returns_none(self, tmp_path):
        cache = ResultCache(db_path=tmp_path / "test.db")
        assert cache.get("dns", "nonexistent.com") is None
        cache.close()

    def test_expired_returns_none(self, tmp_path):
        cache = ResultCache(db_path=tmp_path / "test.db")
        result = _make_result()
        cache.set(result, ttl=0)
        time.sleep(0.01)
        assert cache.get("dns", "test.com") is None
        cache.close()

    def test_kwargs_differentiate(self, tmp_path):
        cache = ResultCache(db_path=tmp_path / "test.db")
        r1 = _make_result(query="test.com")
        r2 = _make_result(query="test.com")
        r2.available = Availability.TAKEN

        cache.set(r1, kwargs={"tlds": ["com"]}, ttl=3600)
        cache.set(r2, kwargs={"tlds": ["com", "io"]}, ttl=3600)

        c1 = cache.get("dns", "test.com", kwargs={"tlds": ["com"]})
        c2 = cache.get("dns", "test.com", kwargs={"tlds": ["com", "io"]})
        assert c1.available == Availability.AVAILABLE
        assert c2.available == Availability.TAKEN
        cache.close()

    def test_clear_expired(self, tmp_path):
        cache = ResultCache(db_path=tmp_path / "test.db")
        cache.set(_make_result(query="old.com"), ttl=0)
        cache.set(_make_result(query="new.com"), ttl=3600)
        time.sleep(0.01)
        deleted = cache.clear_expired()
        assert deleted == 1
        assert cache.get("dns", "new.com") is not None
        cache.close()

    def test_clear_all(self, tmp_path):
        cache = ResultCache(db_path=tmp_path / "test.db")
        cache.set(_make_result(query="a.com"), ttl=3600)
        cache.set(_make_result(query="b.com"), ttl=3600)
        cache.clear_all()
        assert cache.get("dns", "a.com") is None
        assert cache.get("dns", "b.com") is None
        cache.close()
