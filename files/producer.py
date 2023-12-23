from kafka import KafkaAdminClient, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import UnknownTopicOrPartitionError, TopicAlreadyExistsError
import time
import weather
from report_pb2 import Report

broker = 'localhost:9092'
admin_client = KafkaAdminClient(bootstrap_servers=[broker])

try:
    admin_client.delete_topics(["temperatures"])
    print("Deleted topics successfully")
except UnknownTopicOrPartitionError:
    print("Cannot delete topic/s (may not exist yet)")

time.sleep(3) # Deletion sometimes takes a while to reflect

# temperatures_topic = NewTopic(name="temperatures", num_partitions=4, replication_factor=1)
# admin_client.create_topics([temperatures_topic])

try:
    temperatures_topic = NewTopic(name="temperatures", num_partitions=4, replication_factor=1)
    admin_client.create_topics([temperatures_topic])
except TopicAlreadyExistsError:
    print("Topic 'temperatures' already exists.")

print("Topics:", admin_client.list_topics())
    
mapping = {
    "01": "January",
    "02": "February",
    "03": "March",
    "04": "April",
    "05": "May",
    "06": "June",
    "07": "July",
    "08": "August",
    "09": "September",
    "10": "October",
    "11": "November",
    "12": "December"
}

def get_month(date):
    return bytes(mapping[date.split("-")[1]], "utf-8")

producer = KafkaProducer(bootstrap_servers= broker, retries=10, acks='all')
pre_date = None
for date, degrees in weather.get_next_weather(delay_sec=0.1):
    if pre_date and pre_date == date:
        pre_date = date
        continue
    
    pre_date = date
    report = Report(date=date, degrees=degrees)
    # print(mapping[get_month(date)])
    result = producer.send("temperatures", key=get_month(date), value=report.SerializeToString())
    print(result)        
        
