from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "kamu",
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="grab_etl_pipeline",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule="*/5 * * * *",       # sama dengan cronjob lama
    catchup=False,
    max_active_runs=1,            # cegah run menumpuk kalau ETL lebih dari 5 menit
    dagrun_timeout=timedelta(minutes=4),
    tags=["etl", "grab"],
) as dag:

    load = BashOperator(
        task_id="load",
        bash_command="cd /opt/airflow/etl && python -u load.py",
    )

    validation = BashOperator(
        task_id="validation",
        bash_command="cd /opt/airflow/etl && python -u validation.py",
    )

    load >> validation