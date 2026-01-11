import json
import time
from kafka import KafkaProducer

# Connect to External port (since we are running this from Host)
BROKER = 'localhost:29092' 
TOPIC = 'transactions'

def send_fraud():
    producer = KafkaProducer(
        bootstrap_servers=BROKER,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    user_id = 999
    
    # 1. Transaction in Paris
    txn1 = {
        "transaction_id": "manual-1",
        "user_id": user_id,
        "card_number": "1234-5678-9012-3456",
        "timestamp": time.time(),
        "amount": 100.0,
        "currency": "USD",
        "merchant_id": 1001,
        "location": {"lat": 48.8566, "lon": 2.3522, "city": "Paris", "country": "France"}
    }
    producer.send(TOPIC, txn1)
    print(f"Sent Txn 1: Paris (User {user_id})")
    
    # 2. Transaction in New York (1 second later -> IMPOSSIBLE TRAVEL)
    time.sleep(1)
    txn2 = {
        "transaction_id": "manual-2",
        "user_id": user_id,
        "card_number": "1234-5678-9012-3456",
        "timestamp": time.time(),
        "amount": 200.0,
        "currency": "USD",
        "merchant_id": 1002,
        "location": {"lat": 40.7128, "lon": -74.0060, "city": "New York", "country": "USA"}
    }
    producer.send(TOPIC, txn2)
    print(f"Sent Txn 2: New York (User {user_id}) - Should trigger ALERT!")
    
    # 3. High Value 
    txn3 = {
        "transaction_id": "manual-3",
        "user_id": user_id,
        "card_number": "1234-5678-9012-3456",
        "timestamp": time.time(),
        "amount": 5000.0,
        "currency": "USD",
        "merchant_id": 1002,
        "location": {"lat": 40.7128, "lon": -74.0060, "city": "New York", "country": "USA"}
    }
    producer.send(TOPIC, txn3)
    print(f"Sent Txn 3: $5000 (User {user_id}) - Should trigger ALERT!")
    
    producer.flush()

if __name__ == "__main__":
    try:
        send_fraud()
        print("\nDone! Check the dashboard at http://localhost:8501")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure Docker is running and Kafka is accessible at localhost:29092")
