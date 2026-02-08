from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Database configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_USER = os.getenv('DB_USER', 'admin')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
DB_NAME = os.getenv('DB_NAME', 'fraud_detection')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create engine
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database Models
class AMLDetection(Base):
    __tablename__ = 'aml_detections'
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    transaction_id = Column(String(100), index=True)
    num_transactions = Column(Integer)
    total_amount = Column(Float)
    alerts = Column(JSON)  # Store alerts as JSON
    created_at = Column(DateTime, default=datetime.utcnow)

class CreditAssessment(Base):
    __tablename__ = 'credit_assessments'
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    applicant_id = Column(String(100), index=True)
    credit_score = Column(Float)
    risk_tier = Column(String(50))
    decision = Column(String(50))
    confidence = Column(Float)
    recommended_limit = Column(Float)
    recommended_apr = Column(Float)
    factors = Column(JSON)  # Risk factors
    reason_codes = Column(JSON)  # List of reason codes
    requested_amount = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class InsuranceClaim(Base):
    __tablename__ = 'insurance_claims'
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    claim_id = Column(String(100), index=True)
    claim_type = Column(String(50))
    claim_amount = Column(Float)
    alerts = Column(JSON)  # Store alerts as JSON
    created_at = Column(DateTime, default=datetime.utcnow)

class MarketAlert(Base):
    __tablename__ = 'market_alerts'
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(20), index=True)
    price = Column(Float)
    volume = Column(Float)
    alerts = Column(JSON)  # Store alerts as JSON
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create database tables: {e}")
        return False

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Database operations
class DatabaseManager:
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def save_aml_detection(self, data: dict):
        db = self.SessionLocal()
        try:
            record = AMLDetection(
                timestamp=data.get('timestamp'),
                transaction_id=data.get('transaction_id'),
                num_transactions=data.get('num_transactions'),
                total_amount=data.get('total_amount'),
                alerts=self._serialize_alerts(data.get('alerts', []))
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record.id
        except Exception as e:
            db.rollback()
            print(f"Error saving AML detection: {e}")
            raise
        finally:
            db.close()
    
    def save_credit_assessment(self, data: dict):
        db = self.SessionLocal()
        try:
            score = data.get('score')
            record = CreditAssessment(
                timestamp=data.get('timestamp'),
                applicant_id=data.get('applicant_id'),
                credit_score=score.score if score else None,
                risk_tier=score.risk_tier.value if score else None,
                decision=score.decision.value if score else None,
                confidence=score.confidence if score else None,
                recommended_limit=score.recommended_limit if score else None,
                recommended_apr=score.recommended_apr if score else None,
                factors=score.factors if score else None,
                reason_codes=score.reason_codes if score else None,
                requested_amount=data.get('requested_amount')
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record.id
        except Exception as e:
            db.rollback()
            print(f"Error saving credit assessment: {e}")
            raise
        finally:
            db.close()
    
    def save_insurance_claim(self, data: dict):
        db = self.SessionLocal()
        try:
            record = InsuranceClaim(
                timestamp=data.get('timestamp'),
                claim_id=data.get('claim_id'),
                claim_type=data.get('claim_type'),
                claim_amount=data.get('claim_amount'),
                alerts=self._serialize_alerts(data.get('alerts', []))
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record.id
        except Exception as e:
            db.rollback()
            print(f"Error saving insurance claim: {e}")
            raise
        finally:
            db.close()
    
    def save_market_alert(self, data: dict):
        db = self.SessionLocal()
        try:
            record = MarketAlert(
                timestamp=data.get('timestamp'),
                symbol=data.get('symbol'),
                price=data.get('price'),
                volume=data.get('volume'),
                alerts=self._serialize_alerts(data.get('alerts', []))
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record.id
        except Exception as e:
            db.rollback()
            print(f"Error saving market alert: {e}")
            raise
        finally:
            db.close()
    
    def get_aml_history(self, limit: int = 100):
        db = self.SessionLocal()
        try:
            records = db.query(AMLDetection).order_by(
                AMLDetection.timestamp.desc()
            ).limit(limit).all()
            return [self._aml_to_dict(r) for r in records]
        finally:
            db.close()
    
    def get_credit_history(self, limit: int = 100):
        db = self.SessionLocal()
        try:
            records = db.query(CreditAssessment).order_by(
                CreditAssessment.timestamp.desc()
            ).limit(limit).all()
            return [self._credit_to_dict(r) for r in records]
        finally:
            db.close()
    
    def get_insurance_history(self, limit: int = 100):
        db = self.SessionLocal()
        try:
            records = db.query(InsuranceClaim).order_by(
                InsuranceClaim.timestamp.desc()
            ).limit(limit).all()
            return [self._insurance_to_dict(r) for r in records]
        finally:
            db.close()
    
    def get_market_history(self, limit: int = 100):
        db = self.SessionLocal()
        try:
            records = db.query(MarketAlert).order_by(
                MarketAlert.timestamp.desc()
            ).limit(limit).all()
            return [self._market_to_dict(r) for r in records]
        finally:
            db.close()
    
    def clear_all_history(self):
        db = self.SessionLocal()
        try:
            db.query(AMLDetection).delete()
            db.query(CreditAssessment).delete()
            db.query(InsuranceClaim).delete()
            db.query(MarketAlert).delete()
            db.commit()
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()
    
    def get_statistics(self):
        db = self.SessionLocal()
        try:
            return {
                'aml_count': db.query(AMLDetection).count(),
                'credit_count': db.query(CreditAssessment).count(),
                'insurance_count': db.query(InsuranceClaim).count(),
                'market_count': db.query(MarketAlert).count()
            }
        finally:
            db.close()
    
    @staticmethod
    def _serialize_alerts(alerts):
        if not alerts:
            return []
        result = []
        for alert in alerts:
            if hasattr(alert, '__dict__'):
                alert_dict = {}
                for key, value in alert.__dict__.items():
                    if not key.startswith('_'):
                        if hasattr(value, 'value'):
                            alert_dict[key] = value.value
                        elif isinstance(value, datetime):
                            alert_dict[key] = value.isoformat()
                        else:
                            alert_dict[key] = value
                result.append(alert_dict)
            else:
                result.append(alert)
        return result
    
    @staticmethod
    def _aml_to_dict(record):
        return {
            'timestamp': record.timestamp,
            'transaction_id': record.transaction_id,
            'num_transactions': record.num_transactions,
            'total_amount': record.total_amount,
            'alerts': record.alerts
        }
    
    @staticmethod
    def _credit_to_dict(record):
        from dataclasses import dataclass
        from credit_risk import CreditScore, CreditRiskTier, CreditDecision
        
        # Reconstruct CreditScore object
        score = type('CreditScore', (), {
            'score': record.credit_score,
            'risk_tier': type('risk_tier', (), {'value': record.risk_tier})(),
            'decision': type('decision', (), {'value': record.decision})(),
            'confidence': record.confidence,
            'factors': record.factors or {},
            'recommended_limit': record.recommended_limit,
            'recommended_apr': record.recommended_apr,
            'reason_codes': record.reason_codes or [],
            'timestamp': record.timestamp
        })()
        
        return {
            'timestamp': record.timestamp,
            'applicant_id': record.applicant_id,
            'score': score,
            'requested_amount': record.requested_amount
        }
    
    @staticmethod
    def _insurance_to_dict(record):
        return {
            'timestamp': record.timestamp,
            'claim_id': record.claim_id,
            'claim_type': record.claim_type,
            'claim_amount': record.claim_amount,
            'alerts': record.alerts
        }
    
    @staticmethod
    def _market_to_dict(record):
        return {
            'timestamp': record.timestamp,
            'symbol': record.symbol,
            'price': record.price,
            'volume': record.volume,
            'alerts': record.alerts
        }
