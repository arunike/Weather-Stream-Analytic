from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from enum import Enum
from pathlib import Path
import logging

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from .rule_engine import RuleEngine

logger = logging.getLogger(__name__)

class InsuranceType(Enum):
    AUTO = "auto"
    HEALTH = "health"
    PROPERTY = "property"
    LIFE = "life"

class FraudSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class InsuranceFraudAlert:
    is_fraud: bool
    severity: FraudSeverity
    rule_name: str
    confidence: float
    reason: str
    insurance_type: InsuranceType
    estimated_loss: float  # Estimated loss amount
    recommended_action: str
    evidence: List[str]  # Evidence list
    metadata: Dict
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

class InsuranceFraudRule(ABC):
    def __init__(self, enabled: bool = True, priority: int = 0):
        self.enabled = enabled
        self.priority = priority
        self.name = self.__class__.__name__
    
    @abstractmethod
    def evaluate(self, claim: Dict, context: Dict) -> InsuranceFraudAlert:
        pass


class StagedAccidentRule(InsuranceFraudRule):
    def __init__(
        self,
        time_window_hours: int = 2,
        similarity_threshold: float = 0.8,
        max_claims_per_year: int = 3,
        enabled: bool = True,
        priority: int = 10
    ):
        super().__init__(enabled, priority)
        self.time_window_hours = time_window_hours
        self.similarity_threshold = similarity_threshold
        self.max_claims_per_year = max_claims_per_year
    
    def evaluate(self, claim: Dict, context: Dict) -> InsuranceFraudAlert:
        claim_id = claim.get('claim_id')
        claimant_id = claim.get('claimant_id')
        accident_description = claim.get('description', '')
        accident_location = claim.get('location')
        accident_time = claim.get('accident_time')
        claim_amount = claim.get('amount', 0)
        
        evidence = []
        fraud_score = 0.0
        
        # 1. Check if multiple people reported same accident
        related_claims = context.get('related_claims', [])
        # Handle case where accident_time might be string or None
        if isinstance(accident_time, str):
             try:
                 accident_time = datetime.fromisoformat(accident_time.replace('Z', '+00:00'))
             except:
                 accident_time = datetime.utcnow()

        if not accident_time:
             accident_time = datetime.utcnow()

        cutoff_time = accident_time - timedelta(hours=self.time_window_hours)
        
        similar_claims = [
            c for c in related_claims
            if c.get('accident_time') >= cutoff_time and
            c.get('location') == accident_location and
            c.get('claim_id') != claim_id
        ]
        
        if len(similar_claims) >= 2:
            fraud_score += 0.3
            evidence.append(
                f"{len(similar_claims)} other claims filed for same location "
                f"within {self.time_window_hours} hours"
            )
        
        # 2. Check description similarity
        if similar_claims:
            for similar_claim in similar_claims:
                similarity = self._calculate_text_similarity(
                    accident_description,
                    similar_claim.get('description', '')
                )
                if similarity >= self.similarity_threshold:
                    fraud_score += 0.25
                    evidence.append(
                        f"Description highly similar ({similarity:.0%}) to claim "
                        f"{similar_claim.get('claim_id')}"
                    )
                    break
        
        # 3. Check claim frequency history
        claimant_history = context.get('claimant_history', [])
        recent_claims = [
            c for c in claimant_history
            if c.get('claim_date') >= datetime.utcnow() - timedelta(days=365)
        ]
        
        if len(recent_claims) >= self.max_claims_per_year:
            fraud_score += 0.25
            evidence.append(
                f"Claimant has {len(recent_claims)} claims in past year "
                f"(threshold: {self.max_claims_per_year})"
            )
        
        # 4. Check for known fraud networks
        known_fraudsters = context.get('known_fraudsters', set())
        related_parties = set(claim.get('involved_parties', []))
        
        fraud_connections = related_parties.intersection(known_fraudsters)
        if fraud_connections:
            fraud_score += 0.4
            evidence.append(
                f"Claim involves {len(fraud_connections)} known fraudsters"
            )
        
        # 5. Check if incident occurred at high-risk time/location
        is_high_risk_location = self._is_high_risk_location(accident_location)
        if is_high_risk_location:
            fraud_score += 0.1
            evidence.append("Accident location is known fraud hotspot")
        
        # Determination
        is_fraud = fraud_score >= 0.5
        
        if is_fraud:
            severity = (
                FraudSeverity.CRITICAL if fraud_score >= 0.8 else
                FraudSeverity.HIGH if fraud_score >= 0.65 else
                FraudSeverity.MEDIUM
            )
            
            return InsuranceFraudAlert(
                is_fraud=True,
                severity=severity,
                rule_name=self.name,
                confidence=min(0.95, fraud_score),
                reason=f"Staged accident suspected (fraud score: {fraud_score:.2f})",
                insurance_type=InsuranceType.AUTO,
                estimated_loss=claim_amount,
                recommended_action="Special Investigation Unit (SIU) review required",
                evidence=evidence,
                metadata={
                    'fraud_score': fraud_score,
                    'similar_claims_count': len(similar_claims),
                    'claimant_claims_per_year': len(recent_claims)
                }
            )
        
        return self._no_fraud_alert()
    
    @staticmethod
    def _calculate_text_similarity(text1: str, text2: str) -> float:
        if not text1 or not text2:
             return 0.0
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def _is_high_risk_location(location: str) -> bool:
        if not location:
             return False
        # Simplified implementation
        high_risk_areas = {'downtown', 'parking_lot', 'intersection_5th'}
        return any(area in location.lower() for area in high_risk_areas)
    
    def _no_fraud_alert(self) -> InsuranceFraudAlert:
        return InsuranceFraudAlert(
            is_fraud=False,
            severity=FraudSeverity.LOW,
            rule_name=self.name,
            confidence=0.0,
            reason="No staged accident indicators",
            insurance_type=InsuranceType.AUTO,
            estimated_loss=0.0,
            recommended_action="Standard processing",
            evidence=[],
            metadata={}
        )

class MedicalBillingFraudRule(InsuranceFraudRule):
    def __init__(
        self,
        upcoding_threshold: float = 0.3,  # Upcoding ratio threshold
        enabled: bool = True,
        priority: int = 9
    ):
        super().__init__(enabled, priority)
        self.upcoding_threshold = upcoding_threshold
    
    def evaluate(self, claim: Dict, context: Dict) -> InsuranceFraudAlert:
        provider_id = claim.get('provider_id')
        patient_id = claim.get('patient_id')
        procedures = claim.get('procedures', [])
        diagnosis_codes = claim.get('diagnosis_codes', [])
        total_billed = claim.get('total_amount', 0)
        
        evidence = []
        fraud_score = 0.0
        
        # 1. Detect upcoding
        upcoding_detected, upcoding_evidence = self._detect_upcoding(
            procedures, 
            diagnosis_codes,
            context
        )
        if upcoding_detected:
            fraud_score += 0.35
            evidence.extend(upcoding_evidence)
        
        # 2. Detect unbundling
        unbundling_detected = self._detect_unbundling(procedures)
        if unbundling_detected:
            fraud_score += 0.25
            evidence.append("Procedure unbundling detected - billing separately for bundled procedures")
        
        # 3. Detect overtreatment
        excessive_treatment = self._detect_excessive_treatment(
            patient_id,
            procedures,
            context
        )
        if excessive_treatment:
            fraud_score += 0.20
            evidence.append("Excessive or medically unnecessary procedures detected")
        
        # 4. Check provider history
        provider_history = context.get('provider_fraud_history', {})
        if provider_id in provider_history:
            fraud_score += 0.20
            evidence.append(f"Provider has fraud history: {provider_history[provider_id]}")
        
        # 5. Abnormally high bills
        avg_claim_amount = context.get('avg_claim_amount_for_diagnosis', 0)
        if avg_claim_amount > 0 and total_billed > avg_claim_amount * 2:
            fraud_score += 0.15
            evidence.append(
                f"Claim amount ${total_billed:.2f} is {total_billed/avg_claim_amount:.1f}x "
                f"higher than average ${avg_claim_amount:.2f}"
            )
        
        is_fraud = fraud_score >= 0.5
        
        if is_fraud:
            severity = (
                FraudSeverity.CRITICAL if fraud_score >= 0.8 else
                FraudSeverity.HIGH if fraud_score >= 0.65 else
                FraudSeverity.MEDIUM
            )
            
            return InsuranceFraudAlert(
                is_fraud=True,
                severity=severity,
                rule_name=self.name,
                confidence=min(0.90, fraud_score),
                reason=f"Medical billing fraud suspected (score: {fraud_score:.2f})",
                insurance_type=InsuranceType.HEALTH,
                estimated_loss=total_billed * 0.5,  # Estimate 50% as fraudulent
                recommended_action="Medical review and provider audit",
                evidence=evidence,
                metadata={
                    'fraud_score': fraud_score,
                    'provider_id': provider_id,
                    'num_procedures': len(procedures)
                }
            )
        
        return self._no_fraud_alert()
    
    def _detect_upcoding(
        self, 
        procedures: List[Dict],
        diagnosis_codes: List[str],
        context: Dict
    ) -> tuple:
        # Get standard procedure-diagnosis mapping
        standard_mappings = context.get('procedure_diagnosis_mappings', {})
        
        evidence = []
        mismatches = 0
        
        for proc in procedures:
            proc_code = proc.get('code')
            expected_level = standard_mappings.get(proc_code, {}).get('typical_level')
            actual_level = proc.get('level')
            
            if expected_level and actual_level and actual_level > expected_level:
                mismatches += 1
                evidence.append(
                    f"Procedure {proc_code} billed at level {actual_level} "
                    f"(typical: {expected_level})"
                )
        
        upcoding_ratio = mismatches / len(procedures) if procedures else 0
        
        return (
            upcoding_ratio >= self.upcoding_threshold,
            evidence
        )
    
    def _detect_unbundling(self, procedures: List[Dict]) -> bool:
        # Simplified: check if procedures that should be bundled are billed separately
        procedure_codes = [p.get('code') for p in procedures]
        
        # Example: certain procedures should usually be bundled
        bundled_sets = [
            {'CPT-001', 'CPT-002'},  # These two usually together
            {'CPT-101', 'CPT-102', 'CPT-103'},
        ]
        
        for bundle in bundled_sets:
            if bundle.issubset(set(procedure_codes)):
                return True
        
        return False
    
    def _detect_excessive_treatment(
        self,
        patient_id: str,
        procedures: List[Dict],
        context: Dict
    ) -> bool:
        # Check for duplicate treatments within short period
        patient_history = context.get('patient_claim_history', {}).get(patient_id, [])
        
        # 30天内相同procedure超过3次
        recent_procedures = {}
        for claim in patient_history[-10:]:  # 最近10次理赔
            for proc in claim.get('procedures', []):
                code = proc.get('code')
                recent_procedures[code] = recent_procedures.get(code, 0) + 1
        
        for code in [p.get('code') for p in procedures]:
            if recent_procedures.get(code, 0) >= 3:
                return True
        
        return False
    
    def _no_fraud_alert(self) -> InsuranceFraudAlert:
        return InsuranceFraudAlert(
            is_fraud=False,
            severity=FraudSeverity.LOW,
            rule_name=self.name,
            confidence=0.0,
            reason="No medical billing fraud indicators",
            insurance_type=InsuranceType.HEALTH,
            estimated_loss=0.0,
            recommended_action="Standard processing",
            evidence=[],
            metadata={}
        )

class PropertyInflationRule(InsuranceFraudRule):
    def __init__(
        self,
        inflation_threshold: float = 1.5,  # Valuation 50% higher than market price
        enabled: bool = True,
        priority: int = 8
    ):
        super().__init__(enabled, priority)
        self.inflation_threshold = inflation_threshold
    
    def evaluate(self, claim: Dict, context: Dict) -> InsuranceFraudAlert:
        claim_amount = claim.get('amount', 0)
        item_description = claim.get('item_description')
        estimated_value = claim.get('estimated_value', 0)
        loss_date = claim.get('loss_date')
        claimant_id = claim.get('claimant_id')
        
        evidence = []
        fraud_score = 0.0
        
        # 1. Check if valuation is inflated
        market_value = context.get('market_value', estimated_value * 0.7)
        
        if estimated_value > market_value * self.inflation_threshold:
            inflation_ratio = estimated_value / market_value
            fraud_score += 0.4
            evidence.append(
                f"Estimated value ${estimated_value:.2f} is {inflation_ratio:.1f}x "
                f"higher than market value ${market_value:.2f}"
            )
        
        # 2. Check for duplicate claims
        claimant_history = context.get('claimant_history', [])
        duplicate_claims = [
            c for c in claimant_history
            if c.get('item_description') == item_description and
            c.get('loss_date') != loss_date
        ]
        
        if duplicate_claims:
            fraud_score += 0.35
            evidence.append(
                f"Similar item claimed {len(duplicate_claims)} times previously"
            )
        
        # 3. Check claim timing patterns (financial hardship periods)
        recent_payment_issues = context.get('recent_payment_issues', False)
        if recent_payment_issues:
            fraud_score += 0.15
            evidence.append("Claimant has recent financial difficulties")
        
        # 4. Check loss circumstances
        suspicious_circumstances = self._check_suspicious_circumstances(claim)
        if suspicious_circumstances:
            fraud_score += 0.20
            evidence.append("Loss circumstances are suspicious")
        
        is_fraud = fraud_score >= 0.5
        
        if is_fraud:
            severity = (
                FraudSeverity.HIGH if fraud_score >= 0.7 else
                FraudSeverity.MEDIUM
            )
            
            return InsuranceFraudAlert(
                is_fraud=True,
                severity=severity,
                rule_name=self.name,
                confidence=min(0.85, fraud_score),
                reason=f"Property claim inflation suspected (score: {fraud_score:.2f})",
                insurance_type=InsuranceType.PROPERTY,
                estimated_loss=estimated_value - market_value,
                recommended_action="Request proof of ownership and independent appraisal",
                evidence=evidence,
                metadata={
                    'fraud_score': fraud_score,
                    'claimed_value': estimated_value,
                    'market_value': market_value,
                    'inflation_ratio': estimated_value / market_value if market_value > 0 else 0
                }
            )
        
        return self._no_fraud_alert()
    
    @staticmethod
    def _check_suspicious_circumstances(claim: Dict) -> bool:
        loss_cause = claim.get('cause', '').lower()
        suspicious_causes = ['fire', 'theft', 'mysterious_disappearance']
        
        # Fire, theft, mysterious disappearance are easier to fake
        if any(cause in loss_cause for cause in suspicious_causes):
            # Further checks
            has_police_report = claim.get('has_police_report', False)
            if not has_police_report and 'theft' in loss_cause:
                return True  # Theft but no police report
        
        return False
    
    def _no_fraud_alert(self) -> InsuranceFraudAlert:
        return InsuranceFraudAlert(
            is_fraud=False,
            severity=FraudSeverity.LOW,
            rule_name=self.name,
            confidence=0.0,
            reason="No property inflation indicators",
            insurance_type=InsuranceType.PROPERTY,
            estimated_loss=0.0,
            recommended_action="Standard processing",
            evidence=[],
            metadata={}
        )


class InsuranceMLAnomalyRule(InsuranceFraudRule):
    def __init__(self, min_confidence: float = 0.25, **kwargs):
        super().__init__(priority=6, **kwargs)
        self.min_confidence = min_confidence
        self.model_path = (
            Path(__file__).resolve().parents[2] / 'ml_models' / 'insurance_anomaly.joblib'
        )
        self.model = self._load_or_train()

    def evaluate(self, claim: Dict, context: Dict) -> InsuranceFraudAlert:
        vector = self._extract_features(claim, context)
        score = float(self.model.decision_function([vector])[0])
        is_anomaly = int(self.model.predict([vector])[0]) == -1
        confidence = min(1.0, abs(score))

        if not is_anomaly or confidence < self.min_confidence:
            return InsuranceFraudAlert(
                is_fraud=False,
                severity=FraudSeverity.LOW,
                rule_name=self.name,
                confidence=0.0,
                reason="ML model did not flag anomaly",
                insurance_type=self._get_insurance_type(claim),
                estimated_loss=0.0,
                recommended_action="Standard processing",
                evidence=[],
                metadata={}
            )

        severity = FraudSeverity.MEDIUM
        if confidence >= 0.6:
            severity = FraudSeverity.HIGH

        return InsuranceFraudAlert(
            is_fraud=True,
            severity=severity,
            rule_name=self.name,
            confidence=confidence,
            reason="ML anomaly detected in claim profile",
            insurance_type=self._get_insurance_type(claim),
            estimated_loss=float(claim.get('claim_amount', 0)) * 0.4,
            recommended_action="Manual review recommended",
            evidence=["ML anomaly score exceeded threshold"],
            metadata={
                'ml_score': score,
                'ml_features': {
                    'claim_amount': vector[0],
                    'estimated_value': vector[1],
                    'recent_claims': vector[2],
                    'police_report': vector[3]
                }
            }
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
        claim_amounts = rng.normal(2500.0, 1200.0, 800)
        estimated_values = rng.normal(2400.0, 1100.0, 800)
        recent_claims = rng.integers(0, 5, 800)
        police_reports = rng.integers(0, 2, 800)

        training_data = np.column_stack(
            [
                np.abs(claim_amounts),
                np.abs(estimated_values),
                recent_claims.astype(float),
                police_reports.astype(float)
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
    def _extract_features(claim: Dict, context: Dict) -> List[float]:
        claim_amount = float(claim.get('claim_amount', claim.get('amount', 0.0)))
        estimated_value = float(claim.get('estimated_value', claim_amount))
        recent_claims = float(len(context.get('claimant_history', [])))
        police_report = 1.0 if claim.get('has_police_report') else 0.0

        return [claim_amount, estimated_value, recent_claims, police_report]

    @staticmethod
    def _get_insurance_type(claim: Dict) -> InsuranceType:
        raw_type = claim.get('insurance_type')
        if isinstance(raw_type, InsuranceType):
            return raw_type
        if isinstance(raw_type, str):
            try:
                return InsuranceType(raw_type)
            except ValueError:
                return InsuranceType.PROPERTY
        return InsuranceType.PROPERTY

class InsuranceFraudEngine(RuleEngine[InsuranceFraudRule, InsuranceFraudAlert]):
    def __init__(self):
        super().__init__()
        self.rules: List[InsuranceFraudRule] = []
        self._initialize_default_rules()
        logger.info("Initialized Insurance Fraud Detection Engine")
    
    def _initialize_default_rules(self):
        self.add_rule(StagedAccidentRule())
        self.add_rule(MedicalBillingFraudRule())
        self.add_rule(PropertyInflationRule())
        self.add_rule(InsuranceMLAnomalyRule())
    
    def add_rule(self, rule: InsuranceFraudRule):
        super().add_rule(rule)
        logger.info(f"Added rule: {rule.name} (priority: {rule.priority})")
    
    def evaluate(
        self,
        payload: Dict,
        context: Dict
    ) -> List[InsuranceFraudAlert]:
        insurance_type = payload.get('insurance_type')
        logger.info(
            f"Evaluating {insurance_type} insurance claim: "
            f"{payload.get('claim_id')}"
        )

        alerts = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            try:
                alert = rule.evaluate(payload, context)
                if alert.is_fraud:
                    alerts.append(alert)
                    logger.warning(
                        f"Fraud alert: {rule.name} "
                        f"(confidence: {alert.confidence:.2f}, "
                        f"severity: {alert.severity.value})"
                    )
            except Exception as exc:
                logger.error(f"Error evaluating rule {rule.name}: {str(exc)}")

        return alerts

    def evaluate_claim(
        self,
        claim: Dict,
        context: Dict
    ) -> List[InsuranceFraudAlert]:
        return self.evaluate(claim, context)
    
    def get_highest_severity_alert(
        self,
        alerts: List[InsuranceFraudAlert]
    ) -> Optional[InsuranceFraudAlert]:
        if not alerts:
            return None
        
        severity_order = {
            FraudSeverity.CRITICAL: 4,
            FraudSeverity.HIGH: 3,
            FraudSeverity.MEDIUM: 2,
            FraudSeverity.LOW: 1
        }
        
        return max(
            alerts,
            key=lambda a: (severity_order[a.severity], a.confidence)
        )
