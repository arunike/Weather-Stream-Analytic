from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, struct, to_json
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType, LongType
from delta import *
import redis
import psycopg2
import math
import json
import time
import os

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BROKER', "kafka:9092")
REDIS_HOST = "redis"
POSTGRES_HOST = "postgres"
POSTGRES_DB = "fraud_detection"
POSTGRES_USER = "admin"
POSTGRES_PASSWORD = "password"

# Schema for incoming JSON data
schema = StructType([
    StructField("transaction_id", StringType()),
    StructField("user_id", IntegerType()),
    StructField("card_number", StringType()),
    StructField("timestamp", DoubleType()),
    StructField("amount", DoubleType()),
    StructField("currency", StringType()),
    StructField("merchant_id", IntegerType()),
    StructField("location", StructType([
        StructField("lat", DoubleType()),
        StructField("lon", DoubleType()),
        StructField("city", StringType()),
        StructField("country", StringType())
    ]))
])

def get_redis_connection():
    return redis.Redis(host=REDIS_HOST, port=6379, db=0)

def get_postgres_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

def setup_postgres():
    """Ensure the alerts table exists."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fraud_alerts (
                alert_id SERIAL PRIMARY KEY,
                transaction_id VARCHAR(50),
                user_id INT,
                reason VARCHAR(255),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT,
                lat DOUBLE PRECISION,
                lon DOUBLE PRECISION,
                feedback VARCHAR(20)
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("PostgreSQL initialized.")
    except Exception as e:
        print(f"Error initializing Postgres: {e}")

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in km."""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def process_batch(df, epoch_id):
    """
    Process a batch of transactions.
    """
    transactions = df.collect()
    if not transactions:
        return

    r = get_redis_connection()
    pg_conn = get_postgres_connection()
    pg_cur = pg_conn.cursor()
    
    print(f"Processing batch {epoch_id} with {len(transactions)} transactions...")
    
    # Load Model (Lazy loading or global)
    ml_enabled = False
    try:
        import joblib
        import numpy as np
        # Load from local path (mounted volume)
        if os.path.exists("src/model/isolation_forest.pkl"):
            model = joblib.load("src/model/isolation_forest.pkl")
            ml_enabled = True
    except Exception as e:
        print(f"ML Model error: {e}")

    for row in transactions:
        txn = row.asDict(recursive=True)
        user_id = txn['user_id']
        current_lat = txn['location']['lat']
        current_lon = txn['location']['lon']
        current_ts = txn['timestamp']
        amount = txn['amount']
        
        # Rule 0: ML Anomaly Detection
        if ml_enabled:
            # Features: [amount, lat, lon]
            features = np.array([[amount, current_lat, current_lon]])
            prediction = model.predict(features)[0] # -1 for outlier
            score = model.decision_function(features)[0]
            
            if prediction == -1:
                print(f"ML ANOMALY: Score {score:.2f} for user {user_id}")
                pg_cur.execute(
                     "INSERT INTO fraud_alerts (transaction_id, user_id, reason, details, lat, lon) VALUES (%s, %s, %s, %s, %s, %s)",
                     (txn['transaction_id'], user_id, "ML Anomaly Detected", f"Score: {score:.2f}", current_lat, current_lon)
                 )

        # Rule 1: High Amount
        if amount > 2000:
             print(f"FRAUD DETECTED: High Amount {amount} for user {user_id}")
             pg_cur.execute(
                 "INSERT INTO fraud_alerts (transaction_id, user_id, reason, details, lat, lon) VALUES (%s, %s, %s, %s, %s, %s)",
                 (txn['transaction_id'], user_id, "High Value Transaction", f"Amount: {amount}", current_lat, current_lon)
             )
        
        # Rule 2: Impossible Travel (Geo-Velocity)
        last_data_json = r.get(f"user_loc:{user_id}")
        if last_data_json:
            last_data = json.loads(last_data_json)
            last_lat = last_data['lat']
            last_lon = last_data['lon']
            last_ts = last_data['ts']
            
            distance_km = haversine(last_lat, last_lon, current_lat, current_lon)
            time_diff_hours = (current_ts - last_ts) / 3600.0
            
            if time_diff_hours > 0:
                speed = distance_km / time_diff_hours
                if speed > 800 and distance_km > 50:
                    print(f"FRAUD DETECTED: Impossible Travel! Speed: {speed:.2f} km/h")
                    pg_cur.execute(
                        "INSERT INTO fraud_alerts (transaction_id, user_id, reason, details, lat, lon) VALUES (%s, %s, %s, %s, %s, %s)",
                        (txn['transaction_id'], user_id, "Impossible Travel", f"Speed: {speed:.2f} km/h, Dist: {distance_km:.2f} km", current_lat, current_lon)
                    )

        # Update Redis
        new_state = {
            "lat": current_lat,
            "lon": current_lon,
            "ts": current_ts
        }
        r.set(f"user_loc:{user_id}", json.dumps(new_state))
        
    pg_conn.commit()
    pg_cur.close()
    pg_conn.close()

def main():
    # Spark with Delta and S3 support
    builder = SparkSession.builder \
        .appName("FraudDetector") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,io.delta:delta-spark_2.12:3.0.0,org.apache.hadoop:hadoop-aws:3.3.4") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")

    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    
    # Initialize Postgres table
    time.sleep(10)
    setup_postgres()

    # Read from Kafka
    df = spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", "transactions") \
        .option("startingOffsets", "latest") \
        .load()

    # Parse JSON
    json_df = df.select(from_json(col("value").cast("string"), schema).alias("data")).select("data.*")
    
    # 1. Archive to Data Lake (MinIO)
    try:
        query_lake = json_df.writeStream \
            .format("delta") \
            .outputMode("append") \
            .option("checkpointLocation", "/tmp/delta_checkpoint") \
            .option("path", "s3a://lake/transactions") \
            .start()
    except Exception as e:
        print(f"Warning: Could not start Delta Lake stream: {e}")

    # 2. Real-time Fraud Detection
    query_fraud = json_df.writeStream \
        .outputMode("append") \
        .foreachBatch(process_batch) \
        .start()

    spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    main()
