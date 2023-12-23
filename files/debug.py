from kafka import KafkaConsumer
from report_pb2 import Report

broker = 'localhost:9092'

consumer = KafkaConsumer(bootstrap_servers = broker)
consumer.subscribe(["temperatures"])

for message in consumer:
    report = Report.FromString(message.value)

    output = {
        "partition": message.partition,
        "key": message.key.decode('utf-8') if message.key else "None",
        "date": report.date,
        "degrees": report.degrees
    }
    
    print(output)
