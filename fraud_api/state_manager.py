import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from .cache.redis_client import get_redis_client

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 86400
DEFAULT_MAX_ITEMS = 50


class RedisStateManager:
    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.redis = get_redis_client()
        self.ttl_seconds = ttl_seconds

    def _key(self, user_id: str, namespace: str = "transactions") -> str:
        return f"fraud_state:{namespace}:{user_id}"

    def _global_key(self, namespace: str) -> str:
        return f"fraud_state:global:{namespace}"

    def add_transaction(
        self,
        user_id: str,
        transaction: Dict[str, Any],
        namespace: str = "transactions"
    ) -> None:
        key = self._key(user_id, namespace)
        payload = dict(transaction)
        payload.setdefault('timestamp', datetime.now(timezone.utc).timestamp())
        try:
            self.redis.lpush(key, json.dumps(payload))
            self.redis.ltrim(key, 0, DEFAULT_MAX_ITEMS - 1)
            self.redis.expire(key, self.ttl_seconds)
        except Exception as exc:
            logger.warning("Failed to cache transaction state: %s", exc)

    def add_global_transaction(self, namespace: str, payload: Dict[str, Any]) -> None:
        key = self._global_key(namespace)
        data = dict(payload)
        data.setdefault('timestamp', datetime.now(timezone.utc).timestamp())
        try:
            self.redis.lpush(key, json.dumps(data))
            self.redis.ltrim(key, 0, DEFAULT_MAX_ITEMS - 1)
            self.redis.expire(key, self.ttl_seconds)
        except Exception as exc:
            logger.warning("Failed to cache global state: %s", exc)

    def get_recent_transactions(
        self,
        user_id: str,
        limit: int = 20,
        namespace: str = "transactions"
    ) -> List[Dict[str, Any]]:
        key = self._key(user_id, namespace)
        return self._get_recent_items(key, limit)

    def get_global_recent(self, namespace: str, limit: int = 20) -> List[Dict[str, Any]]:
        key = self._global_key(namespace)
        return self._get_recent_items(key, limit)

    def get_list_length(self, key: str) -> int:
        try:
            return int(self.redis.llen(key))
        except Exception as exc:
            logger.warning("Failed to read list length: %s", exc)
            return 0

    def _get_recent_items(self, key: str, limit: int) -> List[Dict[str, Any]]:
        try:
            raw_items = self.redis.lrange(key, 0, max(0, limit - 1))
        except Exception as exc:
            logger.warning("Failed to read cached transactions: %s", exc)
            return []

        items: List[Dict[str, Any]] = []
        for raw_item in raw_items:
            try:
                items.append(json.loads(raw_item))
            except json.JSONDecodeError:
                continue
        return items
