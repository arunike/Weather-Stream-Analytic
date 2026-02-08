import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class Environment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"

@dataclass
class KafkaConfig:
    bootstrap_servers: str = field(
        default_factory=lambda: os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    )
    topic_transactions: str = field(
        default_factory=lambda: os.getenv("KAFKA_TOPIC_TRANSACTIONS", "transactions")
    )
    topic_alerts: str = field(
        default_factory=lambda: os.getenv("KAFKA_TOPIC_ALERTS", "fraud_alerts")
    )
    consumer_group: str = field(
        default_factory=lambda: os.getenv("KAFKA_CONSUMER_GROUP", "fraud_detector")
    )
    auto_offset_reset: str = field(
        default_factory=lambda: os.getenv("KAFKA_AUTO_OFFSET_RESET", "latest")
    )
    enable_auto_commit: bool = field(
        default_factory=lambda: os.getenv("KAFKA_ENABLE_AUTO_COMMIT", "false").lower() == "true"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.consumer_group,
            "auto.offset.reset": self.auto_offset_reset,
            "enable.auto.commit": self.enable_auto_commit
        }

@dataclass
class RedisConfig:
    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "redis"))
    port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    db: int = field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))
    password: Optional[str] = field(default_factory=lambda: os.getenv("REDIS_PASSWORD"))
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    max_connections: int = 50
    
    def get_connection_params(self) -> Dict[str, Any]:
        params = {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "socket_timeout": self.socket_timeout,
            "socket_connect_timeout": self.socket_connect_timeout,
            "max_connections": self.max_connections
        }
        if self.password:
            params["password"] = self.password
        return params

@dataclass
class PostgresConfig:
    host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "postgres"))
    port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    database: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "fraud_detection"))
    user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "admin"))
    password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "password"))
    min_conn: int = 1
    max_conn: int = 10
    
    def get_connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    def get_sqlalchemy_uri(self) -> str:
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

@dataclass
class SparkConfig:
    master: str = field(default_factory=lambda: os.getenv("SPARK_MASTER", "local[*]"))
    app_name: str = field(default_factory=lambda: os.getenv("SPARK_APP_NAME", "FraudDetector"))
    log_level: str = field(default_factory=lambda: os.getenv("SPARK_LOG_LEVEL", "WARN"))
    checkpoint_location: str = field(
        default_factory=lambda: os.getenv("SPARK_CHECKPOINT_LOCATION", "s3a://lake/checkpoints")
    )
    
    # Delta Lake
    enable_delta: bool = field(
        default_factory=lambda: os.getenv("SPARK_ENABLE_DELTA", "true").lower() == "true"
    )
    delta_table_path: str = field(
        default_factory=lambda: os.getenv("DELTA_TABLE_PATH", "s3a://lake/transactions")
    )
    
    def get_spark_conf(self) -> Dict[str, str]:
        conf = {
            "spark.master": self.master,
            "spark.sql.streaming.checkpointLocation": self.checkpoint_location
        }
        
        if self.enable_delta:
            conf.update({
                "spark.sql.extensions": "io.delta.sql.DeltaSparkSessionExtension",
                "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.delta.catalog.DeltaCatalog"
            })
        
        return conf

@dataclass
class MinIOConfig:
    endpoint: str = field(default_factory=lambda: os.getenv("MINIO_ENDPOINT", "minio:9000"))
    access_key: str = field(default_factory=lambda: os.getenv("MINIO_ACCESS_KEY", "minioadmin"))
    secret_key: str = field(default_factory=lambda: os.getenv("MINIO_SECRET_KEY", "minioadmin"))
    bucket: str = field(default_factory=lambda: os.getenv("MINIO_BUCKET", "lake"))
    use_ssl: bool = field(default_factory=lambda: os.getenv("MINIO_USE_SSL", "false").lower() == "true")
    
    def get_s3_config(self) -> Dict[str, str]:
        return {
            "spark.hadoop.fs.s3a.endpoint": f"http://{self.endpoint}",
            "spark.hadoop.fs.s3a.access.key": self.access_key,
            "spark.hadoop.fs.s3a.secret.key": self.secret_key,
            "spark.hadoop.fs.s3a.path.style.access": "true",
            "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
            "spark.hadoop.fs.s3a.connection.ssl.enabled": str(self.use_ssl).lower()
        }

@dataclass
class MLConfig:
    model_dir: str = field(default_factory=lambda: os.getenv("ML_MODEL_DIR", "src/model"))
    model_name: str = field(default_factory=lambda: os.getenv("ML_MODEL_NAME", "isolation_forest"))
    enable_ml: bool = field(default_factory=lambda: os.getenv("ML_ENABLE", "true").lower() == "true")
    inference_batch_size: int = field(default_factory=lambda: int(os.getenv("ML_BATCH_SIZE", "100")))
    model_version: Optional[str] = field(default_factory=lambda: os.getenv("ML_MODEL_VERSION"))
    
    def get_model_path(self, version: Optional[str] = None) -> str:
        ver = version or self.model_version or "latest"
        return f"{self.model_dir}/{self.model_name}_{ver}.pkl"

@dataclass
class MonitoringConfig:
    enable_prometheus: bool = field(
        default_factory=lambda: os.getenv("MONITORING_PROMETHEUS", "true").lower() == "true"
    )
    prometheus_port: int = field(default_factory=lambda: int(os.getenv("PROMETHEUS_PORT", "8000")))
    enable_logging: bool = field(default_factory=lambda: True)
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_format: str = field(
        default_factory=lambda: os.getenv("LOG_FORMAT", "structured")  # structured or standard
    )

@dataclass
class FraudDetectionConfig:
    environment: Environment = field(
        default_factory=lambda: Environment(os.getenv("ENVIRONMENT", "development"))
    )
    
    # Sub-configurations
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    spark: SparkConfig = field(default_factory=SparkConfig)
    minio: MinIOConfig = field(default_factory=MinIOConfig)
    ml: MLConfig = field(default_factory=MLConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    # Rule thresholds
    high_amount_threshold: float = field(
        default_factory=lambda: float(os.getenv("RULE_HIGH_AMOUNT_THRESHOLD", "2000.0"))
    )
    geo_velocity_threshold_kmh: float = field(
        default_factory=lambda: float(os.getenv("RULE_GEO_VELOCITY_THRESHOLD", "800.0"))
    )
    frequency_threshold_per_hour: int = field(
        default_factory=lambda: int(os.getenv("RULE_FREQUENCY_THRESHOLD", "10"))
    )
    
    # Processing configuration
    enable_hot_path: bool = field(
        default_factory=lambda: os.getenv("ENABLE_HOT_PATH", "true").lower() == "true"
    )
    enable_cold_path: bool = field(
        default_factory=lambda: os.getenv("ENABLE_COLD_PATH", "true").lower() == "true"
    )
    
    def validate(self) -> bool:
        try:
            # Validate thresholds
            assert self.high_amount_threshold > 0, "High amount threshold must be positive"
            assert self.geo_velocity_threshold_kmh > 0, "Geo velocity threshold must be positive"
            assert self.frequency_threshold_per_hour > 0, "Frequency threshold must be positive"
            
            # Validate connections can be established
            if self.environment == Environment.PRODUCTION:
                assert self.redis.password is not None, "Redis password required in production"
            
            logger.info("Configuration validation passed")
            return True
            
        except AssertionError as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment": self.environment.value,
            "kafka": {
                "bootstrap_servers": self.kafka.bootstrap_servers,
                "topics": {
                    "transactions": self.kafka.topic_transactions,
                    "alerts": self.kafka.topic_alerts
                }
            },
            "redis": {
                "host": self.redis.host,
                "port": self.redis.port
            },
            "postgres": {
                "host": self.postgres.host,
                "database": self.postgres.database
            },
            "spark": {
                "master": self.spark.master,
                "checkpoint": self.spark.checkpoint_location
            },
            "ml": {
                "enabled": self.ml.enable_ml,
                "model": self.ml.model_name
            },
            "rules": {
                "high_amount_threshold": self.high_amount_threshold,
                "geo_velocity_threshold_kmh": self.geo_velocity_threshold_kmh,
                "frequency_threshold_per_hour": self.frequency_threshold_per_hour
            }
        }

# Global configuration instance
_config_instance: Optional[FraudDetectionConfig] = None

def get_config() -> FraudDetectionConfig:
    global _config_instance
    if _config_instance is None:
        _config_instance = FraudDetectionConfig()
        _config_instance.validate()
    return _config_instance

def reload_config():
    global _config_instance
    _config_instance = FraudDetectionConfig()
    _config_instance.validate()
    logger.info("Configuration reloaded")
