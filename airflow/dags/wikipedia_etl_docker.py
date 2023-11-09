from textwrap import dedent
import pendulum
from airflow import DAG
from airflow.operators.docker_operator import DockerOperator
from dotenv import load_dotenv

load_dotenv()

with DAG(
    "wikipedia_etl_docker",
    default_args={"retries": 2},
    max_active_runs=1,
    description="Wikipedia Batch ETL",
    schedule="@daily",
    start_date=pendulum.datetime(2023, 10, 1, tz="UTC"),
    catchup=True,
    tags=["Wikipedia"],
) as dag:
    dag.doc_md = __doc__

    raw_task = DockerOperator(
        task_id="raw",
        image="airflow_jobs",
        container_name="airflow_jobs_raw",
        api_version="auto",
        auto_remove=True,
        command=["python", "/wikipedia_raw_job.py", "--date", "{{ ds }}"],
        docker_url="tcp://docker-proxy:2375",
        network_mode="bridge",
    )

    trusted_task = DockerOperator(
        task_id="trusted",
        image="airflow_jobs",
        container_name="airflow_jobs_trusted",
        api_version="auto",
        auto_remove=True,
        command="python /opt/airflow/wikipedia_trusted_job.py --date={{ ds }}",
        docker_url="tcp://docker-proxy:2375",
        network_mode="bridge",
    )

    raw_task >> trusted_task
