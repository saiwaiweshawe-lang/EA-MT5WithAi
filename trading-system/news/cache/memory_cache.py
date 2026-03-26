import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryCache:
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.ttl = self.config.get("ttl", 300)
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None

        entry = self._cache[key]
        if self._is_expired(entry):
            del self._cache[key]
            return None

        logger.debug(f"Cache hit: {key}")
        return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expire_at = time.time() + (ttl or self.ttl)
        self._cache[key] = {
            "value": value,
            "expire_at": expire_at,
        }
        logger.debug(f"Cache set: {key} (ttl={ttl or self.ttl})")

    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        self._cache.clear()
        logger.info("Cache cleared")

    def exists(self, key: str) -> bool:
        if key not in self._cache:
            return False
        if self._is_expired(self._cache[key]):
            del self._cache[key]
            return False
        return True

    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result

    def set_many(self, items: Dict[str, Any], ttl: Optional[int] = None) -> None:
        for key, value in items.items():
            self.set(key, value, ttl)

    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        return time.time() > entry.get("expire_at", 0)

    def cleanup(self) -> int:
        expired_keys = [
            key for key, entry in self._cache.items()
            if self._is_expired(entry)
        ]
        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def size(self) -> int:
        return len(self._cache)

    def keys(self) -> List[str]:
        return list(self._cache.keys())
