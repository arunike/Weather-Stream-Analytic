from typing import Dict, List, Union
from enum import Enum
import logging

from src.financial.aml_rules import AMLRuleEngine, AMLAlert
from src.financial.credit_risk import CreditRiskEngine, CreditScore
from src.financial.insurance_fraud import InsuranceFraudEngine, InsuranceFraudAlert
from src.financial.market_manipulation import MarketManipulationEngine, ManipulationAlert

logger = logging.getLogger(__name__)

class FinancialServiceType(Enum):
    FRAUD_DETECTION = "fraud_detection"  # Original payment fraud
    AML = "aml"  # Anti-Money Laundering
    CREDIT_RISK = "credit_risk"  # Credit risk
    INSURANCE_FRAUD = "insurance_fraud"  # Insurance fraud
    MARKET_MANIPULATION = "market_manipulation"  # Market manipulation


class UnifiedFinancialPlatform:
    def __init__(self):
        # Initialize all engines
        self.aml_engine = AMLRuleEngine()
        self.credit_engine = CreditRiskEngine()
        self.insurance_engine = InsuranceFraudEngine()
        self.market_engine = MarketManipulationEngine()
        
        logger.info("Initialized Unified Financial Platform with 4 services")
    
    def process_event(
        self,
        service_type: FinancialServiceType,
        event_data: Dict,
        context: Dict = None
    ) -> Union[List[AMLAlert], CreditScore, List[InsuranceFraudAlert], List[ManipulationAlert]]:
        context = context or {}
        
        if service_type == FinancialServiceType.AML:
            return self._process_aml(event_data, context)
        elif service_type == FinancialServiceType.CREDIT_RISK:
            return self._process_credit_risk(event_data, context)
        elif service_type == FinancialServiceType.INSURANCE_FRAUD:
            return self._process_insurance_fraud(event_data, context)
        elif service_type == FinancialServiceType.MARKET_MANIPULATION:
            return self._process_market_manipulation(event_data, context)
        else:
            raise ValueError(f"Unknown service type: {service_type}")
    
    def _process_aml(self, transaction: Dict, context: Dict) -> List[AMLAlert]:
        logger.info(f"Processing AML check for transaction: {transaction.get('transaction_id')}")
        return self.aml_engine.evaluate_transaction(transaction, context)
    
    def _process_credit_risk(self, application: Dict, context: Dict) -> CreditScore:
        user_id = application.get('user_id')
        logger.info(f"Processing credit risk assessment for user: {user_id}")
        return self.credit_engine.evaluate_application(user_id, application)
    
    def _process_insurance_fraud(self, claim: Dict, context: Dict) -> List[InsuranceFraudAlert]:
        logger.info(f"Processing insurance fraud check for claim: {claim.get('claim_id')}")
        return self.insurance_engine.evaluate_claim(claim, context)
    
    def _process_market_manipulation(self, trade: Dict, context: Dict) -> List[ManipulationAlert]:
        logger.info(f"Processing market manipulation check for symbol: {trade.get('symbol')}")
        return self.market_engine.evaluate_trade(trade, context)
    
    def get_platform_stats(self) -> Dict:
        return {
            'services': [
                {
                    'name': 'AML Detection',
                    'rules_count': len(self.aml_engine.rules),
                    'status': 'active'
                },
                {
                    'name': 'Credit Risk Scoring',
                    'status': 'active'
                },
                {
                    'name': 'Insurance Fraud Detection',
                    'rules_count': len(self.insurance_engine.rules),
                    'status': 'active'
                },
                {
                    'name': 'Market Manipulation Detection',
                    'rules_count': len(self.market_engine.rules),
                    'status': 'active'
                }
            ],
            'total_capabilities': 4
        }

def example_aml_detection():
    print("\n" + "="*60)
    print("Example 1: AML (Anti-Money Laundering) Detection")
    print("="*60)
    
    platform = UnifiedFinancialPlatform()
    
    # Simulate a suspicious structured transaction
    suspicious_transaction = {
        'transaction_id': 'TXN-001',
        'user_id': 'USER-123',
        'amount': 9500,  # Slightly below the $10,000 reporting threshold
        'timestamp': '2026-02-07T10:00:00Z',
        'from_account': 'ACC-001',
        'to_account': 'ACC-002',
    }
    
    context = {
        'recent_transactions': [
            {'user_id': 'USER-123', 'amount': 9300, 'timestamp': '2026-02-07T08:00:00Z'},
            {'user_id': 'USER-123', 'amount': 9600, 'timestamp': '2026-02-07T09:00:00Z'},
        ]
    }
    
    alerts = platform.process_event(
        FinancialServiceType.AML,
        suspicious_transaction,
        context
    )
    
    print(f"\n✅ AML detection completed!")

    print(f"触发告警数: {len(alerts)}")
    
    for alert in alerts:
        print(f"\n🚨 告警详情:")
        print(f"  规则: {alert.rule_name}")
        print(f"  风险等级: {alert.risk_level.value}")
        print(f"  置信度: {alert.confidence:.2%}")
        print(f"  原因: {alert.reason}")
        print(f"  建议措施: {alert.recommended_action}")


def example_credit_risk_scoring():
    print("\n" + "="*60)
    print("Example 2: Credit Risk Scoring")
    print("="*60)
    
    platform = UnifiedFinancialPlatform()
    
    # Simulate a credit application
    application = {
        'user_id': 'USER-456',
        'monthly_income': 5000,
        'employment_length': 36,  # 3 years
        'employment_type': 'full_time',
        'income_verified': True,
    }
    
    credit_score = platform.process_event(
        FinancialServiceType.CREDIT_RISK,
        application
    )
    
    print(f"\n✅ Credit risk scoring completed!")
    print(f"\n📊 Scoring Results:")
    print(f"  Credit Score: {credit_score.score:.0f} / 850")
    print(f"  Risk Tier: {credit_score.risk_tier.value}")
    print(f"  Decision: {credit_score.decision.value.upper()}")
    print(f"  Recommended Limit: ${credit_score.recommended_limit:,.2f}")
    print(f"  Recommended APR: {credit_score.recommended_apr:.2f}%")
    print(f"\n  Key Factors:")
    for factor, score in credit_score.factors.items():
        print(f"    {factor}: {score:.2f}")


def example_insurance_fraud():
    print("\n" + "="*60)
    print("Example 3: Insurance Fraud Detection")
    print("="*60)
    
    platform = UnifiedFinancialPlatform()
    
    # Simulate suspicious auto insurance claim
    claim = {
        'claim_id': 'CLM-789',
        'claimant_id': 'CLAIMANT-001',
        'insurance_type': 'auto',
        'amount': 8000,
        'description': 'rear-end collision at intersection',
        'location': 'intersection_5th',
        'accident_time': '2026-02-07T14:00:00Z',
    }
    
    context = {
        'related_claims': [
            {
                'claim_id': 'CLM-788',
                'location': 'intersection_5th',
                'description': 'rear end collision at intersection',
                'accident_time': '2026-02-07T13:30:00Z'
            }
        ],
        'claimant_history': [
            {'claim_date': '2025-08-01'},
            {'claim_date': '2025-11-01'},
        ]
    }
    
    alerts = platform.process_event(
        FinancialServiceType.INSURANCE_FRAUD,
        claim,
        context
    )
    
    print(f"\n✅ Insurance fraud detection completed!")
    print(f"Alerts triggered: {len(alerts)}")
    
    for alert in alerts:
        print(f"\n🚨 Fraud Alert:")
        print(f"  Rule: {alert.rule_name}")
        print(f"  Severity: {alert.severity.value}")
        print(f"  Confidence: {alert.confidence:.2%}")
        print(f"  Reason: {alert.reason}")
        print(f"  Estimated Loss: ${alert.estimated_loss:,.2f}")
        print(f"  Recommended Action: {alert.recommended_action}")
        if alert.evidence:
            print(f"  Evidence:")
            for evidence in alert.evidence:
                print(f"    - {evidence}")


def example_market_manipulation():
    print("\n" + "="*60)
    print("Example 4: Market Manipulation Detection")
    print("="*60)
    
    platform = UnifiedFinancialPlatform()
    
    # Simulate suspicious pump and dump
    trade = {
        'symbol': 'XYZ',
        'price': 15.50,
        'volume': 1000000,
        'timestamp': '2026-02-07T15:00:00Z',
        'participants': ['TRADER-001', 'TRADER-002']
    }
    
    context = {
        'avg_volume_30d': 150000,  # Average trading volume
        'price_24h_ago': 10.00,  # Price 24 hours ago
        'social_media_mentions_24h': 5000,
        'avg_social_mentions': 200,
        'market_cap': 200_000_000,  # $200M (small-cap stock)
        'buy_sell_ratio': 4.5,
    }
    
    alerts = platform.process_event(
        FinancialServiceType.MARKET_MANIPULATION,
        trade,
        context
    )
    
    print(f"\n✅ Market manipulation detection completed!")
    print(f"Alerts triggered: {len(alerts)}")
    
    for alert in alerts:
        print(f"\n🚨 Manipulation Alert:")
        print(f"  Symbol: {alert.symbol}")
        print(f"  Manipulation Type: {alert.manipulation_type.value}")
        print(f"  Severity: {alert.severity.value}")
        print(f"  Confidence: {alert.confidence:.2%}")
        print(f"  Reason: {alert.reason}")
        print(f"  Estimated Impact: ${alert.estimated_impact:,.2f}")
        print(f"  Recommended Action: {alert.recommended_action}")
        if alert.evidence:
            print(f"  Evidence:")
            for evidence in alert.evidence:
                print(f"    - {evidence}")


def demo_all_services():
    print("\n" + "🎯" * 30)
    print("Unified Financial Services Platform - Complete Demo")
    print("🎯" * 30)
    
    # 1. AML Detection
    example_aml_detection()
    
    # 2. Credit Risk Scoring
    example_credit_risk_scoring()
    
    # 3. Insurance Fraud Detection
    example_insurance_fraud()
    
    # 4. Market Manipulation Detection
    example_market_manipulation()
    
    # Platform Statistics
    print("\n" + "="*60)
    print("Platform Statistics")
    print("="*60)
    
    platform = UnifiedFinancialPlatform()
    stats = platform.get_platform_stats()
    
    print(f"\n📊 Platform Capabilities:")
    for service in stats['services']:
        rules_info = f" ({service['rules_count']} rules)" if 'rules_count' in service else ""
        print(f"  ✓ {service['name']}{rules_info} - {service['status']}")
    
    print(f"\nTotal: {stats['total_capabilities']} financial services")
    
    print("\n" + "="*60)
    print("✅ Demo Completed! Platform is ready.")
    print("="*60 + "\n")


if __name__ == '__main__':
    # Run complete demo
    demo_all_services()
