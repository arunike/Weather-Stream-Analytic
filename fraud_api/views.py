from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse, HttpResponse
import json
import logging
import random # For mock context
import time

from .state_manager import RedisStateManager
from .tasks import record_async_audit
from .metrics import record_detection, render_prometheus, PROMETHEUS_CONTENT_TYPE

# Import restored logic modules
from .logic.aml_rules import AMLRuleEngine, AMLRiskLevel
from .logic.credit_risk import CreditRiskEngine, CreditDecision
from .logic.insurance_fraud import InsuranceFraudEngine, FraudSeverity
from .logic.market_manipulation import MarketManipulationEngine, ManipulationSeverity

# Import models & serializers
from .models import AMLDetection, CreditAssessment, InsuranceClaim, MarketAlert
from .serializers import (
    AMLDetectionSerializer, 
    CreditAssessmentSerializer, 
    InsuranceClaimSerializer, 
    MarketAlertSerializer,
    UserSerializer,
    RegisterSerializer
)

logger = logging.getLogger(__name__)

# Initialize engines globally
aml_engine = AMLRuleEngine()
credit_engine = CreditRiskEngine()
insurance_engine = InsuranceFraudEngine()
market_engine = MarketManipulationEngine()

state_manager = RedisStateManager()

# --- Auth Views ---
class RegisterView(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            "user": UserSerializer(user).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)

# --- Utility Endpoints ---
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({"status": "healthy", "service": "fraud-detection-api"})


@api_view(['GET'])
@permission_classes([AllowAny])
def metrics(request):
    audit_count = state_manager.get_list_length('fraud_state:async_audits')
    return Response({
        "cache": {
            "aml_events": state_manager.get_list_length('fraud_state:global:aml_transactions'),
            "credit_events": state_manager.get_list_length('fraud_state:global:credit_applications'),
            "insurance_events": state_manager.get_list_length('fraud_state:global:insurance_claims'),
            "market_events": state_manager.get_list_length('fraud_state:global:market_trades')
        },
        "async_audits": {
            "events": audit_count
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def prometheus_metrics(request):
    return HttpResponse(render_prometheus(), content_type=PROMETHEUS_CONTENT_TYPE)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_modules(request):
    modules = [
        {
            "key": "aml",
            "name": "AML",
            "displayName": "AML Detections",
            "color": "#8b5cf6",
            "icon": "💰",
            "enabled": True,
            "order": 1,
            "description": "Anti-Money Laundering monitoring"
        },
        {
            "key": "credit",
            "name": "Credit",
            "displayName": "Credit Risk",
            "color": "#3b82f6",
            "icon": "📊",
            "enabled": True,
            "order": 2,
            "description": "Credit scoring and risk assessment"
        },
        {
            "key": "insurance",
            "name": "Insurance",
            "displayName": "Insurance Fraud",
            "color": "#10b981",
            "icon": "🛡️",
            "enabled": True,
            "order": 3,
            "description": "Claims analysis and fraud detection"
        },
        {
            "key": "market",
            "name": "Market",
            "displayName": "Market Manipulation",
            "color": "#f59e0b",
            "icon": "📈",
            "enabled": True,
            "order": 4,
            "description": "Market manipulation detection"
        },
    ]
    return Response({"modules": modules})

@api_view(['POST', 'DELETE'])
@permission_classes([AllowAny])
def clear_history(request):
    AMLDetection.objects.all().delete()
    CreditAssessment.objects.all().delete()
    InsuranceClaim.objects.all().delete()
    MarketAlert.objects.all().delete()
    return Response({"status": "cleared", "message": "All history records deleted successfully"})

# --- Main Detection ViewSets ---

class AMLDetectionViewSet(viewsets.ModelViewSet):
    queryset = AMLDetection.objects.all().order_by('-timestamp')
    serializer_class = AMLDetectionSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        start_time = time.perf_counter()
        data = request.data
        transaction_id = data.get('transaction_id', f"TXN-{random.randint(10000,99999)}")
        amount = float(data.get('amount', 0))
        user_id = data.get('user_id') or data.get('sender_id') or "anonymous"
        now = timezone.now()
        
        # Build Context (Mock for POC)
        # Scan recent transactions from DB for 'structuring' rule
        recent_txns = AMLDetection.objects.all().order_by('-timestamp')[:10]
        # Convert DB models to dicts for the engine
        recent_txn_dicts = []
        for txn in recent_txns:
             # Basic reconstruction since we don't store full txn details in this simple model, just alerts
             # In a real system, we'd query a Transaction table.
             # For now, we just pass the current one repeatedly to simulate *some* history
             pass

        recent_txns = state_manager.get_recent_transactions(user_id)
        context = {
            'recent_transactions': recent_txns,
            'user_profile': {
                'historical_transactions': [],
                'typical_transaction_hour': 12,
                'frequent_merchants': ['Amazon', 'Walmart']
            },
            'transaction_chain': []
        }

        transaction_payload = {
            'transaction_id': transaction_id,
            'user_id': user_id,
            'amount': amount,
            'hour': now.hour,
            'sender_id': data.get('sender_id', ''),
            'receiver_id': data.get('receiver_id', ''),
            'sender_country': data.get('sender_country', ''),
            'receiver_country': data.get('receiver_country', ''),
            'merchant_id': data.get('merchant_id', ''),
            'from_account': data.get('from_account', ''),
            'to_account': data.get('to_account', ''),
            'timestamp': now.timestamp()
        }

        # Run Engine
        alerts = aml_engine.evaluate_transaction(transaction_payload, context)
        
        # Calculate Risk Score
        risk_score = 0.0
        if alerts:
            # Normalize confidence sum to 0-100 score
            max_conf = max(a.confidence for a in alerts)
            risk_score = max_conf * 100
        
        # Serialize alerts for storage
        alerts_data = []
        for alert in alerts:
            alerts_data.append({
                'rule': alert.rule_name,
                'severity': alert.risk_level.value,
                'confidence': alert.confidence,
                'reason': alert.reason,
                'metadata': alert.metadata
            })
            
        # Create Record
        detection = AMLDetection.objects.create(
            transaction_id=transaction_id,
            amount=amount,
            sender_id=data.get('sender_id', ''),
            receiver_id=data.get('receiver_id', ''),
            risk_score=risk_score,
            alerts=alerts_data
        )

        record_detection('aml', risk_score >= 50, time.perf_counter() - start_time)

        state_manager.add_transaction(user_id, transaction_payload)
        state_manager.add_global_transaction('aml_transactions', transaction_payload)
        try:
            record_async_audit.delay({
                'module': 'aml',
                'record_id': detection.id,
                'risk_score': risk_score,
                'transaction_id': transaction_id
            })
        except Exception as exc:
            logger.warning("Failed to dispatch async audit: %s", exc)
        
        serializer = self.get_serializer(detection)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class CreditAssessmentViewSet(viewsets.ModelViewSet):
    queryset = CreditAssessment.objects.all().order_by('-timestamp')
    serializer_class = CreditAssessmentSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        start_time = time.perf_counter()
        data = request.data
        user_id = data.get('applicant_id', f"USER-{random.randint(1000,9999)}")
        recent_applications = state_manager.get_recent_transactions(
            user_id,
            namespace='credit_applications'
        )
        
        # Run Engine (it has internal mock data)
        credit_score = credit_engine.evaluate_application(user_id, data)
        
        # Map decision to model choices
        decision_map = {
            CreditDecision.APPROVE: CreditAssessment.APPROVED,
            CreditDecision.CONDITIONAL_APPROVE: CreditAssessment.APPROVED, # Map conditional to approve for simplicity in simplified model
            CreditDecision.REJECT: CreditAssessment.DECLINED,
            CreditDecision.MANUAL_REVIEW: CreditAssessment.MANUAL_REVIEW
        }
        
        model_decision = decision_map.get(credit_score.decision, CreditAssessment.MANUAL_REVIEW)
        
        # Prepare alerts/factors
        alerts_data = []
        # Add rejection reasons
        for reason in credit_score.reason_codes:
            alerts_data.append({
                'type': 'reason_code',
                'message': reason,
                'severity': 'medium'
            })
        
        # Add risk factors
        for factor, weight in credit_score.factors.items():
            alerts_data.append({
                'type': 'risk_factor',
                'factor': factor,
                'weight': weight,
                'severity': 'info'
            })

        # Add recommended limits
        alerts_data.append({
             'type': 'recommendation',
             'limit': credit_score.recommended_limit,
             'apr': credit_score.recommended_apr,
             'severity': 'info'
        })

        assessment = CreditAssessment.objects.create(
            applicant_id=user_id,
            risk_score=credit_score.score,
            decision=model_decision,
            alerts=alerts_data
        )

        record_detection(
            'credit',
            credit_score.score < 650,
            time.perf_counter() - start_time
        )

        application_payload = {
            'applicant_id': user_id,
            'risk_score': credit_score.score,
            'decision': model_decision,
            'timestamp': timezone.now().timestamp(),
            'recent_applications': len(recent_applications)
        }
        state_manager.add_transaction(
            user_id,
            application_payload,
            namespace='credit_applications'
        )
        state_manager.add_global_transaction('credit_applications', application_payload)
        try:
            record_async_audit.delay({
                'module': 'credit',
                'record_id': assessment.id,
                'risk_score': credit_score.score,
                'transaction_id': assessment.applicant_id
            })
        except Exception as exc:
            logger.warning("Failed to dispatch async audit: %s", exc)
        
        # Determine risk tier based on score
        if credit_score.score >= 750:
            risk_tier = 'LOW'
        elif credit_score.score >= 650:
            risk_tier = 'MEDIUM'
        else:
            risk_tier = 'HIGH'
        
        serializer = self.get_serializer(assessment)
        response_data = serializer.data
        response_data['credit_score'] = credit_score.score
        response_data['risk_tier'] = risk_tier
        response_data['factors'] = credit_score.factors
        
        return Response(response_data, status=status.HTTP_201_CREATED)

class InsuranceClaimViewSet(viewsets.ModelViewSet):
    queryset = InsuranceClaim.objects.all().order_by('-timestamp')
    serializer_class = InsuranceClaimSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        start_time = time.perf_counter()
        data = request.data
        claim_id = data.get('claim_id', f"CLM-{random.randint(10000,99999)}")
        claimant_id = data.get('claimant_id', data.get('policy_id', 'unknown'))
        recent_claims = state_manager.get_recent_transactions(
            claimant_id,
            namespace='insurance_claims'
        )
        
        # Mock Context
        context = {
            'related_claims': [],
            'claimant_history': recent_claims,
            'known_fraudsters': set(['BAD_ACTOR_1', 'BAD_ACTOR_2']),
            'market_value': float(data.get('estimated_value', 0)) * 0.8  # Assume market value is lower to trigger inflation rule if high value
        }
        
        # Run Engine
        alerts = insurance_engine.evaluate_claim(data, context)
        
        # Calculate Fraud Risk
        fraud_risk = 0.0
        if alerts:
            max_conf = max(a.confidence for a in alerts)
            fraud_risk = max_conf * 100
            
        alerts_data = []
        for alert in alerts:
            alerts_data.append({
                'rule': alert.rule_name,
                'severity': alert.severity.value,
                'confidence': alert.confidence,
                'reason': alert.reason,
                'evidence': alert.evidence
            })
            
        claim = InsuranceClaim.objects.create(
            claim_id=claim_id,
            policy_id=data.get('policy_id', ''),
            claim_amount=float(data.get('claim_amount', 0)),
            fraud_risk=fraud_risk,
            alerts=alerts_data
        )

        record_detection(
            'insurance',
            fraud_risk >= 50,
            time.perf_counter() - start_time
        )

        claim_payload = {
            'claim_id': claim_id,
            'claimant_id': claimant_id,
            'claim_amount': float(data.get('claim_amount', 0)),
            'fraud_risk': fraud_risk,
            'timestamp': timezone.now().timestamp()
        }
        state_manager.add_transaction(
            claimant_id,
            claim_payload,
            namespace='insurance_claims'
        )
        state_manager.add_global_transaction('insurance_claims', claim_payload)
        try:
            record_async_audit.delay({
                'module': 'insurance',
                'record_id': claim.id,
                'risk_score': fraud_risk,
                'transaction_id': claim_id
            })
        except Exception as exc:
            logger.warning("Failed to dispatch async audit: %s", exc)
        
        serializer = self.get_serializer(claim)
        response_data = serializer.data
        response_data['fraud_probability'] = fraud_risk / 100.0  # Convert 0-100 to 0-1
        response_data['flagged'] = fraud_risk > 50
        
        return Response(response_data, status=status.HTTP_201_CREATED)

class MarketAlertViewSet(viewsets.ModelViewSet):
    queryset = MarketAlert.objects.all().order_by('-timestamp')
    serializer_class = MarketAlertSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        start_time = time.perf_counter()
        data = request.data
        symbol = data.get('symbol', 'UNKNOWN')
        volume = float(data.get('volume', 0))
        price = float(data.get('price', 0))
        trader_id = data.get('trader_id', symbol)
        recent_trades = state_manager.get_recent_transactions(
            trader_id,
            namespace='market_trades'
        )
        
        # Create data dict with correct types for engine
        trade_data = {
            'symbol': symbol,
            'price': price,
            'volume': volume,
            'timestamp': data.get('timestamp'),
            'trader_id': trader_id
        }
        
        # Mock Context to trigger rules
        # Triggers PUMP_AND_DUMP if volume/price is high relative to these defaults
        context = {
            'avg_volume_30d': 1000, 
            'price_24h_ago': price * 0.8, # 20% jump
            'social_media_mentions_24h': 500,
            'avg_social_mentions': 50,
            'market_cap': 10000000, # Small cap
            'buy_sell_ratio': 4.0,
            'trader_recent_trades': recent_trades,
            'related_trader_accounts': {}
        }
        
        # Run Engine
        alerts = market_engine.evaluate_trade(trade_data, context)
        
        manipulation_risk = 0.0
        if alerts:
            max_conf = max(a.confidence for a in alerts)
            manipulation_risk = max_conf * 100
            
        alerts_data = []
        for alert in alerts:
            alerts_data.append({
                'rule': alert.manipulation_type.value.replace('_', ' ').title(),
                'alert_type': alert.manipulation_type.value,
                'severity': alert.severity.value.upper(),
                'confidence': alert.confidence,
                'reason': alert.reason,
                'evidence': alert.evidence
            })
            
        market_alert = MarketAlert.objects.create(
            symbol=symbol,
            price=float(data.get('price', 0)),
            volume=float(data.get('volume', 0)),
            manipulation_risk=manipulation_risk,
            alerts=alerts_data
        )

        record_detection(
            'market',
            manipulation_risk >= 50,
            time.perf_counter() - start_time
        )

        trade_payload = {
            'symbol': symbol,
            'trader_id': trader_id,
            'price': price,
            'volume': volume,
            'manipulation_risk': manipulation_risk,
            'timestamp': timezone.now().timestamp()
        }
        state_manager.add_transaction(
            trader_id,
            trade_payload,
            namespace='market_trades'
        )
        state_manager.add_global_transaction('market_trades', trade_payload)
        try:
            record_async_audit.delay({
                'module': 'market',
                'record_id': market_alert.id,
                'risk_score': manipulation_risk,
                'transaction_id': symbol
            })
        except Exception as exc:
            logger.warning("Failed to dispatch async audit: %s", exc)
        
        serializer = self.get_serializer(market_alert)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# --- Statistics View ---
@api_view(['GET'])
@permission_classes([AllowAny])
def statistics(request):
    # Calculate daily trends for last 7 days
    today = timezone.now().date()
    trends = []
    
    # Pre-fetch counts to avoid N+1 (though simple loop is fine here for small N)
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        
        # Filter by created_at__date (assuming timestamp is the field)
        # Note: SQLite/Postgres differences in date lookup. Range is safer.
        start_dt = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.min.time()))
        end_dt = start_dt + timedelta(days=1)
        
        daily_aml = AMLDetection.objects.filter(timestamp__range=(start_dt, end_dt)).count()
        daily_credit = CreditAssessment.objects.filter(timestamp__range=(start_dt, end_dt)).count()
        daily_insurance = InsuranceClaim.objects.filter(timestamp__range=(start_dt, end_dt)).count()
        daily_market = MarketAlert.objects.filter(timestamp__range=(start_dt, end_dt)).count()
        
        trends.append({
            'date': date.strftime('%Y-%m-%d'),
            'aml': daily_aml,
            'credit': daily_credit,
            'insurance': daily_insurance,
            'market': daily_market
        })
    
    # Risk Distribution (High/Medium/Low based on risk score)
    # Generic logic: >80 High, >50 Medium, else Low
    def get_risk_dist(queryset, score_field):
        high = queryset.filter(**{f"{score_field}__gte": 80}).count()
        medium = queryset.filter(**{f"{score_field}__gte": 50, f"{score_field}__lt": 80}).count()
        low = queryset.filter(**{f"{score_field}__lt": 50}).count()
        return {"high": high, "medium": medium, "low": low}

    risk_dist = {
        "aml": get_risk_dist(AMLDetection.objects.all(), 'risk_score'),
        "credit": {"high": 0, "medium": 0, "low": 0}, # Credit is score based (inverted risk), skip for now or mapping?
        # Credit: <600 High Risk, 600-700 Medium, >700 Low Risk
        "insurance": get_risk_dist(InsuranceClaim.objects.all(), 'fraud_risk'),
        "market": get_risk_dist(MarketAlert.objects.all(), 'manipulation_risk')
    }
    
    # Credit specific dist
    credit_high = CreditAssessment.objects.filter(risk_score__lt=600).count()
    credit_med = CreditAssessment.objects.filter(risk_score__gte=600, risk_score__lt=700).count()
    credit_low = CreditAssessment.objects.filter(risk_score__gte=700).count()
    risk_dist['credit'] = {"high": credit_high, "medium": credit_med, "low": credit_low}
    
    # Recent Alerts (combine all types)
    recent_alerts = []
    
    # AML
    for item in AMLDetection.objects.all().order_by('-timestamp')[:5]:
        # Parse alerts to see if any high severity
        is_flagged = item.risk_score > 50
        status_text = "Review Required" if is_flagged else "Cleared"
        recent_alerts.append({
            "id": f"AML-{item.id}",
            "record_id": item.id,
            "module": "aml",
            "type": "AML",
            "message": f"Transaction {item.transaction_id}",
            "description": f"Transaction {item.transaction_id}",
            "risk_level": "high" if item.risk_score > 80 else "medium" if item.risk_score > 50 else "low",
            "severity": "high" if item.risk_score > 80 else "medium" if item.risk_score > 50 else "low",
            "timestamp": item.timestamp.isoformat(),
            "status": status_text
        })
    
    # Credit
    for item in CreditAssessment.objects.all().order_by('-timestamp')[:2]:
        is_high_risk = item.risk_score < 650
        recent_alerts.append({
            "id": f"CREDIT-{item.id}",
            "record_id": item.id,
            "module": "credit",
            "type": "Credit",
            "message": f"Application {item.applicant_id}",
            "description": f"Application {item.applicant_id} - Score: {int(item.risk_score)}",
            "risk_level": "high" if item.risk_score < 600 else "medium" if item.risk_score < 700 else "low",
            "severity": "high" if item.risk_score < 600 else "medium" if item.risk_score < 700 else "low",
            "timestamp": item.timestamp.isoformat(),
            "status": item.decision
        })
        
    # Insurance
    for item in InsuranceClaim.objects.all().order_by('-timestamp')[:2]:
        recent_alerts.append({
            "id": f"INS-{item.id}",
            "record_id": item.id,
            "module": "insurance",
            "type": "Insurance",
            "message": f"Claim {item.claim_id}",
            "description": f"Claim {item.claim_id} - ${item.claim_amount:,.0f}",
            "risk_level": "high" if item.fraud_risk > 80 else "medium" if item.fraud_risk > 50 else "low",
            "severity": "high" if item.fraud_risk > 80 else "medium" if item.fraud_risk > 50 else "low",
            "timestamp": item.timestamp.isoformat(),
            "status": "Flagged" if item.fraud_risk > 50 else "Cleared"
        })
    
    # Market
    for item in MarketAlert.objects.all().order_by('-timestamp')[:2]:
        recent_alerts.append({
            "id": f"MARKET-{item.id}",
            "record_id": item.id,
            "module": "market",
            "type": "Market",
            "message": f"Symbol {item.symbol}",
            "description": f"{item.symbol} - ${item.price:.2f}",
            "risk_level": "high" if item.manipulation_risk > 80 else "medium" if item.manipulation_risk > 50 else "low",
            "severity": "high" if item.manipulation_risk > 80 else "medium" if item.manipulation_risk > 50 else "low",
            "timestamp": item.timestamp.isoformat(),
            "status": "Alert" if item.manipulation_risk > 50 else "Normal"
        })
        
    # Sort by timestamp
    recent_alerts.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_alerts = recent_alerts[:10]
    
    # Calculate totals
    total_aml = AMLDetection.objects.count()
    total_credit = CreditAssessment.objects.count()
    total_insurance = InsuranceClaim.objects.count()
    total_market = MarketAlert.objects.count()
    total_detections = total_aml + total_credit + total_insurance + total_market
    
    # Calculate total flagged (high risk items)
    flagged_aml = AMLDetection.objects.filter(risk_score__gte=50).count()
    flagged_credit = CreditAssessment.objects.filter(risk_score__lt=650).count()
    flagged_insurance = InsuranceClaim.objects.filter(fraud_risk__gte=50).count()
    flagged_market = MarketAlert.objects.filter(manipulation_risk__gte=50).count()
    total_flagged = flagged_aml + flagged_credit + flagged_insurance + flagged_market
    
    # Merge risk distribution
    merged_risk_dist = {
        "low": sum(dist["low"] for dist in risk_dist.values()),
        "medium": sum(dist["medium"] for dist in risk_dist.values()),
        "high": sum(dist["high"] for dist in risk_dist.values())
    }

    return JsonResponse({
        "totals": {
            "total_detections": total_detections,
            "total_flagged": total_flagged,
            "aml_count": total_aml,
            "credit_count": total_credit,
            "insurance_count": total_insurance,
            "market_count": total_market
        },
        "trends": {
            "daily": trends
        },
        "risk_distribution": merged_risk_dist,
        "recent_alerts": recent_alerts
    })
