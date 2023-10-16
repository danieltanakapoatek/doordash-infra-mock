### Edit the docker-compose.yaml file

Change line 53 commenting and create a new line as 'build: .' to use a Dockerfile to build the image.

### Create the folders to add volumes:
```bash
$ mkdir ./dags ./logs ./plugins
```

### Set up the Airflow User:
```bash
$ echo -e "AIRFLOW_UID=$(id -u)\nAIRFLOW_GID=0" > .env
```
### Build
```bash
$ docker-compose build
```

### Initialize the Airflow database:
```bash
$ docker-compose up airflow-init
```

### Run Airflow and login with airflow:airflow at localhost:8000
```bash
$ docker-compose up -d
```