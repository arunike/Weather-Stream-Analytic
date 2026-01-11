import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.ensemble import IsolationForest
import joblib
import s3fs
import json

# Configuration
POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'postgres')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'admin')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'password')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'fraud_detection')

MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', 'minio:9000')
MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', 'minioadmin')

MODEL_PATH = "/opt/airflow/src/model/isolation_forest.pkl" # Overwrite live model
# In a real system, we'd save to a registry like MLflow or S3 with versioning

def get_db_engine():
    return create_engine(f'postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}')

def load_feedback_data():
    """Load labeled data from Postgres (Feedback Loop)."""
    print("Loading feedback data from Postgres...")
    engine = get_db_engine()
    query = "SELECT amount, lat, lon, feedback FROM fraud_alerts WHERE feedback IS NOT NULL"
    df = pd.read_sql(query, engine)
    return df

def load_lake_data():
    """Load raw historical data from MinIO (Data Lake)."""
    print("Loading historical data from MinIO...")
    # Using s3fs to read parquet files directly from MinIO
    fs = s3fs.S3FileSystem(
        key=MINIO_ACCESS_KEY,
        secret=MINIO_SECRET_KEY,
        client_kwargs={'endpoint_url': 'http://' + MINIO_ENDPOINT},
        use_listings_cache=False
    )
    
    # Path to Delta Table (Parquet files inside)
    # Note: This is an approximation. A robust way is to use 'deltalake' lib.
    # For now, we blindly read parquet files in the folder.
    try:
        files = fs.glob("s3://lake/transactions/**/*.parquet")
        if not files:
            print("No data found in Data Lake.")
            return pd.DataFrame()
            
        dfs = []
        for f in files:
            # Read only relevant columns to save memory
            try:
                with fs.open(f, 'rb') as fp:
                    dfs.append(pd.read_parquet(fp, columns=['amount', 'location']))
            except Exception as e:
                print(f"Skipping file {f}: {e}")
                
        if not dfs:
             return pd.DataFrame()

        full_df = pd.concat(dfs)
        
        # Flatten location struct if necessary (depends on how parquet saved it)
        # Spark struct often saves as dict in pandas read_parquet logic or separate cols
        # Let's handle generic case: if 'location' is a dict/struct
        if 'location' in full_df.columns:
             # Basic extraction assuming it came back as a dict or similar
             full_df['lat'] = full_df['location'].apply(lambda x: x.get('lat') if x else 0.0)
             full_df['lon'] = full_df['location'].apply(lambda x: x.get('lon') if x else 0.0)
             full_df = full_df.drop(columns=['location'])
             
        return full_df[['amount', 'lat', 'lon']]
        
    except Exception as e:
        print(f"Error reading Lake: {e}")
        return pd.DataFrame()

def train_model():
    print("Starting Model Retraining Workflow...")
    
    # 1. Load Data
    lake_df = load_lake_data()
    feedback_df = load_feedback_data()
    
    print(f"Lake Data: {len(lake_df)} rows")
    print(f"Feedback Data: {len(feedback_df)} rows")
    
    if lake_df.empty and feedback_df.empty:
        print("No data available for training. Exiting.")
        return

    # 2. Preprocessing
    # In a real scenario, we would treat 'True Fraud' as anomalies (-1) and 'False Positive' as normal (1)
    # IsolationForest is unsupervised, but we can enrich the train set with "normal" feedback to reduce false positives.
    
    # Combine datasets (blindly for unsupervised IF, it assumes majority is normal)
    # Ideally: exclude 'True Fraud' from the training set of IF to make it 'cleaner' of anomalies, 
    # OR include them and ensure the contamination parameter handles it.
    
    # Strategy: Train primarily on Lake Data (assuming mostly normal) + False Positives (known normal)
    train_df = lake_df.copy()
    
    if not feedback_df.empty:
        # False Positives are confirmed normal, good to add to training "normal" distribution
        normals = feedback_df[feedback_df['feedback'] == 'False Positive'][['amount', 'lat', 'lon']]
        train_df = pd.concat([train_df, normals])
        
    # Handle NaN
    train_df = train_df.fillna(0)
    
    if train_df.empty:
        print("Training set empty.")
        return

    # 3. Train Isolation Forest
    X = train_df[['amount', 'lat', 'lon']].values
    clf = IsolationForest(n_estimators=100, contamination=0.01, random_state=42)
    clf.fit(X)
    
    # 4. Evaluation (Basic)
    print("Model trained successfully.")
    
    # 5. Save Model
    print(f"Saving model to {MODEL_PATH}...")
    joblib.dump(clf, MODEL_PATH)
    print("Model saved! 🚀")

if __name__ == "__main__":
    train_model()
