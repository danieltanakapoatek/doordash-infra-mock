from datetime import date, timedelta
from pyspark.sql.functions import *
from pyspark import SparkConf, SparkContext
from pyspark.sql import SparkSession
import pyspark as pyspark
import os

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
processing_date = date.today().strftime("%Y-%m-%d")
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
df = spark.read.option("multiline", "true").json("/tmp/wikipedia-data.json")

# Transform:

seven_days_from_processing_date = (date.today() - timedelta(days=7)).strftime(
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
