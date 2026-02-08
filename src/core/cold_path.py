import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd
from pyspark.sql import SparkSession, DataFrame

logger = logging.getLogger(__name__)

@dataclass
class ColdPathConfig:
    batch_interval_seconds: int = 300  # 5 minutes
    enable_ml: bool = True
    enable_all_rules: bool = True
    enable_pattern_detection: bool = True
    delta_lake_path: str = "s3a://lake/transactions"
    checkpoint_location: str = "s3a://lake/checkpoints/cold_path"

class ColdPathProcessor:
    def __init__(
        self,
        spark: SparkSession,
        config: Optional[ColdPathConfig] = None
    ):
        self.spark = spark
        self.config = config or ColdPathConfig()
        self.logger = logging.getLogger(__name__)
    
    def process_batch(
        self,
        transactions: DataFrame,
        epoch_id: int
    ):
        self.logger.info(f"Processing cold path batch {epoch_id}")
        
        # Convert to Pandas for complex analysis
        df = transactions.toPandas()
        
        if len(df) == 0:
            return
        
        # Apply all detection rules
        results = self._apply_all_rules(df)
        
        # Pattern detection
        if self.config.enable_pattern_detection:
            patterns = self._detect_patterns(df)
            self.logger.info(f"Detected {len(patterns)} patterns")
        
        # Save to Delta Lake
        self._save_to_delta_lake(df, epoch_id)
        
        # Generate features for ML
        if self.config.enable_ml:
            features = self._generate_ml_features(df)
            self._save_features(features, epoch_id)
    
    def _apply_all_rules(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        from src.core.rules import (
            FraudRuleEngine,
            HighAmountRule,
            ImpossibleTravelRule,
            FrequencyRule,
            MLAnomalyRule
        )
        
        engine = FraudRuleEngine()
        engine.add_rule(HighAmountRule(threshold=2000.0))
        engine.add_rule(ImpossibleTravelRule(max_speed_kmh=800))
        engine.add_rule(FrequencyRule(max_transactions_per_hour=10))
        
        if self.config.enable_ml:
            engine.add_rule(MLAnomalyRule(
                model_path="src/model/isolation_forest_latest.pkl"
            ))
        
        results = []
        for _, row in df.iterrows():
            transaction = row.to_dict()
            detections = engine.evaluate_transaction(transaction, context={})
            if detections:
                results.extend(detections)
        
        return results
    
    def _detect_patterns(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        patterns = []
        
        # Geographic clustering
        from sklearn.cluster import DBSCAN
        
        coords = df[['lat', 'lon']].values
        clustering = DBSCAN(eps=0.5, min_samples=5).fit(coords)
        
        # Find suspicious clusters
        for label in set(clustering.labels_):
            if label == -1:
                continue
            
            cluster_size = (clustering.labels_ == label).sum()
            if cluster_size > 10:  # Suspicious cluster
                patterns.append({
                    "type": "geographic_cluster",
                    "cluster_id": int(label),
                    "size": int(cluster_size),
                    "timestamp": datetime.now().isoformat()
                })
        
        # Temporal patterns (bursts of activity)
        df['hour'] = pd.to_datetime(df['timestamp'], unit='s').dt.hour
        hourly_counts = df.groupby('hour').size()
        
        if hourly_counts.max() > hourly_counts.mean() * 3:
            patterns.append({
                "type": "temporal_burst",
                "peak_hour": int(hourly_counts.idxmax()),
                "peak_count": int(hourly_counts.max()),
                "avg_count": float(hourly_counts.mean())
            })
        
        return patterns
    
    def _generate_ml_features(self, df: pd.DataFrame) -> pd.DataFrame:
        features = df.copy()
        
        # Temporal features
        features['hour_of_day'] = pd.to_datetime(df['timestamp'], unit='s').dt.hour
        features['day_of_week'] = pd.to_datetime(df['timestamp'], unit='s').dt.dayofweek
        features['is_weekend'] = features['day_of_week'].isin([5, 6]).astype(int)
        
        # User aggregates
        user_stats = df.groupby('user_id').agg({
            'amount': ['mean', 'std', 'max', 'count']
        }).reset_index()
        user_stats.columns = ['user_id', 'user_avg_amount', 'user_std_amount',
                               'user_max_amount', 'user_txn_count']
        
        features = features.merge(user_stats, on='user_id', how='left')
        
        # Geographic features (distance from user's typical location)
        user_geo = df.groupby('user_id')[['lat', 'lon']].mean().reset_index()
        user_geo.columns = ['user_id', 'user_typical_lat', 'user_typical_lon']
        
        features = features.merge(user_geo, on='user_id', how='left')
        
        return features
    
    def _save_to_delta_lake(self, df: pd.DataFrame, epoch_id: int):
        try:
            spark_df = self.spark.createDataFrame(df)
            
            # Write to Delta Lake
            spark_df.write \
                .format("delta") \
                .mode("append") \
                .save(self.config.delta_lake_path)
            
            self.logger.info(f"Saved {len(df)} records to Delta Lake")
            
        except Exception as e:
            self.logger.error(f"Failed to save to Delta Lake: {e}")
    
    def _save_features(self, features: pd.DataFrame, epoch_id: int):
        feature_path = f"s3a://lake/ml_features/epoch_{epoch_id}"
        
        try:
            spark_df = self.spark.createDataFrame(features)
            spark_df.write \
                .mode("overwrite") \
                .parquet(feature_path)
            
            self.logger.info(f"Saved features to {feature_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save features: {e}")
    
    def run_historical_analysis(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        self.logger.info(f"Running historical analysis: {start_date} to {end_date}")
        
        # Read from Delta Lake
        df = self.spark.read \
            .format("delta") \
            .load(self.config.delta_lake_path)
        
        # Filter by date range
        df = df.filter(
            (df.timestamp >= start_date.timestamp()) &
            (df.timestamp <= end_date.timestamp())
        )
        
        # Compute statistics
        stats = {
            "total_transactions": df.count(),
            "unique_users": df.select("user_id").distinct().count(),
            "avg_amount": df.selectExpr("avg(amount)").collect()[0][0],
            "max_amount": df.selectExpr("max(amount)").collect()[0][0],
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
        
        self.logger.info(f"Historical analysis results: {stats}")
        return stats
    
    def get_metrics(self) -> Dict[str, Any]:
        return {
            "path": "cold",
            "batch_interval_seconds": self.config.batch_interval_seconds,
            "delta_lake_path": self.config.delta_lake_path
        }
