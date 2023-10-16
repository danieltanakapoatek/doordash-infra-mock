# doordash-mockup

## Definining configuration files with AWS secrets

Secrets to be defined (aws_client_id and aws_client_secret) are present in some configuration files, follow the steps to populate it:

First, create the airflow .env files. Substitute the aws values for the correct:
```bash
export AWS_ACCESS_KEY={aws_access_key}
export AWS_SECRET_ACCESS={aws_secret_access}
envsubst < ./airflow/.env-template > ./airflow/.env
envsubst < ./airflow/dags/.env-template > ./airflow/dags/.env
```

After that, inside the `doordash-mockup` folder, use the template files to create your config files:

```bash
cd doordash-mockup
envsubst < ./presto/etc/s3-template.properties > ./presto/etc/s3.properties
envsubst < ./hive/conf/hdfs-site-template.xml > ./hive/conf/hdfs-site.xml
envsubst < ./hive/conf/hive-site-template.xml > ./hive/conf/hive-site.xml
```

## Inside the `doordash-mockup` build and start the services

### Building the Docker image

First, build the Docker images by running:

```bash
docker-compose build
```
After, create a single network that will be shared between services (this will allow to create connections with the service names):
```bash
docker network create doordash-mockup-network
```

### Starting the Services

Once the Docker image build is complete, run the following command to start services:

```bash
docker-compose up -d
```

## Configuring Presto configured with S3/hive and elasticsearch

### Copy the configuration files to the presto container
Bug located - it is mandatory to restart the container 2 times for each catalog configuration.

```bash
PRESTO_CTR=$(docker container ls | grep 'presto_1' | awk '{print $1}')
docker cp ./presto/etc/elasticsearch.properties $PRESTO_CTR:/opt/presto-server/etc/catalog/elasticsearch.properties
docker restart $PRESTO_CTR
docker cp ./presto/etc/s3.properties $PRESTO_CTR:/opt/presto-server/etc/catalog/s3.properties
docker restart $PRESTO_CTR
```

### Start Presto CLI
Check if the elasticsearch and s3 catalog are there:

```bash
docker exec -it $PRESTO_CTR presto-cli
```

```bash
show catalogs;
```
### Start the Hive Server
Wait around 2 minutes or skip to the flink/airflow/superset part while hive is getting ready:

```bash
docker-compose exec -d hive /opt/apache-hive-3.1.2-bin/bin/hiveserver2
```

### Connect to beeline and connect to an external table from s3
Connect to beeline (it is possible after hive is ready):
```bash
docker-compose exec hive /opt/apache-hive-3.1.2-bin/bin/beeline -u  jdbc:hive2://localhost:10000
```

Create a table from s3 in the beeline - use this example to build yours (you should check schema and location fields):
```bash
CREATE EXTERNAL TABLE IF NOT EXISTS wikipedia_batch(
domain STRING,
pageviews BIGINT,
pageview_date date
)
PARTITIONED BY (processing_date date)
ROW FORMAT SERDE
'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
STORED AS INPUTFORMAT
'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat'
OUTPUTFORMAT
'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat'
LOCATION
's3a://doordash-mockup-daniel/wikipedia-batch/trusted/';
```

Run MSCK REPAIR and exit beeline:

```bash
MSCK REPAIR TABLE wikipedia_batch;
```

## Submiting the Flink Job with JobManager

Run the flink job - in this example it will get the data provided from the Kafka Producer and process it sending to an elasticsearch sink:

```shell script
docker-compose exec jobmanager ./bin/flink run -py /opt/pyflink-jobs/wikipedia_events_proccessing_tumbling_window.py -d
```
You can check the created job in the Flink Web UI [http://localhost:8081](http://localhost:8081).
## Configuring Superset
After that, clone the [Superset repository](https://github.com/apache/superset). It is recommended to have the superset folder in the same folder structure as the `doordash-infra-mock`

Edit the /superset/docker-compose-non-dev.yml docker-compose file adding a network option at the end of the docker-compose file (this will allow to communicate the services using their name as URI):
```
networks: 
  default: 
    external: 
      name: doordash-mockup-network
```

### Start the superset container with the production docker-compose file
```bash
docker-compose -f ../superset/docker-compose-non-dev.yml up -d
```

Kill the volumes if needed (sometimes the UI loads with missing info regarding databases) - this will clear all superset cache (After that, run the `docker-compose up` command again):
```bash
docker-compose -f ../superset/docker-compose-non-dev.yml down -v
```
Check the Superset UI at [http://localhost:8088](http://localhost:8088) and login with:

user: admin

password: admin

### Create databases connections from Presto

If you added all the services in the same network (editing the docker-compose file), you can just add a new presto database with the service name using SQL Alchemy:

```bash
presto://presto:8080/s3
presto://presto:8080/elasticsearch
```

### Query data using SQL Lab
Go to the SQL > SQL Lab view to query data from both sources - s3 and Elasticsearch. After doing some tests, you can check the Presto UI [http://localhost:8080](http://localhost:8080) and check the completed queries section to understand better how Presto interacts with Superset.

An alternative is to check the superset-resources folder and import `dashboard_export_wikipedia.zip` - it includes 4 datasets, 4 charts and 1 dashboard. Or you can build your own visualizations.

Important to notice: it is not possible to query between different Databases performing joins. But you can have data from different databases in the same dashboard.

## Configuring Airflow

Build airflow - you can edit the Dockerfile and requirements.txt to change airflow version or add dependencies. For this case, we've added pyspark, boto3 and mwviews.
```bash
docker-compose -f ../airflow/docker-compose.yaml build
```

Initialize the Airflow database:
```bash
docker-compose -f ../airflow/docker-compose.yaml up airflow-init
```

Run Airflow and login with airflow:airflow at [http://localhost:8082](http://localhost:8082) after the service is ready:
```bash
docker-compose -f ../airflow/docker-compose.yaml up -d
```

## Check all the running services

1. visiting Flink Web UI [http://localhost:8081](http://localhost:8081).
2. visiting Elasticsearch [http://localhost:9200](http://localhost:9200).
3. visiting Superset [http://localhost:8088](http://localhost:8088).
4. visiting Airflow [http://localhost:8082](http://localhost:8082).
5. visiting Presto UI [http://localhost:8080](http://localhost:8080).

## Stopping the Services

To stop the services and clean volumes, run the following commands:

```bash
docker-compose down -v
docker-compose -f ../superset/docker-compose-non-dev.yml down -v
docker-compose -f ../airflow/docker-compose.yaml down -v
```
