from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'fraud_model_retraining',
    default_args=default_args,
    description='Daily retraining of the Fraud Detection Model',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['mlops', 'fraud'],
) as dag:

    # Task 1: Wait for data / Checking sensors
    check_dependencies = BashOperator(
        task_id='check_dependencies',
        bash_command='echo "Checking Data Lake and DB connections..." && sleep 5'
    )

    # Task 2: Run the retraining script
    train_model = BashOperator(
        task_id='train_model',
        bash_command='python /opt/airflow/src/model/retrain.py '
    )

    check_dependencies >> train_model
