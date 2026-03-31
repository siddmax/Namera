"""Local SQLite cache for provider results."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from namera.providers.base import Availability, CheckType, ProviderResult

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "namera"
DEFAULT_CACHE_DB = DEFAULT_CACHE_DIR / "cache.db"

# TTLs per provider (seconds)
PROVIDER_TTLS: dict[str, int] = {
    "rdap": 3600,       # 1 hour
    "dns": 3600,        # 1 hour
    "whois": 21600,     # 6 hours
    "uspto": 86400,     # 24 hours
    "trademark-similarity": 86400,
    "social": 3600,     # 1 hour
}

DEFAULT_TTL = 3600


def _kwargs_hash(kwargs: dict) -> str:
    """Deterministic hash of kwargs for cache key."""
    serialized = json.dumps(kwargs, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def _serialize_result(result: ProviderResult) -> str:
    """Serialize ProviderResult to JSON string."""
    return json.dumps({
        "check_type": result.check_type.value,
        "provider_name": result.provider_name,
        "query": result.query,
        "available": result.available.value,
        "details": result.details,
        "error": result.error,
    })


def _deserialize_result(data: str) -> ProviderResult:
    """Deserialize JSON string to ProviderResult."""
    d = json.loads(data)
    return ProviderResult(
        check_type=CheckType(d["check_type"]),
        provider_name=d["provider_name"],
        query=d["query"],
        available=Availability(d["available"]),
        details=d.get("details", {}),
        error=d.get("error"),
    )


class ResultCache:
    """SQLite-backed cache for provider results."""

    def __init__(self, db_path: Path = DEFAULT_CACHE_DB):
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._ensure_schema()

    def _ensure_schema(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                provider TEXT NOT NULL,
                query TEXT NOT NULL,
                kwargs_hash TEXT NOT NULL,
                result TEXT NOT NULL,
                expires_at REAL NOT NULL,
                PRIMARY KEY (provider, query, kwargs_hash)
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires ON results(expires_at)
        """)
        self._conn.commit()

    def get(self, provider: str, query: str, kwargs: dict | None = None) -> ProviderResult | None:
        """Get a cached result. Returns None on miss or expiry."""
        kh = _kwargs_hash(kwargs or {})
        row = self._conn.execute(
            "SELECT result, expires_at FROM results WHERE provider=? AND query=? AND kwargs_hash=?",
            (provider, query, kh),
        ).fetchone()

        if row is None:
            return None

        result_str, expires_at = row
        if time.time() > expires_at:
            self._conn.execute(
                "DELETE FROM results WHERE provider=? AND query=? AND kwargs_hash=?",
                (provider, query, kh),
            )
            self._conn.commit()
            return None

        return _deserialize_result(result_str)

    def set(self, result: ProviderResult, kwargs: dict | None = None, ttl: int | None = None):
        """Cache a provider result."""
        if ttl is None:
            ttl = PROVIDER_TTLS.get(result.provider_name, DEFAULT_TTL)

        kh = _kwargs_hash(kwargs or {})
        expires_at = time.time() + ttl

        self._conn.execute(
            """INSERT OR REPLACE INTO results (provider, query, kwargs_hash, result, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (result.provider_name, result.query, kh, _serialize_result(result), expires_at),
        )
        self._conn.commit()

    def clear_expired(self) -> int:
        """Remove expired entries. Returns count of deleted rows."""
        cursor = self._conn.execute(
            "DELETE FROM results WHERE expires_at < ?", (time.time(),)
        )
        self._conn.commit()
        return cursor.rowcount

    def clear_all(self):
        """Remove all cached entries."""
        self._conn.execute("DELETE FROM results")
        self._conn.commit()

    def close(self):
        self._conn.close()


# Module-level singleton (lazy init)
_cache: ResultCache | None = None


def get_cache() -> ResultCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        _cache = ResultCache()
    return _cache
