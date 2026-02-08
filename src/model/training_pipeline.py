import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    classification_report
)
import joblib
import json
import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from pathlib import Path
import psycopg2

logger = logging.getLogger(__name__)

class FeatureStore:
    def __init__(self, postgres_conn):
        self.conn = postgres_conn
        self.logger = logging.getLogger(__name__)
    
    def extract_features(self, lookback_days: int = 30) -> pd.DataFrame:
        query = f"""
        SELECT 
            fa.transaction_id,
            fa.user_id,
            fa.lat,
            fa.lon,
            fa.details,
            fa.feedback,
            EXTRACT(EPOCH FROM fa.timestamp) as timestamp,
            fa.reason
        FROM fraud_alerts fa
        WHERE fa.timestamp >= NOW() - INTERVAL '{lookback_days} days'
        AND fa.feedback IS NOT NULL
        """
        
        df = pd.read_sql(query, self.conn)
        
        # Parse amount from details (format: "Amount: X" or "Score: X")
        df['amount'] = df['details'].str.extract(r'Amount: ([\d.]+)').astype(float).fillna(0)
        df['ml_score'] = df['details'].str.extract(r'Score: ([-\d.]+)').astype(float).fillna(0)
        df['speed_kmh'] = df['details'].str.extract(r'Speed: ([\d.]+)').astype(float).fillna(0)
        
        # Create label: 1 for true fraud, 0 for false positive
        df['label'] = (df['feedback'] == 'true_fraud').astype(int)
        
        # Feature engineering
        df['hour_of_day'] = pd.to_datetime(df['timestamp'], unit='s').dt.hour
        df['day_of_week'] = pd.to_datetime(df['timestamp'], unit='s').dt.dayofweek
        
        # Aggregate features per user
        user_stats = df.groupby('user_id').agg({
            'amount': ['mean', 'std', 'max'],
            'transaction_id': 'count'
        }).reset_index()
        user_stats.columns = ['user_id', 'user_avg_amount', 'user_std_amount', 
                               'user_max_amount', 'user_txn_count']
        
        df = df.merge(user_stats, on='user_id', how='left')
        
        self.logger.info(f"Extracted {len(df)} samples with {df['label'].sum()} fraud cases")
        return df
    
    def save_features(self, df: pd.DataFrame, feature_set_name: str):
        output_path = Path(f"data/features/{feature_set_name}.parquet")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False)
        self.logger.info(f"Saved feature set to {output_path}")

class ModelTrainer:
    def __init__(self, model_dir: str = "src/model"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def train_isolation_forest(
        self,
        X_train: np.ndarray,
        contamination: float = 0.1
    ) -> Tuple[IsolationForest, Dict[str, float]]:
        self.logger.info("Training Isolation Forest...")
        
        model = IsolationForest(
            n_estimators=100,
            max_samples='auto',
            contamination=contamination,
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_train)
        
        # Calculate anomaly scores
        scores = model.decision_function(X_train)
        predictions = model.predict(X_train)
        
        metrics = {
            "anomaly_count": int((predictions == -1).sum()),
            "normal_count": int((predictions == 1).sum()),
            "mean_score": float(scores.mean()),
            "std_score": float(scores.std())
        }
        
        self.logger.info(f"Isolation Forest metrics: {metrics}")
        return model, metrics
    
    def train_supervised_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray
    ) -> Tuple[RandomForestClassifier, Dict[str, float]]:
        self.logger.info("Training Random Forest Classifier...")
        
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=20,
            min_samples_leaf=10,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_train, y_train)
        
        # Evaluate on validation set
        y_pred = model.predict(X_val)
        y_proba = model.predict_proba(X_val)[:, 1]
        
        metrics = {
            "precision": float(precision_score(y_val, y_pred)),
            "recall": float(recall_score(y_val, y_pred)),
            "f1_score": float(f1_score(y_val, y_pred)),
            "roc_auc": float(roc_auc_score(y_val, y_proba))
        }
        
        # Cross-validation score
        cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='f1')
        metrics["cv_f1_mean"] = float(cv_scores.mean())
        metrics["cv_f1_std"] = float(cv_scores.std())
        
        self.logger.info(f"Model metrics: {metrics}")
        self.logger.info(f"\n{classification_report(y_val, y_pred)}")
        
        return model, metrics
    
    def save_model(
        self,
        model: Any,
        metrics: Dict[str, float],
        model_name: str = "fraud_model",
        version: Optional[str] = None
    ) -> str:
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        model_path = self.model_dir / f"{model_name}_v{version}.pkl"
        metadata_path = self.model_dir / f"{model_name}_v{version}_metadata.json"
        
        # Save model
        joblib.dump(model, model_path)
        self.logger.info(f"Saved model to {model_path}")
        
        # Save metadata
        metadata = {
            "model_name": model_name,
            "version": version,
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
            "model_type": type(model).__name__
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.info(f"Saved metadata to {metadata_path}")
        
        # Update "latest" symlink
        latest_path = self.model_dir / f"{model_name}_latest.pkl"
        if latest_path.exists():
            latest_path.unlink()
        latest_path.symlink_to(model_path.name)
        
        return version
    
    def load_model(self, model_name: str, version: str = "latest") -> Tuple[Any, Dict[str, Any]]:
        if version == "latest":
            model_path = self.model_dir / f"{model_name}_latest.pkl"
        else:
            model_path = self.model_dir / f"{model_name}_v{version}.pkl"
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        model = joblib.load(model_path)
        
        # Load metadata
        if version == "latest":
            # Resolve symlink to get actual version
            actual_path = model_path.resolve()
            version = actual_path.stem.split('_v')[1]
        
        metadata_path = self.model_dir / f"{model_name}_v{version}_metadata.json"
        with open(metadata_path) as f:
            metadata = json.load(f)
        
        return model, metadata

class ModelRegistry:
    def __init__(self, postgres_conn):
        self.conn = postgres_conn
        self._setup_registry_table()
    
    def _setup_registry_table(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_registry (
                id SERIAL PRIMARY KEY,
                model_name VARCHAR(100),
                version VARCHAR(50),
                model_path VARCHAR(255),
                metrics JSONB,
                status VARCHAR(20), -- training, testing, production, archived
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deployed_at TIMESTAMP,
                traffic_percentage FLOAT DEFAULT 0.0
            );
        """)
        self.conn.commit()
    
    def register_model(
        self,
        model_name: str,
        version: str,
        model_path: str,
        metrics: Dict[str, float],
        status: str = "training"
    ):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO model_registry 
            (model_name, version, model_path, metrics, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (model_name, version, model_path, json.dumps(metrics), status))
        self.conn.commit()
    
    def promote_to_production(self, model_name: str, version: str):
        cursor = self.conn.cursor()
        
        # Set current production to archived
        cursor.execute("""
            UPDATE model_registry
            SET status = 'archived', traffic_percentage = 0.0
            WHERE model_name = %s AND status = 'production'
        """, (model_name,))
        
        # Promote new version
        cursor.execute("""
            UPDATE model_registry
            SET status = 'production', deployed_at = NOW(), traffic_percentage = 100.0
            WHERE model_name = %s AND version = %s
        """, (model_name, version))
        
        self.conn.commit()
    
    def get_production_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT model_name, version, model_path, metrics, deployed_at
            FROM model_registry
            WHERE model_name = %s AND status = 'production'
        """, (model_name,))
        
        row = cursor.fetchone()
        if row:
            return {
                "model_name": row[0],
                "version": row[1],
                "model_path": row[2],
                "metrics": row[3],
                "deployed_at": row[4]
            }
        return None
