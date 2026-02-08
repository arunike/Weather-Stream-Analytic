import json
import logging
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import redis

logger = logging.getLogger(__name__)

@dataclass
class StateEntry:
    user_id: int
    lat: float
    lon: float
    timestamp: float
    version: int = 1
    metadata: Dict[str, Any] = None
    
    def to_json(self) -> str:
        data = asdict(self)
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'StateEntry':
        data = json.loads(json_str)
        return cls(**data)

class StateManager:
    def __init__(
        self,
        redis_client: redis.Redis,
        ttl_seconds: int = 86400,  # 24 hours default
        enable_versioning: bool = False,
        key_prefix: str = "fraud_state"
    ):
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
        self.enable_versioning = enable_versioning
        self.key_prefix = key_prefix
        self.logger = logging.getLogger(__name__)
    
    def _make_key(self, user_id: int, suffix: str = "location") -> str:
        return f"{self.key_prefix}:{suffix}:{user_id}"
    
    def save_user_location(
        self,
        user_id: int,
        state: Dict[str, Any],
        version: Optional[int] = None
    ) -> bool:
        try:
            key = self._make_key(user_id)
            
            if self.enable_versioning and version:
                # Save versioned state
                versioned_key = f"{key}:v{version}"
                self.redis.set(versioned_key, json.dumps(state), ex=self.ttl_seconds)
                
                # Update version pointer
                self.redis.set(f"{key}:current_version", version)
            
            # Always save current state
            self.redis.set(key, json.dumps(state), ex=self.ttl_seconds)
            
            self.logger.debug(f"Saved state for user {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save state for user {user_id}: {e}")
            return False
    
    def get_user_location(self, user_id: int, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        try:
            if self.enable_versioning and version:
                key = f"{self._make_key(user_id)}:v{version}"
            else:
                key = self._make_key(user_id)
            
            data = self.redis.get(key)
            
            if data:
                return json.loads(data)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get state for user {user_id}: {e}")
            return None
    
    def get_user_locations_batch(self, user_ids: List[int]) -> List[Optional[Dict[str, Any]]]:
        try:
            keys = [self._make_key(uid) for uid in user_ids]
            values = self.redis.mget(keys)
            
            results = []
            for val in values:
                if val:
                    results.append(json.loads(val))
                else:
                    results.append(None)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Batch get failed: {e}")
            return [None] * len(user_ids)
    
    def delete_user_state(self, user_id: int) -> bool:
        try:
            key = self._make_key(user_id)
            self.redis.delete(key)
            
            if self.enable_versioning:
                # Delete all versions
                pattern = f"{key}:v*"
                for k in self.redis.scan_iter(match=pattern):
                    self.redis.delete(k)
                self.redis.delete(f"{key}:current_version")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete state for user {user_id}: {e}")
            return False
    
    def get_current_version(self, user_id: int) -> Optional[int]:
        if not self.enable_versioning:
            return None
        
        try:
            key = f"{self._make_key(user_id)}:current_version"
            version = self.redis.get(key)
            return int(version) if version else None
        except Exception as e:
            self.logger.error(f"Failed to get version for user {user_id}: {e}")
            return None
    
    def increment_transaction_count(self, user_id: int, window_seconds: int = 3600) -> int:
        try:
            key = f"{self.key_prefix}:txn_count:{user_id}"
            current_time = datetime.now().timestamp()
            
            # Use sorted set with scores as timestamps
            self.redis.zadd(key, {str(current_time): current_time})
            
            # Remove old entries
            cutoff = current_time - window_seconds
            self.redis.zremrangebyscore(key, 0, cutoff)
            
            # Set TTL on the key
            self.redis.expire(key, window_seconds)
            
            # Get count
            count = self.redis.zcard(key)
            return count
            
        except Exception as e:
            self.logger.error(f"Failed to increment count for user {user_id}: {e}")
            return 0
    
    def get_transaction_count(self, user_id: int, window_seconds: int = 3600) -> int:
        try:
            key = f"{self.key_prefix}:txn_count:{user_id}"
            current_time = datetime.now().timestamp()
            cutoff = current_time - window_seconds
            
            # Count entries within window
            count = self.redis.zcount(key, cutoff, current_time)
            return count
            
        except Exception as e:
            self.logger.error(f"Failed to get count for user {user_id}: {e}")
            return 0
    
    def health_check(self) -> bool:
        try:
            self.redis.ping()
            return True
        except Exception as e:
            self.logger.error(f"Redis health check failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        try:
            info = self.redis.info()
            return {
                "connected": True,
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_keys": self.redis.dbsize(),
                "ttl_seconds": self.ttl_seconds,
                "versioning_enabled": self.enable_versioning
            }
        except Exception as e:
            self.logger.error(f"Failed to get stats: {e}")
            return {"connected": False, "error": str(e)}
