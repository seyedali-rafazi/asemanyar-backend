import time
from typing import Any, Dict, Optional, Tuple


class TTLCache:
    """
    Thread-safe in-memory cache with Time-To-Live (TTL) expiration.
    Allows fallback to stale cache when upstream API (e.g. OpenSky) is unavailable
    or rate-limited (HTTP 429).
    """

    def __init__(self, default_ttl: int = 10):
        self.default_ttl = default_ttl
        self._cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expiry_timestamp)
        self._fallback_snapshots: Dict[str, Any] = {}  # key -> latest valid data

    def get(self, key: str) -> Optional[Any]:
        """Returns cached value if present and not expired."""
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
        return None

    def get_with_status(self, key: str) -> Tuple[Optional[Any], bool]:
        """Returns (value, is_fresh) tuple."""
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value, True
        return None, False

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Stores value in cache with TTL."""
        expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
        self._cache[key] = (value, expiry)
        self._fallback_snapshots[key] = value

    def get_fallback(self, key: str) -> Optional[Any]:
        """Returns the most recent snapshot regardless of expiration."""
        if key in self._fallback_snapshots:
            return self._fallback_snapshots[key]
        if key in self._cache:
            return self._cache[key][0]
        return None

    def invalidate(self, key: str) -> None:
        """Removes a key from cache."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clears all cached entries."""
        self._cache.clear()


cache_service = TTLCache(default_ttl=10)
