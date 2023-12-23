import pandas as pd
import matplotlib.pyplot as plt
import json
import os

def getYear(partition_data, month):
    if month in partition_data:
        latestYear = max(partition_data[month].keys(), key=lambda y: int(y))
        return partition_data[month][latestYear]['avg'], latestYear
    
    return None, None

path = "/files/partition-{}.json"
partitionNum = [0, 1, 2, 3]

monthData = {}

for p in partitionNum:
    file_path = path.format(p)

    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)

            for month in ['January', 'February', 'March']:
                averageTemp, year = getYear(data, month)

                if averageTemp is not None:
                    monthData[f'{month}-{year}'] = averageTemp

monthSeries = pd.Series(monthData)

fig, ax = plt.subplots()
monthSeries.plot.bar(ax = ax)
ax.set_ylabel('Avg. Max Temperature')
plt.title('Month Averages')
plt.tight_layout()
plt.savefig("/files/month.svg")
