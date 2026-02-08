import logging
import json
import sys
from typing import Any, Dict
from datetime import datetime

class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data)

def setup_logging(
    level: str = "INFO",
    format_type: str = "structured",
    log_file: str = None
):
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if format_type == "structured":
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        handlers=handlers
    )
    
    # Reduce noise from libraries
    logging.getLogger("kafka").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

class AuditLogger:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_fraud_detection(
        self,
        transaction_id: str,
        user_id: int,
        rule_name: str,
        is_fraud: bool,
        risk_score: float,
        metadata: Dict[str, Any]
    ):
        self.logger.info(
            extra={
                "extra_fields": {
                    "event_type": "fraud_detection",
                    "transaction_id": transaction_id,
                    "user_id": user_id,
                    "rule_name": rule_name,
                    "is_fraud": is_fraud,
                    "risk_score": risk_score,
                    "metadata": metadata
                }
            }
        )
    
    def log_feedback(
        self,
        transaction_id: str,
        user_id: int,
        feedback_type: str,
        analyst_id: str
    ):
        self.logger.info(
            "Analyst feedback",
            extra={
                "extra_fields": {
                    "event_type": "analyst_feedback",
                    "transaction_id": transaction_id,
                    "user_id": user_id,
                    "feedback_type": feedback_type,
                    "analyst_id": analyst_id
                }
            }
        )
    
    def log_model_update(
        self,
        model_version: str,
        metrics: Dict[str, float],
        training_data_size: int
    ):
        self.logger.info(
            "Model training completed",
            extra={
                "extra_fields": {
                    "event_type": "model_training",
                    "model_version": model_version,
                    "metrics": metrics,
                    "training_data_size": training_data_size
                }
            }
        )
