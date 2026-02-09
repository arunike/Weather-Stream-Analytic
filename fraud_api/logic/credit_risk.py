from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum
from pathlib import Path
import logging
import math

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from .rule_engine import RuleEngine

logger = logging.getLogger(__name__)

class CreditDecision(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    MANUAL_REVIEW = "manual_review"
    CONDITIONAL_APPROVE = "conditional_approve"


class CreditRiskTier(Enum):
    EXCELLENT = "excellent"  # 750+
    GOOD = "good"  # 700-749
    FAIR = "fair"  # 650-699
    POOR = "poor"  # 600-649
    VERY_POOR = "very_poor"  # <600

@dataclass
class CreditScore:
    score: float  # 300-850 (FICO range)
    risk_tier: CreditRiskTier
    decision: CreditDecision
    confidence: float
    factors: Dict[str, float]  # Impact factors and weights
    recommended_limit: float  # Recommended credit limit
    recommended_apr: float  # Recommended annual percentage rate
    reason_codes: List[str]  # Rejection reason codes
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class CreditPolicyAlert:
    code: str
    message: str
    severity: str


class CreditPolicyRule:
    def __init__(self, enabled: bool = True, priority: int = 0):
        self.enabled = enabled
        self.priority = priority
        self.name = self.__class__.__name__

    def evaluate(self, application: Dict, context: Dict) -> Optional[CreditPolicyAlert]:
        raise NotImplementedError


class HighDtiRule(CreditPolicyRule):
    def __init__(self, threshold: float = 0.5, **kwargs):
        super().__init__(priority=10, **kwargs)
        self.threshold = threshold

    def evaluate(self, application: Dict, context: Dict) -> Optional[CreditPolicyAlert]:
        features = context.get('features', {})
        dti_ratio = features.get('debt_to_income_ratio', 0.0)
        if dti_ratio > self.threshold:
            return CreditPolicyAlert(
                code="HIGH_DTI_POLICY",
                message=f"Debt-to-income ratio {dti_ratio:.2f} exceeds policy",
                severity="high"
            )
        return None


class ThinFileRule(CreditPolicyRule):
    def __init__(self, min_history_months: int = 12, **kwargs):
        super().__init__(priority=8, **kwargs)
        self.min_history_months = min_history_months

    def evaluate(self, application: Dict, context: Dict) -> Optional[CreditPolicyAlert]:
        features = context.get('features', {})
        history_months = features.get('payment_history_length_months', 0)
        if history_months < self.min_history_months:
            return CreditPolicyAlert(
                code="THIN_FILE",
                message="Insufficient credit history",
                severity="medium"
            )
        return None


class DelinquencyRule(CreditPolicyRule):
    def __init__(self, min_delinquencies: int = 1, **kwargs):
        super().__init__(priority=7, **kwargs)
        self.min_delinquencies = min_delinquencies

    def evaluate(self, application: Dict, context: Dict) -> Optional[CreditPolicyAlert]:
        features = context.get('features', {})
        delinquencies = features.get('delinquency_count', 0)
        if delinquencies > self.min_delinquencies:
            return CreditPolicyAlert(
                code="DELINQUENCY_RISK",
                message="Multiple delinquencies on record",
                severity="high"
            )
        return None


class CreditMLAnomalyRule(CreditPolicyRule):
    def __init__(self, min_confidence: float = 0.25, **kwargs):
        super().__init__(priority=6, **kwargs)
        self.min_confidence = min_confidence
        self.model_path = (
            Path(__file__).resolve().parents[2] / 'ml_models' / 'credit_anomaly.joblib'
        )
        self.model = self._load_or_train()

    def evaluate(self, application: Dict, context: Dict) -> Optional[CreditPolicyAlert]:
        features = context.get('features', {})
        vector = self._extract_features(features)
        score = float(self.model.decision_function([vector])[0])
        is_anomaly = int(self.model.predict([vector])[0]) == -1
        confidence = min(1.0, abs(score))

        if not is_anomaly or confidence < self.min_confidence:
            return None

        severity = "high" if confidence >= 0.6 else "medium"
        return CreditPolicyAlert(
            code="ML_ANOMALY",
            message="ML anomaly detected in credit profile",
            severity=severity
        )

    def _load_or_train(self) -> IsolationForest:
        if self.model_path.exists():
            return joblib.load(self.model_path)

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        model = self._train_default_model()
        joblib.dump(model, self.model_path)
        return model

    @staticmethod
    def _train_default_model() -> IsolationForest:
        rng = np.random.default_rng(42)
        incomes = rng.normal(5000.0, 1500.0, 800)
        dti_ratios = rng.uniform(0.05, 0.55, 800)
        history_months = rng.integers(6, 120, 800)
        delinquencies = rng.integers(0, 3, 800)

        training_data = np.column_stack(
            [
                np.abs(incomes),
                dti_ratios,
                history_months.astype(float),
                delinquencies.astype(float)
            ]
        )

        model = IsolationForest(
            n_estimators=100,
            contamination=0.08,
            random_state=42
        )
        model.fit(training_data)
        return model

    @staticmethod
    def _extract_features(features: Dict) -> List[float]:
        monthly_income = float(features.get('monthly_income', 0.0))
        dti_ratio = float(features.get('debt_to_income_ratio', 0.0))
        history_months = float(features.get('payment_history_length_months', 0.0))
        delinquencies = float(features.get('delinquency_count', 0.0))

        return [monthly_income, dti_ratio, history_months, delinquencies]


class CreditPolicyEngine(RuleEngine[CreditPolicyRule, CreditPolicyAlert]):
    def __init__(self):
        super().__init__()
        self.add_rule(HighDtiRule())
        self.add_rule(ThinFileRule())
        self.add_rule(DelinquencyRule())
        self.add_rule(CreditMLAnomalyRule())

    def evaluate(self, payload: Dict, context: Dict) -> List[CreditPolicyAlert]:
        alerts: List[CreditPolicyAlert] = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            try:
                result = rule.evaluate(payload, context)
                if result:
                    alerts.append(result)
            except Exception as exc:
                logger.warning("Credit policy rule failed: %s", exc)
        return alerts

class CreditFeatureExtractor:
    def __init__(self, db_connection=None):
        self.db_connection = db_connection
    
    def extract_features(self, user_id: str, application: Dict) -> Dict:
        features = {}
        
        # 1. Character - Payment history
        features.update(self._extract_character_features(user_id))
        
        # 2. Capacity - Income and debt
        features.update(self._extract_capacity_features(user_id, application))
        
        # 3. Capital - Net worth
        features.update(self._extract_capital_features(user_id))
        
        # 4. Collateral - Asset value
        features.update(self._extract_collateral_features(user_id))
        
        # 5. Conditions - Economic environment
        features.update(self._extract_conditions_features())
        
        # 6. Behavioral features
        features.update(self._extract_behavioral_features(user_id))
        
        # 7. Alternative data
        features.update(self._extract_alternative_data_features(user_id))
        
        return features
    
    def _extract_character_features(self, user_id: str) -> Dict:
        # Simulate database query
        payment_history = self._get_payment_history(user_id)
        
        return {
            # Payment history
            'payment_history_length_months': payment_history.get('length_months', 0),
            'on_time_payment_ratio': payment_history.get('on_time_ratio', 0.0),
            'late_payments_30d': payment_history.get('late_30d', 0),
            'late_payments_60d': payment_history.get('late_60d', 0),
            'late_payments_90d': payment_history.get('late_90d', 0),
            'delinquency_count': payment_history.get('delinquencies', 0),
            'charge_off_count': payment_history.get('charge_offs', 0),
            'bankruptcy_count': payment_history.get('bankruptcies', 0),
            'collections_count': payment_history.get('collections', 0),
            
            # Recent payment behavior
            'recent_missed_payments': payment_history.get('recent_missed', 0),
            'consecutive_on_time': payment_history.get('consecutive_on_time', 0),
        }
    
    def _extract_capacity_features(self, user_id: str, application: Dict) -> Dict:
        monthly_income = application.get('monthly_income', 0)
        
        # Get existing debts
        debts = self._get_user_debts(user_id)
        total_monthly_debt = sum(d.get('monthly_payment', 0) for d in debts)
        
        # Calculate debt-to-income ratio (DTI)
        dti_ratio = (total_monthly_debt / monthly_income) if monthly_income > 0 else 1.0
        
        return {
            # Income
            'monthly_income': monthly_income,
            'annual_income': monthly_income * 12,
            'income_verified': application.get('income_verified', False),
            'employment_length_months': application.get('employment_length', 0),
            'employment_type': application.get('employment_type', 'unknown'),
            
            # Debt
            'total_debt': sum(d.get('balance', 0) for d in debts),
            'total_monthly_debt_payment': total_monthly_debt,
            'debt_to_income_ratio': dti_ratio,
            'number_of_credit_accounts': len(debts),
            'revolving_balance': sum(d.get('balance', 0) for d in debts if d.get('type') == 'revolving'),
            'installment_balance': sum(d.get('balance', 0) for d in debts if d.get('type') == 'installment'),
        }
    
    def _extract_capital_features(self, user_id: str) -> Dict:
        assets = self._get_user_assets(user_id)
        liabilities = self._get_user_liabilities(user_id)
        
        total_assets = sum(a.get('value', 0) for a in assets)
        total_liabilities = sum(l.get('balance', 0) for l in liabilities)
        net_worth = total_assets - total_liabilities
        
        return {
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'net_worth': net_worth,
            'savings_balance': sum(a.get('value', 0) for a in assets if a.get('type') == 'savings'),
            'investment_balance': sum(a.get('value', 0) for a in assets if a.get('type') == 'investment'),
            'liquid_assets': sum(a.get('value', 0) for a in assets if a.get('liquid', False)),
        }
    
    def _extract_collateral_features(self, user_id: str) -> Dict:
        collateral = self._get_user_collateral(user_id)
        
        return {
            'has_real_estate': any(c.get('type') == 'real_estate' for c in collateral),
            'real_estate_value': sum(c.get('value', 0) for c in collateral if c.get('type') == 'real_estate'),
            'vehicle_value': sum(c.get('value', 0) for c in collateral if c.get('type') == 'vehicle'),
            'total_collateral_value': sum(c.get('value', 0) for c in collateral),
        }
    
    def _extract_conditions_features(self) -> Dict:
        # Macroeconomic indicators (usually from external API)
        return {
            'unemployment_rate': 4.5,  # Example value
            'inflation_rate': 2.3,
            'prime_rate': 7.5,
            'gdp_growth': 2.8,
        }
    
    def _extract_behavioral_features(self, user_id: str) -> Dict:
        transactions = self._get_recent_transactions(user_id, days=90)
        
        if not transactions:
            return {
                'transaction_count_90d': 0,
                'avg_transaction_amount': 0,
                'transaction_frequency': 0,
            }
        
        amounts = [t.get('amount', 0) for t in transactions]
        
        return {
            # Transaction behavior
            'transaction_count_90d': len(transactions),
            'avg_transaction_amount': sum(amounts) / len(amounts),
            'transaction_frequency': len(transactions) / 90,  # Average transactions per day
            'spending_volatility': self._calculate_std(amounts),
            
            # Account usage
            'account_age_months': self._get_account_age(user_id),
            'days_since_last_transaction': self._get_days_since_last_txn(user_id),
            'active_days_90d': len(set(t.get('date') for t in transactions)),
        }
    
    def _extract_alternative_data_features(self, user_id: str) -> Dict:
        return {
            # Mobile device usage
            'mobile_app_installed': True,  # Example
            'mobile_login_frequency': 15.3,  # Per month
            'mobile_session_duration_avg': 8.5,  # Minutes
            
            # Social network (if available)
            'social_connections_count': 0,
            'social_score': 0.0,
            
            # Other
            'utility_payment_history': 'good',  # Utilities
            'rental_payment_history': 'good',  # Rent
        }
    
    # Helper methods (simulate database queries)
    def _get_payment_history(self, user_id: str) -> Dict:
        return {
            'length_months': 36,
            'on_time_ratio': 0.95,
            'late_30d': 1,
            'late_60d': 0,
            'late_90d': 0,
            'delinquencies': 0,
            'charge_offs': 0,
            'bankruptcies': 0,
            'collections': 0,
            'recent_missed': 0,
            'consecutive_on_time': 12
        }
    
    def _get_user_debts(self, user_id: str) -> List[Dict]:
        return [
            {'balance': 3000, 'monthly_payment': 100, 'type': 'revolving'},
            {'balance': 15000, 'monthly_payment': 350, 'type': 'installment'},
        ]
    
    def _get_user_assets(self, user_id: str) -> List[Dict]:
        return [
            {'value': 5000, 'type': 'savings', 'liquid': True},
            {'value': 20000, 'type': 'investment', 'liquid': False},
        ]
    
    def _get_user_liabilities(self, user_id: str) -> List[Dict]:
        return self._get_user_debts(user_id)
    
    def _get_user_collateral(self, user_id: str) -> List[Dict]:
        return []
    
    def _get_recent_transactions(self, user_id: str, days: int) -> List[Dict]:
        return [
            {'amount': 50, 'date': '2026-02-01'},
            {'amount': 120, 'date': '2026-02-03'},
            {'amount': 80, 'date': '2026-02-05'},
        ]
    
    def _get_account_age(self, user_id: str) -> int:
        return 24  # 24 months
    
    def _get_days_since_last_txn(self, user_id: str) -> int:
        return 2
    
    @staticmethod
    def _calculate_std(values: List[float]) -> float:
        if len(values) <= 1:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

class CreditScoringModel:
    # FICO scoring weights (industry standard)
    FICO_WEIGHTS = {
        'payment_history': 0.35,  # Payment history (35%)
        'amounts_owed': 0.30,  # Amounts owed (30%)
        'length_of_credit': 0.15,  # Credit history length (15%)
        'new_credit': 0.10,  # New credit (10%)
        'credit_mix': 0.10,  # Credit mix (10%)
    }
    
    def __init__(self):
        self.min_score = 300
        self.max_score = 850
    
    def calculate_score(self, features: Dict) -> CreditScore:
        # 1. Calculate dimension scores
        payment_score = self._score_payment_history(features)
        debt_score = self._score_amounts_owed(features)
        history_score = self._score_length_of_credit(features)
        inquiry_score = self._score_new_credit(features)
        mix_score = self._score_credit_mix(features)
        
        # 2. Weighted average
        raw_score = (
            payment_score * self.FICO_WEIGHTS['payment_history'] +
            debt_score * self.FICO_WEIGHTS['amounts_owed'] +
            history_score * self.FICO_WEIGHTS['length_of_credit'] +
            inquiry_score * self.FICO_WEIGHTS['new_credit'] +
            mix_score * self.FICO_WEIGHTS['credit_mix']
        )
        
        # 3. Normalize to 300-850 range
        final_score = self.min_score + (raw_score * (self.max_score - self.min_score))
        final_score = max(self.min_score, min(self.max_score, final_score))
        
        # 4. Determine risk tier
        risk_tier = self._determine_risk_tier(final_score)
        
        # 5. Make decision
        decision = self._make_decision(final_score, features)
        
        # 6. Calculate recommended limit and APR
        recommended_limit = self._calculate_credit_limit(final_score, features)
        recommended_apr = self._calculate_apr(final_score, risk_tier)
        
        # 7. Generate reason codes
        reason_codes = self._generate_reason_codes(features, final_score)
        
        return CreditScore(
            score=round(final_score),
            risk_tier=risk_tier,
            decision=decision,
            confidence=round(0.85, 2),  # Can be calculated based on feature completeness
            factors={
                'payment_history': round(payment_score, 2),
                'amounts_owed': round(debt_score, 2),
                'length_of_credit': round(history_score, 2),
                'new_credit': round(inquiry_score, 2),
                'credit_mix': round(mix_score, 2)
            },
            recommended_limit=round(recommended_limit, 2),
            recommended_apr=round(recommended_apr, 2),
            reason_codes=reason_codes
        )
    
    def _score_payment_history(self, features: Dict) -> float:
        on_time_ratio = features.get('on_time_payment_ratio', 0.0)
        late_30d = features.get('late_payments_30d', 0)
        late_60d = features.get('late_payments_60d', 0)
        late_90d = features.get('late_payments_90d', 0)
        delinquencies = features.get('delinquency_count', 0)
        
        # Base score
        score = on_time_ratio
        
        # Late payment penalties
        score -= late_30d * 0.05
        score -= late_60d * 0.10
        score -= late_90d * 0.15
        score -= delinquencies * 0.20
        
        return max(0.0, min(1.0, score))
    
    def _score_amounts_owed(self, features: Dict) -> float:
        dti_ratio = features.get('debt_to_income_ratio', 0.0)
        
        # DTI < 36% considered good
        if dti_ratio <= 0.36:
            score = 1.0 - (dti_ratio / 0.36) * 0.3
        else:
            score = 0.7 - (min(dti_ratio - 0.36, 0.5) / 0.5) * 0.7
        
        return max(0.0, min(1.0, score))
    
    def _score_length_of_credit(self, features: Dict) -> float:
        history_months = features.get('payment_history_length_months', 0)
        account_age = features.get('account_age_months', 0)
        
        avg_age = (history_months + account_age) / 2
        
        # 7 years (84 months) considered excellent
        score = min(avg_age / 84, 1.0)
        
        return score
    
    def _score_new_credit(self, features: Dict) -> float:
        # Simplified: assume no frequent new credit applications
        return 0.9
    
    def _score_credit_mix(self, features: Dict) -> float:
        num_accounts = features.get('number_of_credit_accounts', 0)
        has_revolving = features.get('revolving_balance', 0) > 0
        has_installment = features.get('installment_balance', 0) > 0
        
        # Diversified credit types are better
        score = 0.5
        if has_revolving:
            score += 0.2
        if has_installment:
            score += 0.2
        if num_accounts >= 3:
            score += 0.1
        
        return min(1.0, score)
    
    def _determine_risk_tier(self, score: float) -> CreditRiskTier:
        if score >= 750:
            return CreditRiskTier.EXCELLENT
        elif score >= 700:
            return CreditRiskTier.GOOD
        elif score >= 650:
            return CreditRiskTier.FAIR
        elif score >= 600:
            return CreditRiskTier.POOR
        else:
            return CreditRiskTier.VERY_POOR
    
    def _make_decision(self, score: float, features: Dict) -> CreditDecision:
        # Decision thresholds
        if score >= 700:
            return CreditDecision.APPROVE
        elif score >= 620:
            # Medium score, check other factors
            dti = features.get('debt_to_income_ratio', 0)
            if dti < 0.43:  # DTI acceptable
                return CreditDecision.CONDITIONAL_APPROVE
            else:
                return CreditDecision.MANUAL_REVIEW
        elif score >= 550:
            return CreditDecision.MANUAL_REVIEW
        else:
            return CreditDecision.REJECT
    
    def _calculate_credit_limit(self, score: float, features: Dict) -> float:
        monthly_income = features.get('monthly_income', 0)
        
        if score >= 750:
            # Excellent: 30% of monthly income
            return monthly_income * 0.30
        elif score >= 700:
            # Good: 20% of monthly income
            return monthly_income * 0.20
        elif score >= 650:
            # Fair: 15% of monthly income
            return monthly_income * 0.15
        elif score >= 600:
            # Poor: 10% of monthly income
            return monthly_income * 0.10
        else:
            # Very poor: 5% of monthly income
            return monthly_income * 0.05
    
    def _calculate_apr(self, score: float, risk_tier: CreditRiskTier) -> float:
        base_rate = 7.5  # Prime rate
        
        if risk_tier == CreditRiskTier.EXCELLENT:
            return base_rate + 2.0  # 9.5%
        elif risk_tier == CreditRiskTier.GOOD:
            return base_rate + 5.0  # 12.5%
        elif risk_tier == CreditRiskTier.FAIR:
            return base_rate + 8.0  # 15.5%
        elif risk_tier == CreditRiskTier.POOR:
            return base_rate + 12.0  # 19.5%
        else:
            return base_rate + 17.0  # 24.5%
    
    def _generate_reason_codes(self, features: Dict, score: float) -> List[str]:
        codes = []
        
        if features.get('on_time_payment_ratio', 1.0) < 0.90:
            codes.append("LATE_PAYMENTS")
        
        if features.get('debt_to_income_ratio', 0) > 0.43:
            codes.append("HIGH_DTI")
        
        if features.get('delinquency_count', 0) > 0:
            codes.append("DELINQUENCIES")
        
        if features.get('payment_history_length_months', 999) < 12:
            codes.append("INSUFFICIENT_CREDIT_HISTORY")
        
        if features.get('bankruptcy_count', 0) > 0:
            codes.append("BANKRUPTCY")
        
        if score < 620:
            codes.append("LOW_CREDIT_SCORE")
        
        return codes if codes else ["APPROVED"]

class CreditRiskEngine:
    def __init__(self):
        self.feature_extractor = CreditFeatureExtractor()
        self.scoring_model = CreditScoringModel()
        self.policy_engine = CreditPolicyEngine()
        logger.info("Initialized Credit Risk Engine")
    
    def evaluate_application(
        self, 
        user_id: str, 
        application: Dict
    ) -> CreditScore:
        logger.info(f"Evaluating credit application for user: {user_id}")
        
        # 1. Extract features
        features = self.feature_extractor.extract_features(user_id, application)
        
        # 2. Calculate score
        credit_score = self.scoring_model.calculate_score(features)

        # 3. Apply policy rules
        policy_alerts = self.policy_engine.evaluate(application, {'features': features})
        for alert in policy_alerts:
            if alert.code not in credit_score.reason_codes:
                credit_score.reason_codes.append(alert.code)
        
        logger.info(
            f"Credit decision for {user_id}: {credit_score.decision.value} "
            f"(score: {credit_score.score:.0f}, tier: {credit_score.risk_tier.value})"
        )
        
        return credit_score
