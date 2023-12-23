import os
import json
from datetime import datetime
import sys
from kafka import KafkaConsumer, TopicPartition
from report_pb2 import Report

broker = 'localhost:9092'

def getDate(dateString):
    date = datetime.strptime(dateString, '%Y-%m-%d')

    return date.strftime('%B'), str(date.year)

def statistics(data, monthYear, temperature, date):
    month, year = monthYear

    if month not in data:
        data[month] = {}
    if year not in data[month]:
        data[month][year] = {'count': 0, 'sum': 0, 'start': date, 'end': date}

    entry = data[month][year]

    if date >= entry['start']:
        if date > entry['end']:
            entry['end'] = date

        entry['count'] += 1
        entry['sum'] += temperature
        entry['avg'] = entry['sum'] / entry['count']

def toFile(partitionData, partition):
    filePath = f"/files/partition-{partition}.json"
    temp = f"{filePath}.tmp"
    with open(temp, 'w') as file:
        json.dump(partitionData, file, indent = 4)
    os.rename(temp, filePath)


paritionNum = [int(arg) for arg in sys.argv[1:]]
paritionDict = {}
partitionData = {}
for p in paritionNum:
    if not 0 <= p <= 3: exit()
    paritionDict[p] = TopicPartition('temperatures', p)
    file_name = f"/files/partition-{p}.json"
    
    if os.path.exists(file_name):
        with open(file_name, 'r') as file:
            partitionData[p] = json.load(file)
    else:
        partitionData[p] = {'partition': p, 'offset': 0}
        toFile(partitionData[p], p)
        
consumer = KafkaConsumer(bootstrap_servers=broker, auto_offset_reset='latest')
consumer.assign(paritionDict.values())

for key, values in paritionDict.items():
    consumer.seek(values, partitionData[p]['offset'])

for message in consumer:
    report = Report.FromString(message.value)
    date = report.date
    temperature = report.degrees
    monthYear = getDate(date)
    partition = message.partition
    statistics(partitionData[partition], monthYear, temperature, date)
    partitionData[partition]['offset'] = consumer.position(paritionDict[partition])
    toFile(partitionData[partition], partition)