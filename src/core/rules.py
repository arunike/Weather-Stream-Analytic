from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class FraudDetectionResult:
    is_fraud: bool
    reason: str
    risk_score: float  # 0.0 to 1.0
    rule_name: str
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_fraud": self.is_fraud,
            "reason": self.reason,
            "risk_score": self.risk_score,
            "rule_name": self.rule_name,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

class FraudRule(ABC):    
    def __init__(self, name: str, enabled: bool = True, priority: int = 0):
        self.name = name
        self.enabled = enabled
        self.priority = priority
    
    @abstractmethod
    def evaluate(self, transaction: Dict[str, Any], context: Dict[str, Any]) -> FraudDetectionResult:
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, enabled={self.enabled})"

class HighAmountRule(FraudRule):    
    def __init__(self, threshold: float = 2000.0, **kwargs):
        super().__init__(name="high_amount", **kwargs)
        self.threshold = threshold
    
    def evaluate(self, transaction: Dict[str, Any], context: Dict[str, Any]) -> FraudDetectionResult:
        amount = transaction.get("amount", 0.0)
        is_fraud = amount > self.threshold
        
        risk_score = min(amount / (self.threshold * 2), 1.0) if is_fraud else 0.0
        
        return FraudDetectionResult(
            is_fraud=is_fraud,
            reason=f"High Value Transaction: ${amount:.2f}" if is_fraud else "",
            risk_score=risk_score,
            rule_name=self.name,
            metadata={"amount": amount, "threshold": self.threshold}
        )

class ImpossibleTravelRule(FraudRule):    
    def __init__(self, max_speed_kmh: float = 800.0, min_distance_km: float = 50.0, **kwargs):
        super().__init__(name="impossible_travel", **kwargs)
        self.max_speed_kmh = max_speed_kmh
        self.min_distance_km = min_distance_km
    
    def evaluate(self, transaction: Dict[str, Any], context: Dict[str, Any]) -> FraudDetectionResult:
        last_location = context.get("last_location")
        
        if not last_location:
            return FraudDetectionResult(
                is_fraud=False,
                reason="",
                risk_score=0.0,
                rule_name=self.name
            )
        
        current_loc = transaction.get("location", {})
        current_lat = current_loc.get("lat", 0.0)
        current_lon = current_loc.get("lon", 0.0)
        current_ts = transaction.get("timestamp", 0.0)
        
        last_lat = last_location.get("lat", 0.0)
        last_lon = last_location.get("lon", 0.0)
        last_ts = last_location.get("timestamp", 0.0)
        
        distance_km = self._haversine(last_lat, last_lon, current_lat, current_lon)
        time_diff_hours = (current_ts - last_ts) / 3600.0
        
        if time_diff_hours <= 0:
            return FraudDetectionResult(is_fraud=False, reason="", risk_score=0.0, rule_name=self.name)
        
        speed_kmh = distance_km / time_diff_hours
        is_fraud = speed_kmh > self.max_speed_kmh and distance_km > self.min_distance_km
        
        risk_score = min(speed_kmh / (self.max_speed_kmh * 2), 1.0) if is_fraud else 0.0
        
        return FraudDetectionResult(
            is_fraud=is_fraud,
            reason=f"Impossible Travel: {speed_kmh:.2f} km/h over {distance_km:.2f} km" if is_fraud else "",
            risk_score=risk_score,
            rule_name=self.name,
            metadata={
                "speed_kmh": speed_kmh,
                "distance_km": distance_km,
                "time_hours": time_diff_hours
            }
        )
    
    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        import math
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

class MLAnomalyRule(FraudRule):    
    def __init__(self, model_path: str, threshold: float = 0.0, **kwargs):
        super().__init__(name="ml_anomaly", **kwargs)
        self.model_path = model_path
        self.threshold = threshold
        self.model = None
        self._load_model()
    
    def _load_model(self):
        try:
            import joblib
            import os
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                logger.info(f"Loaded ML model from {self.model_path}")
            else:
                logger.warning(f"Model not found at {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
    
    def evaluate(self, transaction: Dict[str, Any], context: Dict[str, Any]) -> FraudDetectionResult:
        if not self.model:
            return FraudDetectionResult(is_fraud=False, reason="", risk_score=0.0, rule_name=self.name)
        
        try:
            import numpy as np
            
            amount = transaction.get("amount", 0.0)
            location = transaction.get("location", {})
            lat = location.get("lat", 0.0)
            lon = location.get("lon", 0.0)
            
            features = np.array([[amount, lat, lon]])
            prediction = self.model.predict(features)[0]
            score = self.model.decision_function(features)[0]
            
            is_fraud = prediction == -1 and score < self.threshold
            risk_score = abs(min(score, 0) / 10.0)  # Normalize to 0-1
            
            return FraudDetectionResult(
                is_fraud=is_fraud,
                reason=f"ML Anomaly Detected: score={score:.3f}" if is_fraud else "",
                risk_score=risk_score,
                rule_name=self.name,
                metadata={"ml_score": float(score), "prediction": int(prediction)}
            )
        except Exception as e:
            logger.error(f"ML evaluation error: {e}")
            return FraudDetectionResult(is_fraud=False, reason="", risk_score=0.0, rule_name=self.name)

class FrequencyRule(FraudRule):    
    def __init__(self, max_transactions_per_hour: int = 10, **kwargs):
        super().__init__(name="high_frequency", **kwargs)
        self.max_transactions_per_hour = max_transactions_per_hour
    
    def evaluate(self, transaction: Dict[str, Any], context: Dict[str, Any]) -> FraudDetectionResult:
        user_history = context.get("user_history", [])
        current_ts = transaction.get("timestamp", 0.0)
        
        # Count recent transactions (last hour)
        recent_count = sum(1 for ts in user_history if current_ts - ts < 3600)
        
        is_fraud = recent_count > self.max_transactions_per_hour
        risk_score = min(recent_count / (self.max_transactions_per_hour * 2), 1.0) if is_fraud else 0.0
        
        return FraudDetectionResult(
            is_fraud=is_fraud,
            reason=f"High Frequency: {recent_count} transactions in 1 hour" if is_fraud else "",
            risk_score=risk_score,
            rule_name=self.name,
            metadata={"transaction_count": recent_count, "time_window_hours": 1}
        )

class FraudRuleEngine:
    def __init__(self):
        self.rules: List[FraudRule] = []
        self.logger = logging.getLogger(__name__)
    
    def add_rule(self, rule: FraudRule) -> None:
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        self.logger.info(f"Added rule: {rule}")
    
    def remove_rule(self, rule_name: str) -> bool:
        initial_count = len(self.rules)
        self.rules = [r for r in self.rules if r.name != rule_name]
        removed = len(self.rules) < initial_count
        if removed:
            self.logger.info(f"Removed rule: {rule_name}")
        return removed
    
    def enable_rule(self, rule_name: str) -> bool:
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = True
                self.logger.info(f"Enabled rule: {rule_name}")
                return True
        return False
    
    def disable_rule(self, rule_name: str) -> bool:
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = False
                self.logger.info(f"Disabled rule: {rule_name}")
                return True
        return False
    
    def evaluate_transaction(
        self,
        transaction: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[FraudDetectionResult]:
        results = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            try:
                result = rule.evaluate(transaction, context)
                if result.is_fraud:
                    results.append(result)
                    self.logger.warning(
                        f"Fraud detected by {rule.name}: {result.reason} "
                        f"(risk_score={result.risk_score:.2f})"
                    )
            except Exception as e:
                self.logger.error(f"Error evaluating rule {rule.name}: {e}", exc_info=True)
        
        return results
    
    def get_aggregated_risk_score(
        self,
        transaction: Dict[str, Any],
        context: Dict[str, Any]
    ) -> float:
        results = self.evaluate_transaction(transaction, context)
        if not results:
            return 0.0
        
        # Max risk score approach
        return max(r.risk_score for r in results)
    
    def list_rules(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": rule.name,
                "enabled": rule.enabled,
                "priority": rule.priority,
                "type": rule.__class__.__name__
            }
            for rule in self.rules
        ]
