# doordash-infra-mockup
This repository is a infra-mockup containing the following resources: Kafka, Flink, Airflow, Pyspark, Presto and Superset. We've collected data from wikipedia in two different formats: streaming and batch.

For batch data, we've used the mwviews library to collect pageviews from different wikipedia domains. For streaming data, the streaming url for wikipedia edits (https://stream.wikimedia.org/v2/stream/recentchange) with a Kafka producer. The batch data is collected and saved as .json in a raw layer and then processed in a pyspark job to be saved as .parquet in a trusted layer in AWS s3. Streaming data is processed by a Flink Job and sent to a local elasticsearch instance and to a Kafka topic with two different jobs.

Batch data job is orchestrated using Airflow - there is a task for raw data processing and a task for trusted data in the same DAG.

There is a Presto virtualization for different databases - s3, elasticsearch and druid.

And finally, the endpoint to visualize everything with simple dashboard views using Superset. It is important to notice that Superset cannot join between different databases (at the begining of this project we thought this was a feature), an ETL job would be required to perform this. Though, it is possible to visualize in a same dashboard data from different databases. 


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

## Inside `doordash-mockup` folder - build and start the services

### Building the Docker image

First, create a single network that will be shared between services (this will allow to create connections with the service names):

```bash
docker network create doordash-mockup-network
```

After, build the Docker images by running:
```bash
docker-compose build
```

### Starting the Services

Once the Docker image build is complete, run the following command to start services:

```bash
docker-compose up -d
```

## Configuring Presto with S3/hive, elasticsearch and Apache Druid

### Copy the configuration files to the presto container
1st Bug located - it is mandatory to restart the container 2 times for each catalog configuration.

2nd Bug located - druid presto connection is not working yet. We're investigating the issue.

```bash
PRESTO_CTR=$(docker container ls | grep 'presto_1' | awk '{print $1}')
docker cp ./presto/etc/elasticsearch.properties $PRESTO_CTR:/opt/presto-server/etc/catalog/elasticsearch.properties
docker restart $PRESTO_CTR
docker cp ./presto/etc/s3.properties $PRESTO_CTR:/opt/presto-server/etc/catalog/s3.properties
docker restart $PRESTO_CTR
docker cp ./presto/etc/druid.properties $PRESTO_CTR:/opt/presto-server/etc/catalog/druid.properties
docker restart $PRESTO_CTR
```

### Start Presto CLI
Check if the elasticsearch, s3 and Druid catalog are there:

```bash
docker exec -it $PRESTO_CTR presto-cli
```

```bash
show catalogs;
```
### Start the Hive Server
Run the command below and wait around 2 minutes or skip to the flink/airflow/superset part while hive is getting ready:

```bash
docker-compose exec -d hive /opt/apache-hive-3.1.2-bin/bin/hiveserver2
```

### Connect to beeline and create an external table from s3
Connect to beeline (it is possible after hive is ready - waiting around 2 minutes):
```bash
docker-compose exec hive /opt/apache-hive-3.1.2-bin/bin/beeline -u  jdbc:hive2://localhost:10000
```

Create an external table from s3 in the beeline - use this example to build yours (you should check schema and location fields):
```sql
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

```sql
MSCK REPAIR TABLE wikipedia_batch;
```

## Submiting the Flink Jobs with JobManager

Run the flink job - in this examples it will get the data provided from the Kafka Producer and process it sending to an elasticsearch sink and a Kafka topic:

```bash
docker-compose exec jobmanager ./bin/flink run -py /opt/pyflink-jobs/wikipedia_events_proccessing_tumbling_window_es.py -d
docker-compose exec jobmanager ./bin/flink run -py /opt/pyflink-jobs/wikipedia_events_proccessing_tumbling_window_kafka.py -d
```
You can check the created job in the Flink Web UI [http://localhost:8081](http://localhost:8081).

## Configuring Apache Druid
Clone the [druid repository](https://github.com/apache/druid) and change the git version to 27.0.0 in a separate terminal. After that, add to the docker-compose the network configuration, edit the druid/distribution/docker/environment adding the kafka extensions and running it.

### Adding the network
```
networks: 
  default: 
    external: 
      name: doordash-mockup-network
```

### Adding the kafka extensions to druid/distribution/docker/environment
```
druid_extensions_loadList=["druid-histogram", "druid-datasketches", "druid-lookups-cached-global", "postgresql-metadata-storage", "druid-multi-stage-query", "druid-kafka-indexing-service", "druid-kafka-extraction-namespace", "kafka-emitter"]
```

### And finally running it
```bash
docker-compose -f ../druid/distribution/docker/docker-compose.yml up -d
```
Run the following command to create an ingestion from the Kafka topic created by the Flink job:
```bash
curl -X 'POST' -H 'Content-Type:application/json' -d @druid/ingestion-spec.json http://localhost:8089/druid/indexer/v1/supervisor
```

## Configuring Superset
Clone the [Superset repository](https://github.com/apache/superset). It is recommended to have the superset folder in the same folder structure as the `doordash-infra-mock`

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
### Check the Superset UI

 [Access the Superset UI](http://localhost:8088) and login with:
```
user: admin
password: admin
```
### Create databases connections from Presto

If you added all the services in the same network (editing the docker-compose file), you can just add a new presto/druid database with the service name using SQL Alchemy:

### Presto connections:
```bash
presto://presto:8080/s3
presto://presto:8080/elasticsearch
presto://presto:8080/druid
```
### Druid connection:
```bash
druid://broker:8082/druid/v2/sql
```
### Query data using SQL Lab
Go to the SQL > SQL Lab view to query data from both sources - s3 and Elasticsearch. After doing some tests, you can check the [Presto UI](http://localhost:8080) and find the completed queries section to understand better how Presto interacts with Superset.

You can use the superset-resources folder and import `dashboard_export_wikipedia.zip` - it includes 4 datasets, 4 charts and 1 dashboard. Or you can build your own visualizations.

Important to notice: it is not possible to query between different Databases performing joins. But you can have data from different databases in the same dashboard.

## Configuring Airflow

Build airflow - you can edit the `Dockerfile` and `requirements.txt` to change airflow version or add dependencies. For this case, we've added pyspark, boto3 and mwviews. There is a DAG example file that sends data to a specific s3 folder, try to create a new DAG file or edit the current changing the s3 file destination.
```bash
docker-compose -f ../airflow/docker-compose.yaml build
```

Initialize the Airflow database:
```bash
docker-compose -f ../airflow/docker-compose.yaml up airflow-init
```

Run Airflow and login with airflow:airflow at [Airflow WebServer UI](http://localhost:8082) after the service is ready:
```bash
docker-compose -f ../airflow/docker-compose.yaml up -d
```

## Check all the running services

1. visiting Flink Web UI [http://localhost:8081](http://localhost:8081).
2. visiting Elasticsearch [http://localhost:9200](http://localhost:9200).
3. visiting Superset [http://localhost:8088](http://localhost:8088).
4. visiting Airflow WebServer UI [http://localhost:8082](http://localhost:8082).
5. visiting Presto UI [http://localhost:8080](http://localhost:8080).

## Stopping the Services

To stop the services and clean volumes, run the following commands:

```bash
docker-compose down -v
docker-compose -f ../druid/distribution/docker/docker-compose.yml down -v
docker-compose -f ../superset/docker-compose-non-dev.yml down -v
docker-compose -f ../airflow/docker-compose.yaml down -v
```
