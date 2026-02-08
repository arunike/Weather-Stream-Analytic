# 🏗️ Architecture Documentation

## System Architecture Overview

The Real-Time Fraud Detection Platform follows a **Lambda Architecture** with separated hot and cold paths, providing both real-time alerting and comprehensive batch analytics.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INGESTION LAYER                                     │
│  ┌──────────────────────┐                                                   │
│  │ Transaction Generator │  Produces 50+ TPS                                │
│  │  (Faker + Random)    │────────────────────────┐                         │
│  └──────────────────────┘                        │                         │
│                                                    ▼                         │
│                                          ┌──────────────────┐               │
│                                          │  Apache Kafka    │               │
│                                          │  Topic: txns     │               │
│                                          └──────────────────┘               │
└─────────────────────────────────────────────────────────────────────────────┘
                                                    │
                                 ┌──────────────────┴──────────────────┐
                                 │                                      │
┌────────────────────────────────▼─────┐     ┌───────────────────────▼──────┐
│          HOT PATH (Real-time)        │     │    COLD PATH (Batch)         │
│  ⚡ Sub-100ms latency                 │     │    📊 5-min batches          │
│  ┌────────────────────────────────┐  │     │  ┌──────────────────────┐   │
│  │   Spark Structured Streaming   │  │     │  │  Spark Streaming     │   │
│  │   - Essential rules only       │  │     │  │  - All rules         │   │
│  │   - ML inference (fast)        │  │     │  │  - Pattern detection │   │
│  │   - Geo-velocity check         │  │     │  │  - Feature gen       │   │
│  └────────────────────────────────┘  │     │  └──────────────────────┘   │
│               │                       │     │              │               │
│               ▼                       │     │              ▼               │
│  ┌────────────────────────────────┐  │     │  ┌──────────────────────┐   │
│  │  State Store (Redis)           │  │     │  │  Delta Lake          │   │
│  │  - User last location          │  │     │  │  - S3/MinIO          │   │
│  │  - Transaction history         │  │     │  │  - ACID guarantees   │   │
│  │  - TTL: 24 hours              │  │     │  │  - Time travel       │   │
│  └────────────────────────────────┘  │     │  └──────────────────────┘   │
│               │                       │     │              │               │
│               ▼                       │     │              ▼               │
│  ┌────────────────────────────────┐  │     │  ┌──────────────────────┐   │
│  │  PostgreSQL (Hot Storage)      │  │     │  │  Feature Store       │   │
│  │  - Immediate alerts            │  │     │  │  - ML training data  │   │
│  │  - Analyst feedback            │  │     │  │  - Aggregates        │   │
│  └────────────────────────────────┘  │     │  └──────────────────────┘   │
└──────────────────────────────────────┘     └──────────────────────────────┘
                    │                                         │
                    └──────────────┬──────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                        SERVING & ANALYTICS LAYER                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐ │
│  │  Streamlit       │  │  Grafana         │  │  Airflow                 │ │
│  │  Dashboard       │  │  Monitoring      │  │  ML Retraining           │ │
│  │  - Alert review  │  │  - Metrics viz   │  │  - Feedback loop         │ │
│  │  - Feedback      │  │  - Performance   │  │  - Model versioning      │ │
│  │  - Geo heatmap   │  │  - Health status │  │  - Feature engineering   │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Ingestion Layer

#### Transaction Generator
- **Language:** Python
- **Libraries:** Faker, kafka-python
- **Throughput:** 50-100 TPS
- **Data Format:** JSON (validated against schema)

```python
{
  "transaction_id": "uuid-v4",
  "user_id": 1-100,
  "amount": 5-5000,
  "location": {"lat": float, "lon": float, "city": str, "country": str},
  "timestamp": unix_timestamp
}
```

#### Apache Kafka
- **Version:** 7.5.0
- **Topics:**
  - `transactions` - Raw transaction stream
  - `fraud_alerts` - Detected fraud events
- **Replication:** 1 (single-broker setup, increase for prod)
- **Partitions:** 3 (allows parallel processing)

---

### 2. Processing Layer

#### Hot Path (Real-time)

**Purpose:** Immediate fraud detection with minimal latency

**Components:**
- **Spark Structured Streaming**
  - Batch interval: 1 second
  - Trigger: `processingTime='1 second'`
  - Checkpoint: S3/MinIO

**Rules Applied:**
1. High Amount (> $2000)
2. Geo-velocity (> 800 km/h)
3. ML Anomaly (Isolation Forest)

**Data Flow:**
```
Kafka → Spark → Redis (state) → PostgreSQL (alerts)
  └─────────────→ Metrics (Prometheus)
```

**Implementation:** `src/core/hot_path.py`

#### Cold Path (Batch Analytics)

**Purpose:** Comprehensive analysis and pattern detection

**Components:**
- **Spark Structured Streaming**
  - Batch interval: 5 minutes
  - Trigger: `processingTime='5 minutes'`
  - Checkpoint: S3/MinIO

**Rules Applied:**
1. All hot path rules
2. Frequency detection
3. Geographic clustering
4. Temporal patterns
5. Coordinated attacks

**Data Flow:**
```
Kafka → Spark → Delta Lake → Feature Store
  └─────────────→ Pattern Detection
  └─────────────→ ML Training Data
```

**Implementation:** `src/core/cold_path.py`

---

### 3. Storage Layer

#### Redis (State Store)
- **Version:** 7 (Alpine)
- **Purpose:** Distributed state management
- **Data:**
  - User last location (with TTL)
  - Transaction frequency counters
  - ML model cache
- **TTL:** 24 hours (configurable)
- **Eviction:** LRU policy

**Key Patterns:**
```
user_loc:{user_id}              → {lat, lon, timestamp}
user_loc:{user_id}:v{version}   → Versioned state
fraud_state:txn_count:{user_id} → Sorted set (timestamps)
processed_txn:{txn_id}          → Idempotency check
```

#### PostgreSQL (Hot Storage)
- **Version:** 15
- **Purpose:** Immediate alerts and feedback
- **Tables:**

```sql
-- Fraud Alerts
CREATE TABLE fraud_alerts (
    alert_id SERIAL PRIMARY KEY,
    transaction_id VARCHAR(50),
    user_id INT,
    reason VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    feedback VARCHAR(20)  -- 'true_fraud', 'false_positive'
);

-- Model Registry
CREATE TABLE model_registry (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100),
    version VARCHAR(50),
    model_path VARCHAR(255),
    metrics JSONB,
    status VARCHAR(20),  -- 'training', 'testing', 'production'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deployed_at TIMESTAMP,
    traffic_percentage FLOAT DEFAULT 0.0
);
```

#### MinIO / S3 (Data Lake)
- **Version:** Latest
- **Purpose:** Long-term storage with ACID
- **Format:** Delta Lake (Parquet + transaction log)
- **Buckets:**
  - `lake/transactions/` - Raw transaction archive
  - `lake/ml_features/` - ML training features
  - `lake/checkpoints/` - Spark checkpoints
  - `lake/models/` - Model artifacts

**Delta Lake Benefits:**
- ✅ ACID transactions
- ✅ Time travel (query historical states)
- ✅ Schema evolution
- ✅ Upserts and deletes

---

### 4. ML Layer

#### Model Pipeline

```
┌─────────────────────┐
│  Feature Store      │
│  (PostgreSQL)       │
│  - User aggregates  │
│  - Geo features     │
│  - Temporal         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Model Training     │
│  - Isolation Forest │
│  - Random Forest    │
│  - Cross-validation │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Model Registry     │
│  (PostgreSQL)       │
│  - Versioning       │
│  - A/B testing      │
│  - Metrics tracking │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Inference          │
│  (Spark Streaming)  │
│  - Real-time scoring│
│  - Batch prediction │
└─────────────────────┘
```

**Models:**
1. **Isolation Forest** (Unsupervised)
   - Features: [amount, lat, lon]
   - Contamination: 0.1
   - Use: Anomaly detection

2. **Random Forest Classifier** (Supervised)
   - Features: [amount, lat, lon, hour, day, user_stats]
   - Class weight: Balanced
   - Use: Binary classification

**Retraining Schedule:**
- Frequency: Daily (Airflow DAG)
- Trigger: New feedback data available
- Promotion: Auto-promote if F1 > 0.7

**Implementation:** `src/model/training_pipeline.py`

---

### 5. Monitoring & Observability

#### Prometheus Metrics

**Categories:**
1. **Transaction Metrics**
   - `fraud_detection_transactions_total{status}`
   - `fraud_detection_alerts_total{rule_name, severity}`
   
2. **Performance Metrics**
   - `fraud_detection_processing_latency_seconds` (histogram)
   - `fraud_detection_event_lag_seconds` (gauge)
   - `fraud_detection_batch_size` (histogram)

3. **ML Metrics**
   - `fraud_detection_ml_predictions_total{prediction}`
   - `fraud_detection_ml_inference_latency_seconds`
   - `fraud_detection_model_score` (histogram)

4. **System Health**
   - `fraud_detection_system_health{component}` (kafka, redis, postgres, spark)

**Scrape Configuration:**
```yaml
scrape_configs:
  - job_name: 'fraud-detection'
    static_configs:
      - targets: ['fraud-detector:8000']
```

#### Grafana Dashboards

**Dashboard 1: Real-time Operations**
- TPS (Transactions per second)
- Alerts per minute
- Average latency
- Event lag

**Dashboard 2: Fraud Analytics**
- Detection rate by rule
- False positive rate
- Geographic heatmap
- Temporal patterns

**Dashboard 3: System Health**
- Component status
- Resource utilization
- Error rates
- State store size

---

## Data Flow Diagrams

### Fraud Detection Flow

```
┌──────────────┐
│ Transaction  │
│    Arrives   │
└──────┬───────┘
       │
       ▼
┌──────────────────────────┐
│  Schema Validation       │
│  (JSON Schema Registry)  │
└──────┬───────────────────┘
       │ Valid
       ▼
┌──────────────────────────┐
│  Hot Path Processing     │
│  - Load user state       │
│  - Apply fast rules      │
│  - ML inference          │
└──────┬───────────────────┘
       │
       ├─── Fraud? ──Yes──┐
       │                  │
       No                 ▼
       │           ┌──────────────┐
       │           │ Create Alert │
       │           │ Save to PG   │
       │           └──────────────┘
       │
       ▼
┌──────────────────────────┐
│  Update State (Redis)    │
│  - Save location         │
│  - Increment count       │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  Cold Path (Async)       │
│  - Save to Delta Lake    │
│  - Pattern detection     │
│  - Feature generation    │
└──────────────────────────┘
```

### Feedback Loop

```
┌──────────────┐
│   Analyst    │
│  Dashboard   │
└──────┬───────┘
       │ Review alert
       ▼
┌──────────────────────────┐
│  Mark as:                │
│  - True Fraud            │
│  - False Positive        │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  Update PostgreSQL       │
│  fraud_alerts.feedback   │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  Airflow Retraining DAG  │
│  (Triggered daily)       │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  Extract Features        │
│  from Labeled Data       │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  Train New Model         │
│  - Cross-validation      │
│  - Metrics tracking      │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  Register in Registry    │
│  with Version            │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  Auto-promote if         │
│  Metrics > Threshold     │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  Deploy to Production    │
│  (Rolling update)        │
└──────────────────────────┘
```

---

## Deployment Architecture

### Docker Compose (Development)
```
Services:
├── zookeeper        (2181)
├── kafka            (9092, 29092)
├── redis            (6379)
├── postgres         (5432)
├── spark-master     (8080, 7077)
├── spark-worker     (8081)
├── fraud-detector   (Spark app)
├── generator        (Python app)
├── dashboard        (8501)
├── prometheus       (9090)
├── grafana          (3000)
└── minio            (9000, 9001)
```

### Kubernetes (Production)

**Namespaces:**
- `fraud-detection-prod`
- `fraud-detection-staging`

**Deployments:**
- `kafka-cluster` (3 replicas)
- `redis-cluster` (3 masters, 3 replicas)
- `postgres-ha` (1 primary, 2 replicas)
- `spark-operator` (manages Spark jobs)
- `fraud-detector` (auto-scaling: 2-10 pods)
- `dashboard` (2 replicas)
- `monitoring` (Prometheus + Grafana)

**Storage:**
- `persistent-volume-claims` for PostgreSQL
- `s3-backed-storage` for Delta Lake (EKS/EFS)

**Helm Chart:** `k8s/fraud-detection-platform/`

---

## Performance Characteristics

| Metric | Hot Path | Cold Path |
|--------|----------|-----------|
| **Latency** | < 100ms (p99) | 5 min (batch) |
| **Throughput** | 500 TPS | Unlimited |
| **Rules** | 3 essential | All rules |
| **ML Models** | 1 (fast) | Multiple |
| **Storage** | PostgreSQL | Delta Lake |
| **Use Case** | Alerts | Analytics |

---

## Scalability

### Horizontal Scaling:
- **Kafka:** Increase partitions (3 → 12)
- **Spark:** Add workers (1 → 10)
- **Redis:** Cluster mode (sharding)
- **PostgreSQL:** Read replicas

### Vertical Scaling:
- **Spark Worker:** 1GB → 4GB RAM
- **Redis:** Increase memory limit
- **PostgreSQL:** More CPU cores

### Auto-scaling Triggers:
- CPU > 70%
- Kafka lag > 1000 messages
- Latency > 200ms

---

## Security

### Network:
- TLS for Kafka (production)
- Redis AUTH enabled
- PostgreSQL SSL required

### Authentication:
- Kafka SASL/SCRAM
- Redis password
- PostgreSQL role-based access

### Data Protection:
- PII encryption at rest
- Masked card numbers
- Audit logging

---

**Last Updated:** February 2026  
**Version:** 2.0.0
