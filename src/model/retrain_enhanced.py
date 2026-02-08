import numpy as np
import pandas as pd
import psycopg2
import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment
POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'postgres')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'fraud_detection')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'admin')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'password')

def get_postgres_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

def get_db_engine():
    return create_engine(
        f'postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}'
    )

def extract_features(lookback_days: int = 30) -> pd.DataFrame:
    logger.info(f"Extracting features from last {lookback_days} days...")
    
    engine = get_db_engine()
    query = f"""
    SELECT 
        transaction_id,
        user_id,
        lat,
        lon,
        details,
        feedback,
        timestamp
    FROM fraud_alerts
    WHERE timestamp >= NOW() - INTERVAL '{lookback_days} days'
    AND feedback IS NOT NULL
    """
    
    df = pd.read_sql(query, engine)
    
    # Parse amount from details
    df['amount'] = df['details'].str.extract(r'Amount: ([\d.]+)|Score: ([-\d.]+)').fillna(0).sum(axis=1).astype(float)
    
    # Create label
    df['label'] = (df['feedback'] == 'true_fraud').astype(int)
    
    logger.info(f"Extracted {len(df)} samples with {df['label'].sum()} fraud cases")
    return df

def train_models():
    logger.info("Starting model retraining with feedback data...")
    
    try:
        from sklearn.ensemble import IsolationForest
        import joblib
        
        # Extract features
        df = extract_features(lookback_days=30)
        
        if len(df) < 100:
            logger.warning(f"Insufficient training data: {len(df)} samples. Skipping training.")
            return
        
        # Prepare features
        X = df[['amount', 'lat', 'lon']].fillna(0).values
        
        # Train Isolation Forest
        logger.info("Training Isolation Forest...")
        model = IsolationForest(
            n_estimators=100,
            contamination=0.1,
            random_state=42
        )
        model.fit(X)
        
        # Save model
        model_path = "/opt/airflow/src/model/isolation_forest.pkl"
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)
        
        logger.info(f"Model saved to {model_path}")
        logger.info("Model retraining completed successfully!")
        
    except Exception as e:
        logger.error(f"Model retraining failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    train_models()
