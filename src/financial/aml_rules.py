from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class AMLRiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AMLAlert:
    is_suspicious: bool
    risk_level: AMLRiskLevel
    rule_name: str
    confidence: float
    reason: str
    recommended_action: str
    metadata: Dict
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

class AMLRule(ABC):
    def __init__(self, enabled: bool = True, priority: int = 0):
        self.enabled = enabled
        self.priority = priority
        self.name = self.__class__.__name__
    
    @abstractmethod
    def evaluate(self, transaction: Dict, context: Dict) -> AMLAlert:
        pass


class StructuringRule(AMLRule):
    def __init__(
        self,
        threshold: float = 10000.0,
        time_window_hours: int = 24,
        min_transactions: int = 3,
        cumulative_ratio: float = 0.9,
        enabled: bool = True,
        priority: int = 10
    ):
        super().__init__(enabled, priority)
        self.threshold = threshold
        self.time_window_hours = time_window_hours
        self.min_transactions = min_transactions
        self.cumulative_ratio = cumulative_ratio
    
    def evaluate(self, transaction: Dict, context: Dict) -> AMLAlert:
        user_id = transaction.get('user_id')
        amount = transaction.get('amount', 0)
        
        # Get historical transactions within time window
        recent_txns = context.get('recent_transactions', [])
        cutoff_time = datetime.utcnow() - timedelta(hours=self.time_window_hours)
        
        window_txns = [
            txn for txn in recent_txns
            if txn.get('timestamp') >= cutoff_time
            and txn.get('user_id') == user_id
        ]
        
        # Include current transaction
        window_txns.append(transaction)
        
        # Calculate statistics
        num_transactions = len(window_txns)
        total_amount = sum(txn.get('amount', 0) for txn in window_txns)
        avg_amount = total_amount / num_transactions if num_transactions > 0 else 0
        
        # Check if all transactions are below threshold
        all_below_threshold = all(
            txn.get('amount', 0) < self.threshold 
            for txn in window_txns
        )
        
        # Check if cumulative amount is close to multiples of threshold
        cumulative_suspicious = (
            total_amount > self.threshold * self.cumulative_ratio and
            total_amount < self.threshold * (self.min_transactions + 1)
        )
        
        # Check transaction amount consistency (potential intentional splitting)
        amounts = [txn.get('amount', 0) for txn in window_txns]
        amount_variance = self._calculate_variance(amounts)
        low_variance = amount_variance < (avg_amount * 0.3)  # Highly similar amounts
        
        is_suspicious = (
            num_transactions >= self.min_transactions and
            all_below_threshold and
            cumulative_suspicious and
            low_variance
        )
        
        if is_suspicious:
            confidence = min(0.95, 0.6 + (num_transactions * 0.05))
            
            return AMLAlert(
                is_suspicious=True,
                risk_level=AMLRiskLevel.HIGH,
                rule_name=self.name,
                confidence=confidence,
                reason=(
                    f"Structuring detected: {num_transactions} transactions "
                    f"totaling ${total_amount:.2f} in {self.time_window_hours}h, "
                    f"all below ${self.threshold} threshold"
                ),
                recommended_action="File SAR (Suspicious Activity Report)",
                metadata={
                    'num_transactions': num_transactions,
                    'total_amount': total_amount,
                    'avg_amount': avg_amount,
                    'time_window_hours': self.time_window_hours,
                    'transaction_ids': [txn.get('transaction_id') for txn in window_txns]
                }
            )
        
        return AMLAlert(
            is_suspicious=False,
            risk_level=AMLRiskLevel.LOW,
            rule_name=self.name,
            confidence=0.0,
            reason="No structuring pattern detected",
            recommended_action="Continue monitoring",
            metadata={}
        )
    
    @staticmethod
    def _calculate_variance(values: List[float]) -> float:
        if len(values) <= 1:
            return 0.0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)


class RapidMovementRule(AMLRule):
    def __init__(
        self,
        max_hops: int = 3,
        time_window_hours: int = 6,
        min_amount: float = 5000.0,
        enabled: bool = True,
        priority: int = 9
    ):
        super().__init__(enabled, priority)
        self.max_hops = max_hops
        self.time_window_hours = time_window_hours
        self.min_amount = min_amount
    
    def evaluate(self, transaction: Dict, context: Dict) -> AMLAlert:
        amount = transaction.get('amount', 0)
        
        if amount < self.min_amount:
            return self._no_alert()
        
        # Track fund flow
        transaction_chain = context.get('transaction_chain', [])
        source_account = transaction.get('from_account')
        dest_account = transaction.get('to_account')
        
        # Find fund source chain
        chain_length = self._trace_fund_flow(
            dest_account, 
            transaction_chain,
            self.time_window_hours
        )
        
        if chain_length >= self.max_hops:
            confidence = min(0.9, 0.5 + (chain_length * 0.1))
            
            return AMLAlert(
                is_suspicious=True,
                risk_level=AMLRiskLevel.HIGH,
                rule_name=self.name,
                confidence=confidence,
                reason=(
                    f"Rapid fund movement detected: ${amount:.2f} moved through "
                    f"{chain_length} accounts in {self.time_window_hours} hours"
                ),
                recommended_action="Investigate transaction chain, possible layering",
                metadata={
                    'chain_length': chain_length,
                    'amount': amount,
                    'source_account': source_account,
                    'dest_account': dest_account
                }
            )
        
        return self._no_alert()
    
    def _trace_fund_flow(
        self, 
        account_id: str, 
        chain: List[Dict],
        time_window_hours: int
    ) -> int:
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        # Simplified implementation: calculate transaction depth for this account
        hops = 0
        current_account = account_id
        visited = set()
        
        for _ in range(10):  # Max 10 hops
            if current_account in visited:
                break
            visited.add(current_account)
            
            # Find transactions flowing into this account
            incoming_txn = next(
                (txn for txn in chain 
                 if txn.get('to_account') == current_account
                 and txn.get('timestamp') >= cutoff_time),
                None
            )
            
            if incoming_txn:
                hops += 1
                current_account = incoming_txn.get('from_account')
            else:
                break
        
        return hops
    
    def _no_alert(self) -> AMLAlert:
        return AMLAlert(
            is_suspicious=False,
            risk_level=AMLRiskLevel.LOW,
            rule_name=self.name,
            confidence=0.0,
            reason="No rapid movement detected",
            recommended_action="Continue monitoring",
            metadata={}
        )

class HighRiskJurisdictionRule(AMLRule):
    # FATF high-risk and monitored countries (2026 example)
    HIGH_RISK_COUNTRIES = {
        'KP', 'IR',  # North Korea, Iran
    }
    
    MONITORED_COUNTRIES = {
        'AF', 'MM', 'PK', 'SY', 'YE',  # Monitoring list
    }
    
    def __init__(
        self,
        min_amount: float = 1000.0,
        enabled: bool = True,
        priority: int = 8
    ):
        super().__init__(enabled, priority)
        self.min_amount = min_amount
    
    def evaluate(self, transaction: Dict, context: Dict) -> AMLAlert:
        amount = transaction.get('amount', 0)
        sender_country = transaction.get('sender_country', '').upper()
        receiver_country = transaction.get('receiver_country', '').upper()
        
        # Check high-risk countries
        high_risk_involved = (
            sender_country in self.HIGH_RISK_COUNTRIES or
            receiver_country in self.HIGH_RISK_COUNTRIES
        )
        
        # Check monitored countries
        monitored_involved = (
            sender_country in self.MONITORED_COUNTRIES or
            receiver_country in self.MONITORED_COUNTRIES
        )
        
        if high_risk_involved and amount >= self.min_amount:
            return AMLAlert(
                is_suspicious=True,
                risk_level=AMLRiskLevel.CRITICAL,
                rule_name=self.name,
                confidence=0.95,
                reason=(
                    f"Transaction involving high-risk jurisdiction: "
                    f"{sender_country} -> {receiver_country}, ${amount:.2f}"
                ),
                recommended_action="Enhanced Due Diligence (EDD) required, possible sanctions check",
                metadata={
                    'sender_country': sender_country,
                    'receiver_country': receiver_country,
                    'amount': amount,
                    'risk_category': 'HIGH_RISK_JURISDICTION'
                }
            )
        
        if monitored_involved and amount >= self.min_amount * 5:
            return AMLAlert(
                is_suspicious=True,
                risk_level=AMLRiskLevel.MEDIUM,
                rule_name=self.name,
                confidence=0.7,
                reason=(
                    f"Large transaction involving monitored jurisdiction: "
                    f"{sender_country} -> {receiver_country}, ${amount:.2f}"
                ),
                recommended_action="Enhanced monitoring and documentation required",
                metadata={
                    'sender_country': sender_country,
                    'receiver_country': receiver_country,
                    'amount': amount,
                    'risk_category': 'MONITORED_JURISDICTION'
                }
            )
        
        return AMLAlert(
            is_suspicious=False,
            risk_level=AMLRiskLevel.LOW,
            rule_name=self.name,
            confidence=0.0,
            reason="No high-risk jurisdiction involvement",
            recommended_action="Continue monitoring",
            metadata={}
        )


class UnusualPatternRule(AMLRule):
    def __init__(
        self,
        deviation_threshold: float = 3.0,  # Standard deviation multiplier
        min_history: int = 10,  # Minimum number of historical transactions
        enabled: bool = True,
        priority: int = 7
    ):
        super().__init__(enabled, priority)
        self.deviation_threshold = deviation_threshold
        self.min_history = min_history
    
    def evaluate(self, transaction: Dict, context: Dict) -> AMLAlert:
        user_id = transaction.get('user_id')
        amount = transaction.get('amount', 0)
        
        # Get user historical transactions
        user_profile = context.get('user_profile', {})
        historical_txns = user_profile.get('historical_transactions', [])
        
        if len(historical_txns) < self.min_history:
            return AMLAlert(
                is_suspicious=False,
                risk_level=AMLRiskLevel.LOW,
                rule_name=self.name,
                confidence=0.0,
                reason="Insufficient historical data",
                recommended_action="Build user profile",
                metadata={'history_count': len(historical_txns)}
            )
        
        # Calculate historical statistics
        amounts = [txn.get('amount', 0) for txn in historical_txns]
        mean_amount = sum(amounts) / len(amounts)
        std_amount = self._calculate_std(amounts, mean_amount)
        
        # Calculate deviation of current transaction
        if std_amount > 0:
            z_score = abs(amount - mean_amount) / std_amount
        else:
            z_score = 0
        
        # Check if unusual
        is_unusual = z_score > self.deviation_threshold
        
        # Check if transaction time is unusual
        typical_hour = user_profile.get('typical_transaction_hour', 12)
        current_hour = datetime.utcnow().hour
        unusual_time = abs(current_hour - typical_hour) > 6
        
        # Check if transaction type is unusual
        typical_merchant = user_profile.get('frequent_merchants', [])
        current_merchant = transaction.get('merchant_id')
        unusual_merchant = (
            len(typical_merchant) > 0 and 
            current_merchant not in typical_merchant
        )
        
        anomaly_score = 0
        if is_unusual:
            anomaly_score += 0.5
        if unusual_time:
            anomaly_score += 0.2
        if unusual_merchant:
            anomaly_score += 0.3
        
        if anomaly_score >= 0.5:
            risk_level = (
                AMLRiskLevel.HIGH if anomaly_score >= 0.8 else
                AMLRiskLevel.MEDIUM
            )
            
            return AMLAlert(
                is_suspicious=True,
                risk_level=risk_level,
                rule_name=self.name,
                confidence=min(0.9, anomaly_score),
                reason=(
                    f"Unusual transaction pattern: amount ${amount:.2f} "
                    f"({z_score:.1f} std devs from mean ${mean_amount:.2f})"
                ),
                recommended_action="Customer verification recommended",
                metadata={
                    'z_score': z_score,
                    'mean_amount': mean_amount,
                    'std_amount': std_amount,
                    'unusual_time': unusual_time,
                    'unusual_merchant': unusual_merchant,
                    'anomaly_score': anomaly_score
                }
            )
        
        return AMLAlert(
            is_suspicious=False,
            risk_level=AMLRiskLevel.LOW,
            rule_name=self.name,
            confidence=0.0,
            reason="Transaction consistent with user profile",
            recommended_action="Continue monitoring",
            metadata={}
        )
    
    @staticmethod
    def _calculate_std(values: List[float], mean: float) -> float:
        if len(values) <= 1:
            return 0.0
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5


class AMLRuleEngine:
    def __init__(self):
        self.rules: List[AMLRule] = []
        logger.info("Initialized AML Rule Engine")
    
    def add_rule(self, rule: AMLRule):
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"Added rule: {rule.name} (priority: {rule.priority})")
    
    def evaluate_transaction(
        self, 
        transaction: Dict, 
        context: Dict
    ) -> List[AMLAlert]:
        alerts = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            try:
                alert = rule.evaluate(transaction, context)
                if alert.is_suspicious:
                    alerts.append(alert)
                    logger.warning(
                        f"AML Alert triggered: {rule.name} "
                        f"(confidence: {alert.confidence:.2f})"
                    )
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.name}: {str(e)}")
        
        return alerts
    
    def get_highest_risk_alert(
        self, 
        alerts: List[AMLAlert]
    ) -> Optional[AMLAlert]:
        if not alerts:
            return None
        
        risk_order = {
            AMLRiskLevel.CRITICAL: 4,
            AMLRiskLevel.HIGH: 3,
            AMLRiskLevel.MEDIUM: 2,
            AMLRiskLevel.LOW: 1
        }
        
        return max(
            alerts, 
            key=lambda a: (risk_order[a.risk_level], a.confidence)
        )
