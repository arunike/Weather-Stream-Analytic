import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST
)

logger = logging.getLogger(__name__)

@dataclass
class MetricSnapshot:
    timestamp: float = field(default_factory=time.time)
    transaction_count: int = 0
    fraud_detected_count: int = 0
    false_positive_count: int = 0
    true_positive_count: int = 0
    avg_latency_ms: float = 0.0
    current_tps: float = 0.0
    state_store_size: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "transaction_count": self.transaction_count,
            "fraud_detected_count": self.fraud_detected_count,
            "false_positive_count": self.false_positive_count,
            "true_positive_count": self.true_positive_count,
            "avg_latency_ms": self.avg_latency_ms,
            "current_tps": self.current_tps,
            "state_store_size": self.state_store_size,
            "detection_rate": (
                self.fraud_detected_count / self.transaction_count
                if self.transaction_count > 0 else 0.0
            ),
            "false_positive_rate": (
                self.false_positive_count / self.fraud_detected_count
                if self.fraud_detected_count > 0 else 0.0
            )
        }

class MetricsCollector:
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        self.logger = logging.getLogger(__name__)
        
        # Transaction metrics
        self.transaction_counter = Counter(
            'fraud_detection_transactions_total',
            'Total number of transactions processed',
            ['status'],  # Labels: processed, failed
            registry=self.registry
        )
        
        self.fraud_detection_counter = Counter(
            'fraud_detection_alerts_total',
            'Total fraud alerts generated',
            ['rule_name', 'severity'],  # Labels: rule type, severity
            registry=self.registry
        )
        
        self.feedback_counter = Counter(
            'fraud_detection_feedback_total',
            'User feedback on fraud alerts',
            ['feedback_type'],  # Labels: true_fraud, false_positive
            registry=self.registry
        )
        
        # Performance metrics
        self.processing_latency = Histogram(
            'fraud_detection_processing_latency_seconds',
            'Transaction processing latency',
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
            registry=self.registry
        )
        
        self.batch_size = Histogram(
            'fraud_detection_batch_size',
            'Number of transactions per batch',
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000],
            registry=self.registry
        )
        
        self.event_lag = Gauge(
            'fraud_detection_event_lag_seconds',
            'Lag between event time and processing time',
            registry=self.registry
        )
        
        # State store metrics
        self.state_store_size = Gauge(
            'fraud_detection_state_store_size',
            'Number of entries in state store',
            registry=self.registry
        )
        
        self.state_store_memory = Gauge(
            'fraud_detection_state_store_memory_bytes',
            'Memory used by state store',
            registry=self.registry
        )
        
        # ML model metrics
        self.ml_prediction_counter = Counter(
            'fraud_detection_ml_predictions_total',
            'ML model predictions',
            ['prediction'],  # Labels: fraud, normal
            registry=self.registry
        )
        
        self.ml_inference_latency = Summary(
            'fraud_detection_ml_inference_latency_seconds',
            'ML model inference latency',
            registry=self.registry
        )
        
        self.model_score_distribution = Histogram(
            'fraud_detection_model_score',
            'Distribution of ML model scores',
            buckets=[-10, -5, -2, -1, -0.5, 0, 0.5, 1, 2, 5, 10],
            registry=self.registry
        )
        
        # System health metrics
        self.system_health = Gauge(
            'fraud_detection_system_health',
            'System health status (1=healthy, 0=unhealthy)',
            ['component'],  # Labels: kafka, redis, postgres, spark
            registry=self.registry
        )
        
        # Geo-velocity metrics
        self.geo_velocity_detected = Counter(
            'fraud_detection_geo_velocity_alerts_total',
            'Geo-velocity anomalies detected',
            registry=self.registry
        )
        
        self.travel_speed = Histogram(
            'fraud_detection_travel_speed_kmh',
            'Distribution of calculated travel speeds',
            buckets=[0, 50, 100, 200, 500, 800, 1000, 2000, 5000],
            registry=self.registry
        )
        
        # Internal state
        self._start_time = time.time()
        self._transaction_count = 0
        self._fraud_count = 0
        self._latencies = []
        self._window_start = time.time()
        self._window_transactions = 0
    
    # Transaction tracking
    def increment_transaction_count(self, status: str = "processed"):
        self.transaction_counter.labels(status=status).inc()
        self._transaction_count += 1
        self._window_transactions += 1
    
    def increment_fraud_detected(self, rule_name: str = "unknown", severity: str = "medium"):
        self.fraud_detection_counter.labels(rule_name=rule_name, severity=severity).inc()
        self._fraud_count += 1
    
    def record_feedback(self, is_true_fraud: bool):
        feedback_type = "true_fraud" if is_true_fraud else "false_positive"
        self.feedback_counter.labels(feedback_type=feedback_type).inc()
    
    # Performance tracking
    def record_processing_latency(self, latency_seconds: float):
        self.processing_latency.observe(latency_seconds)
        self._latencies.append(latency_seconds)
        
        # Keep only last 1000 measurements
        if len(self._latencies) > 1000:
            self._latencies = self._latencies[-1000:]
    
    def record_batch_size(self, size: int):
        self.batch_size.observe(size)
    
    def update_event_lag(self, lag_seconds: float):
        self.event_lag.set(lag_seconds)
    
    # State store tracking
    def update_state_store_size(self, size: int):
        self.state_store_size.set(size)
    
    def update_state_store_memory(self, bytes_used: int):
        self.state_store_memory.set(bytes_used)
    
    # ML model tracking
    def record_ml_prediction(self, is_fraud: bool, score: float, inference_time: float):
        prediction = "fraud" if is_fraud else "normal"
        self.ml_prediction_counter.labels(prediction=prediction).inc()
        self.ml_inference_latency.observe(inference_time)
        self.model_score_distribution.observe(score)
    
    # System health tracking
    def update_component_health(self, component: str, is_healthy: bool):
        self.system_health.labels(component=component).set(1 if is_healthy else 0)
    
    # Geo-velocity tracking
    def record_geo_velocity_alert(self, speed_kmh: float):
        self.geo_velocity_detected.inc()
        self.travel_speed.observe(speed_kmh)
    
    # Aggregated metrics
    def get_metrics(self) -> Dict[str, Any]:
        current_time = time.time()
        window_duration = current_time - self._window_start
        
        avg_latency_ms = (
            sum(self._latencies) / len(self._latencies) * 1000
            if self._latencies else 0.0
        )
        
        current_tps = (
            self._window_transactions / window_duration
            if window_duration > 0 else 0.0
        )
        
        return {
            "transaction_count": self._transaction_count,
            "fraud_detected_count": self._fraud_count,
            "avg_latency_ms": avg_latency_ms,
            "current_tps": current_tps,
            "uptime_seconds": current_time - self._start_time,
            "detection_rate": (
                self._fraud_count / self._transaction_count
                if self._transaction_count > 0 else 0.0
            )
        }
    
    def get_snapshot(self) -> MetricSnapshot:
        metrics = self.get_metrics()
        return MetricSnapshot(
            transaction_count=metrics["transaction_count"],
            fraud_detected_count=metrics["fraud_detected_count"],
            avg_latency_ms=metrics["avg_latency_ms"],
            current_tps=metrics["current_tps"]
        )
    
    def reset_window(self):
        self._window_start = time.time()
        self._window_transactions = 0
    
    def export_metrics(self) -> bytes:
        return generate_latest(self.registry)
    
    def get_content_type(self) -> str:
        return CONTENT_TYPE_LATEST

class PerformanceMonitor:
    def __init__(self, collector: MetricsCollector, operation: str):
        self.collector = collector
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            latency = time.time() - self.start_time
            self.collector.record_processing_latency(latency)
