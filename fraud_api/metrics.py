from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

PROMETHEUS_CONTENT_TYPE = CONTENT_TYPE_LATEST

DETECTION_COUNTER = Counter(
    'fraud_detections_total',
    'Total detections by module',
    ['module']
)

FLAGGED_COUNTER = Counter(
    'fraud_flagged_total',
    'Total flagged detections by module',
    ['module']
)

LATENCY_HISTOGRAM = Histogram(
    'fraud_detection_latency_seconds',
    'Detection latency by module',
    ['module']
)


def record_detection(module: str, is_flagged: bool, latency_seconds: float) -> None:
    DETECTION_COUNTER.labels(module=module).inc()
    if is_flagged:
        FLAGGED_COUNTER.labels(module=module).inc()
    LATENCY_HISTOGRAM.labels(module=module).observe(latency_seconds)


def render_prometheus() -> bytes:
    return generate_latest()
