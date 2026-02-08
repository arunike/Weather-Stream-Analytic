import logging
from typing import Optional, Dict, Any
from pathlib import Path
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class CheckpointManager:
    def __init__(
        self,
        checkpoint_location: str,
        enable_wal: bool = True,
        checkpoint_interval_ms: int = 10000
    ):
        self.checkpoint_location = checkpoint_location
        self.enable_wal = enable_wal
        self.checkpoint_interval_ms = checkpoint_interval_ms
        self.logger = logging.getLogger(__name__)
    
    def get_checkpoint_config(self) -> Dict[str, Any]:
        config = {
            "spark.sql.streaming.checkpointLocation": self.checkpoint_location,
            "spark.sql.streaming.checkpointInterval": f"{self.checkpoint_interval_ms}ms"
        }
        
        if self.enable_wal:
            config["spark.streaming.receiver.writeAheadLog.enable"] = "true"
        
        return config
    
    def validate_checkpoint(self) -> bool:
        try:
            # For S3 paths
            if self.checkpoint_location.startswith("s3://"):
                # Would need boto3 to validate
                self.logger.info(f"S3 checkpoint location: {self.checkpoint_location}")
                return True
            
            # For local paths
            path = Path(self.checkpoint_location)
            path.mkdir(parents=True, exist_ok=True)
            
            # Write test file
            test_file = path / ".checkpoint_test"
            test_file.write_text("test")
            test_file.unlink()
            
            self.logger.info(f"Checkpoint location validated: {self.checkpoint_location}")
            return True
            
        except Exception as e:
            self.logger.error(f"Checkpoint validation failed: {e}")
            return False
    
    def get_recovery_metadata(self) -> Optional[Dict[str, Any]]:
        try:
            metadata_path = Path(self.checkpoint_location) / "metadata"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    return json.load(f)
            return None
        except Exception as e:
            self.logger.error(f"Failed to read recovery metadata: {e}")
            return None
    
    def save_recovery_metadata(self, metadata: Dict[str, Any]) -> bool:
        try:
            metadata_path = Path(self.checkpoint_location) / "metadata"
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to save recovery metadata: {e}")
            return False

class StateBackend:    
    def __init__(self, backend_type: str = "redis", config: Optional[Dict[str, Any]] = None):
        self.backend_type = backend_type
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
    
    def supports_transactions(self) -> bool:
        return self.backend_type in ["redis", "dynamodb"]
    
    def supports_ttl(self) -> bool:
        return self.backend_type in ["redis", "dynamodb"]
    
    def get_recommended_config(self) -> Dict[str, Any]:
        configs = {
            "redis": {
                "max_connections": 50,
                "connection_pool_size": 20,
                "socket_timeout": 5,
                "socket_connect_timeout": 5,
                "retry_on_timeout": True,
                "health_check_interval": 30
            },
            "rocksdb": {
                "write_buffer_size": 67108864,  # 64MB
                "max_write_buffer_number": 3,
                "target_file_size_base": 67108864,
                "compression": "snappy"
            },
            "dynamodb": {
                "read_capacity_units": 5,
                "write_capacity_units": 5,
                "billing_mode": "PAY_PER_REQUEST"
            }
        }
        
        return configs.get(self.backend_type, {})

class ExactlyOnceDelivery:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.logger = logging.getLogger(__name__)
        self.processed_key_prefix = "processed_txn"
        self.ttl_seconds = 86400  # 24 hours
    
    def is_processed(self, transaction_id: str) -> bool:
        try:
            key = f"{self.processed_key_prefix}:{transaction_id}"
            return self.redis.exists(key) > 0
        except Exception as e:
            self.logger.error(f"Failed to check processed status: {e}")
            return False
    
    def mark_processed(self, transaction_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        try:
            key = f"{self.processed_key_prefix}:{transaction_id}"
            value = {
                "processed_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            self.redis.set(key, json.dumps(value), ex=self.ttl_seconds)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to mark processed: {e}")
            return False
    
    def process_with_idempotency(
        self,
        transaction_id: str,
        process_func: callable,
        *args,
        **kwargs
    ) -> Any:
        if self.is_processed(transaction_id):
            self.logger.info(f"Transaction {transaction_id} already processed, skipping")
            return None
        
        try:
            result = process_func(*args, **kwargs)
            self.mark_processed(transaction_id, metadata={"status": "success"})
            return result
            
        except Exception as e:
            self.logger.error(f"Processing failed for {transaction_id}: {e}")
            self.mark_processed(transaction_id, metadata={"status": "failed", "error": str(e)})
            raise
