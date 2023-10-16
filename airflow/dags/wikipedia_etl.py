from __future__ import annotations
import json
from textwrap import dedent
import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator
from mwviews.api import PageviewsClient
from datetime import date as dt
from datetime import datetime as dtime
from datetime import timedelta
import json
import boto3
import os
from pyspark.sql.functions import *
from pyspark import SparkConf, SparkContext
from pyspark.sql import SparkSession
import pyspark as pyspark
from dotenv import load_dotenv

load_dotenv()

with DAG(
    "wikipedia_etl",
    default_args={"retries": 2},
    max_active_runs=1,
    description="Wikipedia Batch ETL",
    schedule="@daily",
    start_date=pendulum.datetime(2023, 10, 1, tz="UTC"),
    catchup=True,
    tags=["Wikipedia"],
) as dag:
    dag.doc_md = __doc__
    
    def raw(date_run,**kwargs):
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS")
        aws_bucket='doordash-mockup-daniel'
        aws_folder = 'wikipedia-batch/raw'
        processing_date = date_run
        aws_file = aws_folder + '/processing_date=' + processing_date + '/data.json'


        s3 = boto3.resource(
            's3',
            region_name='us-east-2',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )

        p = PageviewsClient(user_agent="<daniel.tanaka@poatek.com>")
        domains_list = [
            "meta.wikimedia",
            "io.wiktionary",
            "pl.wiktionary",
            "az.wikipedia",
            "en.wikisource",
            "fi.wikipedia",
            "ka.wikipedia",
            "th.wikipedia",
            "pl.wikipedia",
            "en.wiktionary",
            "vi.wikipedia",
            "azb.wikipedia",
            "incubator.wikimedia",
            "tr.wikipedia",
            "en.wikibooks",
            "sr.wikipedia",
            "el.wiktionary",
            "it.wikipedia",
            "hi.wikipedia",
            "nl.wikipedia",
            "eo.wikipedia",
            "az.wikiquote",
            "no.wikipedia",
            "rue.wikipedia",
            "es.wikipedia",
            "ko.wikipedia",
            "bn.wikipedia",
            "fr.wikipedia",
            "ja.wikipedia",
            "fr.wiktionary",
            "zh.wikipedia",
            "de.wikipedia",
            "ca.wikipedia",
            "he.wikipedia",
            "lv.wikipedia",
            "uk.wikisource",
            "fa.wikipedia",
            "ar.wikipedia",
            "bg.wikipedia",
            "ru.wikipedia",
            "uk.wikipedia",
            "id.wikipedia",
            "pt.wikipedia",
            "sk.wikipedia",
            "cs.wikipedia",
            "en.wikipedia",
            "sv.wikipedia",
            "commons.wikimedia"]

        project_views = p.project_views(domains_list)
        project_views_keys_str = {}
        data_list = []
        for key in project_views:
            new_key = key.strftime("%Y-%m-%d")
            project_views_keys_str[new_key] = project_views[key]

        for date in project_views_keys_str:
            for key in project_views_keys_str[date]:
                data_dict = {
                    "date": date,
                    "domain": key,
                    "pageviews": project_views_keys_str[date][key]
                }
                data_list.append(data_dict)

        with open("/tmp/wikipedia-data.json", "w") as outfile:
            outfile.write(json.dumps(data_list, indent=4))

        s3.Bucket(aws_bucket).upload_file('/tmp/wikipedia-data.json', aws_file)

    def trusted(date_run,**kwargs):
        # File Secret configurations
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS")

        # Spark Configurations:
        conf = pyspark.SparkConf()
        conf.set("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.4")

        sc = SparkContext(conf=conf)

        sc._jsc.hadoopConfiguration().set("fs.s3a.access.key", aws_access_key_id)
        sc._jsc.hadoopConfiguration().set("fs.s3a.secret.key", aws_secret_access_key)
        sc._jsc.hadoopConfiguration().set(
            "fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem"
        )

        spark = SparkSession(sc)

        # Filesystem definitions:
        processing_date = date_run
        aws_bucket = "s3a://doordash-mockup-daniel"
        raw_file = (
            aws_bucket
            + "/wikipedia-batch/raw/"
            + "processing_date="
            + processing_date
            + "/data.json"
        )
        trusted_folder = (
            aws_bucket
            + "/wikipedia-batch/trusted/"
        )

        # Extract:
        df = spark.read.option("multiline", "true").json(raw_file)

        # Transform:
        processing_date_date_object = dtime.strptime(processing_date, '%Y-%m-%d').date()
        seven_days_from_processing_date = (processing_date_date_object - timedelta(days=7)).strftime(
            "%Y-%m-%d"
        )
        df = df.withColumn("pageview_date", to_date("date", "yyyy-MM-dd")).drop(col("date"))
        df = df.filter(df.pageview_date < processing_date).filter(
            df.pageview_date >= seven_days_from_processing_date
        )
        df = df.withColumn("processing_date", to_date(lit(processing_date), "yyyy-MM-dd"))

        # Load and stop:
        df.write.partitionBy("processing_date").parquet(
            trusted_folder, mode="append"
        )

        spark.stop()

    raw_task = PythonOperator(
        task_id="raw",
        python_callable=raw,
        op_args={
         "{{ ds }}"
        }
    )
    raw_task.doc_md = dedent(
        """\
    #### Raw task
    This task collects data using the mwview library and saves it to a raw partition in an s3 bucket
    """
    )

    trusted_task = PythonOperator(
        task_id="trusted",
        python_callable=trusted,
        op_args={
         "{{ ds }}"
        }
    )
    trusted.doc_md = dedent(
        """\
    #### Trusted task
    This task collects data from the raw s3 layer and runs a pyspark job saving the results
    as .parquet in a trusted layer in s3
    """
    )

    raw_task >> trusted_task