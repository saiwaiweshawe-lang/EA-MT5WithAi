import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.ttl = self.config.get("ttl", 300)
        self.redis_url = self.config.get("redis_url", "redis://localhost:6379/0")
        self._client = None
        self._connected = False

    def _get_client(self):
        if self._client is None:
            try:
                import redis
                self._client = redis.from_url(self.redis_url)
                self._connected = True
                logger.info(f"Connected to Redis at {self.redis_url}")
            except ImportError:
                logger.warning("redis package not installed")
                self._connected = False
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                self._connected = False
        return self._client if self._connected else None

    def get(self, key: str) -> Optional[Any]:
        client = self._get_client()
        if not client:
            return None

        try:
            value = client.get(key)
            if value is None:
                return None

            logger.debug(f"Cache hit: {key}")
            return json.loads(value)

        except Exception as e:
            logger.error(f"Redis get failed for {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        client = self._get_client()
        if not client:
            return

        try:
            ttl_value = ttl or self.ttl
            serialized = json.dumps(value)
            client.setex(key, ttl_value, serialized)
            logger.debug(f"Cache set: {key} (ttl={ttl_value})")

        except Exception as e:
            logger.error(f"Redis set failed for {key}: {e}")

    def delete(self, key: str) -> bool:
        client = self._get_client()
        if not client:
            return False

        try:
            result = client.delete(key)
            return bool(result)

        except Exception as e:
            logger.error(f"Redis delete failed for {key}: {e}")
            return False

    def clear(self) -> None:
        client = self._get_client()
        if not client:
            return

        try:
            client.flushdb()
            logger.info("Redis cache cleared")

        except Exception as e:
            logger.error(f"Redis clear failed: {e}")

    def exists(self, key: str) -> bool:
        client = self._get_client()
        if not client:
            return False

        try:
            return bool(client.exists(key))

        except Exception as e:
            logger.error(f"Redis exists failed for {key}: {e}")
            return False

    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        client = self._get_client()
        if not client:
            return {}

        try:
            values = client.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = json.loads(value)
            return result

        except Exception as e:
            logger.error(f"Redis mget failed: {e}")
            return {}

    def set_many(self, items: Dict[str, Any], ttl: Optional[int] = None) -> None:
        client = self._get_client()
        if not client:
            return

        try:
            ttl_value = ttl or self.ttl
            pipe = client.pipeline()
            for key, value in items.items():
                serialized = json.dumps(value)
                pipe.setex(key, ttl_value, serialized)
            pipe.execute()

        except Exception as e:
            logger.error(f"Redis mset failed: {e}")

    def cleanup(self) -> int:
        logger.info("Redis TTL-based expiration is automatic")
        return 0

    def size(self) -> int:
        client = self._get_client()
        if not client:
            return 0

        try:
            return client.dbsize()

        except Exception as e:
            logger.error(f"Redis dbsize failed: {e}")
            return 0

    def keys(self, pattern: str = "*") -> List[str]:
        client = self._get_client()
        if not client:
            return []

        try:
            return [k.decode() if isinstance(k, bytes) else k 
                   for k in client.keys(pattern)]

        except Exception as e:
            logger.error(f"Redis keys failed: {e}")
            return []
