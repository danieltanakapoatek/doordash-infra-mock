.PHONY: build_all
build_all: generate_env build_airflow build_jobs
	-docker network create doordash-mockup-network
	cd doordash-mockup docker-compose build

.PHONY: generate_env
generate_env:
	envsubst < ./airflow/.env-template > ./airflow/.env
	envsubst < ./airflow/dags/.env-template > ./airflow/dags/.env
	envsubst < ./airflow/jobs/.env-template > ./airflow/jobs/.env
	envsubst < ./doordash-mockup/presto/etc/s3-template.properties > ./doordash-mockup/presto/etc/s3.properties
	envsubst < ./doordash-mockup/hive/conf/hdfs-site-template.xml > ./doordash-mockup/hive/conf/hdfs-site.xml
	envsubst < ./doordash-mockup/hive/conf/hive-site-template.xml > ./doordash-mockup/hive/conf/hive-site.xml

.PHONY: build_airflow
build_airflow:
	docker-compose -f ./airflow/docker-compose.yaml build

.PHONY: build_jobs
build_jobs:
	cd airflow/jobs && docker build -t airflow_jobs .

.PHONY: run_airflow
run_airflow:
	docker-compose -f ./airflow/docker-compose.yaml up airflow-init && docker-compose -f ./airflow/docker-compose.yaml up -d

.PHONY: run_services
run_services: build_all run_doordash_mockup_services run_airflow

.PHONY: run_superset
run_superset:
	docker-compose -f ./superset/docker-compose-non-dev.yml up -d

.PHONY: run_druid
run_druid: 
	docker-compose -f ./apache-druid/distribution/docker/docker-compose.yml up -d

.PHONY: create_druid_ingestion
create_druid_ingestion:
	curl -X 'POST' -H 'Content-Type:application/json' -d @doordash-mockup/druid/ingestion-spec.json http://localhost:8089/druid/indexer/v1/supervisor

.PHONY: run_doordash_mockup_services
run_services:
	docker-compose -f ./doordash-mockup/docker-compose.yml up -d

.PHONY: run_flink_jobs
run_flink_jobs: 
	cd doordash-mockup && docker-compose exec jobmanager ./bin/flink run -py /opt/pyflink-jobs/wikipedia_events_proccessing_tumbling_window_es.py -d && docker-compose exec jobmanager ./bin/flink run -py /opt/pyflink-jobs/wikipedia_events_proccessing_tumbling_window_kafka.py -d

.PHONY: start_hive
start_hive:
	cd doordash-mockup && docker-compose exec -d hive /opt/apache-hive-3.1.2-bin/bin/hiveserver2

.PHONY: connect_hive
connect_hive:
	cd doordash-mockup docker-compose exec hive /opt/apache-hive-3.1.2-bin/bin/beeline -u  jdbc:hive2://localhost:10000

.PHONY: stop_all
stop_all:
	-docker-compose -f ./doordash-mockup/docker-compose.yml down -v
	-docker-compose -f ./apache-druid/distribution/docker/docker-compose.yml down -v
	-docker-compose -f ./superset/docker-compose-non-dev.yml down -v
	-docker-compose -f ./airflow/docker-compose.yaml down -v