import time
import json
import random
import os
from kafka import KafkaProducer
from faker import Faker

# Configuration
KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka:9092')
TOPIC = 'transactions'

# Initialize Faker
fake = Faker()

def create_transaction():
    # Simulate a user from a limited set to allow 'history' to build up
    user_id = random.randint(1, 100)
    
    # 5% chance of a "teleportation" attack (Impossible Travel)
    # We simulate this by NOT updating the location logically, or moving too fast?
    # Actually, simpler: The detector will flag if this txn is far from the last one.
    # So we just generate random locations. To make it "normal", we should stick to a region?
    # For now, let's just be random.
    
    transaction = {
        "transaction_id": fake.uuid4(),
        "user_id": user_id,
        "card_number": fake.credit_card_number(card_type="mastercard"),
        "timestamp": time.time(),
        "amount": round(random.uniform(5.0, 500.0), 2),
        "currency": "USD",
        "merchant_id": random.randint(1000, 9999),
        "location": {
            "lat": float(fake.latitude()),
            "lon": float(fake.longitude()),
            "city": fake.city(),
            "country": fake.country()
        }
    }
    
    # Inject high value fraud (Amount > 450)
    if random.random() < 0.05:
        transaction['amount'] = round(random.uniform(1000.0, 5000.0), 2)
        
    return transaction

def main():
    print(f"Connecting to Kafka at {KAFKA_BROKER}...")
    producer = None
    for i in range(10):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print("Connected to Kafka!")
            break
        except Exception as e:
            print(f"Retrying connection... {e}")
            time.sleep(5)
            
    if not producer:
        print("Failed to connect to Kafka. Exiting.")
        return

    print("Starting transaction stream...")
    while True:
        txn = create_transaction()
        producer.send(TOPIC, txn)
        print(f"Sent: {txn['transaction_id']} | User: {txn['user_id']} | Amount: ${txn['amount']}")
        
        # Simulate high throughput (approx 50-100 TPS)
        time.sleep(0.01)

if __name__ == "__main__":
    main()
