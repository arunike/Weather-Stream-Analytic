import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import redis
import psycopg2
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class HotPathConfig:
    max_latency_ms: int = 100  # Target latency
    batch_size: int = 1  # Process immediately
    enable_ml: bool = True  # Enable ML inference
    enable_complex_rules: bool = False  # Disable slow rules
    checkpoint_interval_ms: int = 5000

class HotPathProcessor:
    def __init__(
        self,
        redis_client: redis.Redis,
        postgres_conn: psycopg2.extensions.connection,
        config: Optional[HotPathConfig] = None
    ):
        self.redis = redis_client
        self.postgres = postgres_conn
        self.config = config or HotPathConfig()
        self.logger = logging.getLogger(__name__)
    
    def process_transaction(self, transaction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        from src.core.rules import HighAmountRule, ImpossibleTravelRule
        from src.core.state_manager import StateManager
        
        user_id = transaction['user_id']
        
        # Get user state from Redis
        state_manager = StateManager(self.redis, ttl_seconds=3600)
        last_location = state_manager.get_user_location(user_id)
        
        context = {"last_location": last_location}
        
        # Apply fast rules only
        rules = [
            HighAmountRule(threshold=2000.0),
            ImpossibleTravelRule(max_speed_kmh=800)
        ]
        
        for rule in rules:
            result = rule.evaluate(transaction, context)
            
            if result.is_fraud:
                # Immediate alert to hot storage
                alert = self._create_alert(transaction, result)
                self._store_alert_hot(alert)
                
                self.logger.warning(f"HOT PATH ALERT: {result.reason}")
                return alert
        
        # Update state
        new_state = {
            "lat": transaction['location']['lat'],
            "lon": transaction['location']['lon'],
            "timestamp": transaction['timestamp']
        }
        state_manager.save_user_location(user_id, new_state)
        
        return None
    
    def _create_alert(self, transaction: Dict[str, Any], result: Any) -> Dict[str, Any]:
        return {
            "transaction_id": transaction['transaction_id'],
            "user_id": transaction['user_id'],
            "reason": result.reason,
            "risk_score": result.risk_score,
            "rule_name": result.rule_name,
            "timestamp": datetime.now().timestamp(),
            "metadata": result.metadata
        }
    
    def _store_alert_hot(self, alert: Dict[str, Any]):
        cursor = self.postgres.cursor()
        cursor.execute("""
            INSERT INTO fraud_alerts 
            (transaction_id, user_id, reason, details, lat, lon)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            alert['transaction_id'],
            alert['user_id'],
            alert['reason'],
            str(alert['metadata']),
            alert['metadata'].get('lat', 0.0),
            alert['metadata'].get('lon', 0.0)
        ))
        self.postgres.commit()
    
    def get_metrics(self) -> Dict[str, Any]:
        return {
            "path": "hot",
            "max_latency_ms": self.config.max_latency_ms,
            "batch_size": self.config.batch_size
        }
