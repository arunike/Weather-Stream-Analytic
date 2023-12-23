# Weather Stream Analytics

## Description
This project demonstrates a practical application of Kafka for real-time data streaming and processing encapsulated within a Docker environment. The primary objective is to simulate handling daily weather data, focusing on key Kafka functionalities and Python scripting.

### Data Generation and Streaming
A Python script functions as a Kafka producer, simulating the generation of daily weather data (e.g., maximum temperatures) for a specific location.
This weather data is streamed into a Kafka topic, configured with multiple partitions to support distributed data handling and scalability.

### Data Consumption and Processing
Various Python consumer scripts are designed to subscribe to the Kafka topic and process the incoming weather data:
A debug script displays the weather data stream in a human-readable format, aiding in troubleshooting and verification.
A more complex consumer script calculates statistical summaries (such as average temperatures) from the weather data. It ensures data integrity and consistency by implementing mechanisms to prevent duplication and guarantee that each data point is processed exactly once. The results are outputted as JSON files, suitable for further analysis or visualization.

### Key Technologies
- Kafka: Utilized for setting up a robust streaming platform.
- Python: Scripts are written in Python for producing and consuming data, as well as for data processing and potentially visualization.
- Docker: Ensures a consistent and isolated environment, facilitating easy setup and deployment.
