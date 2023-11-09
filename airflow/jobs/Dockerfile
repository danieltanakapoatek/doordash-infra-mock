FROM python:3.9.18-bullseye

RUN apt-get update -y \
    && apt-get install -y python3-dev python3-pip build-essential \
    && apt-get install -y openjdk-11-jdk \
    && apt-get install gcc -y \
    && apt-get install sudo -y \ 
    && apt-get clean

# Set JAVA_HOME
ENV JAVA_HOME /usr/lib/jvm/java-11-openjdk-amd64/
RUN export JAVA_HOME

RUN adduser --disabled-password --gecos '' airflow

ADD ./requirements.txt . 
ADD ./wikipedia_raw_job.py .
ADD ./wikipedia_trusted_job.py .
ADD ./.env .
RUN pip install -r requirements.txt

USER airflow

CMD ["echo", "hello world"]