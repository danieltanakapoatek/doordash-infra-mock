################################################################################
#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
# limitations under the License.
################################################################################

from pyflink.datastream import StreamExecutionEnvironment, TimeCharacteristic
from pyflink.table import StreamTableEnvironment, DataTypes, EnvironmentSettings
from pyflink.table.expressions import call, col, lit
from pyflink.table.udf import udf
from pyflink.table.window import Tumble


def log_processing():
    env = StreamExecutionEnvironment.get_execution_environment()
    t_env = StreamTableEnvironment.create(stream_execution_environment=env)
    t_env.get_config().get_configuration().set_boolean(
        "python.fn-execution.memory.managed", True
    )
   
    create_kafka_source_ddl = """
            CREATE TABLE IF NOT EXISTS wikipedia_events(
                id STRING,
                domain STRING,
                namespace STRING,
                title STRING,
                createTime TIMESTAMP(3),
                user_name STRING,
                user_type STRING,
                WATERMARK FOR createTime AS createTime - INTERVAL '5' SECOND
            ) WITH (
              'connector' = 'kafka',
              'topic' = 'wikipedia-events',
              'properties.bootstrap.servers' = 'kafka:9092',
              'properties.group.id' = 'test_5',
              'scan.startup.mode' = 'earliest-offset',
              'format' = 'json'
            )
            """

    create_es_sink_ddl = """
            CREATE TABLE es_sink_wikipedia_window(
                domain STRING,
                ten_second_window TIMESTAMP(3),
                count_actions BIGINT NOT NULL
            ) with (
                'connector' = 'elasticsearch-7',
                'hosts' = 'http://elasticsearch:9200',
                'index' = 'wikipedia_window_1',
                'document-id.key-delimiter' = '$',
                'sink.bulk-flush.max-size' = '42mb',
                'sink.bulk-flush.max-actions' = '32',
                'sink.bulk-flush.interval' = '1000',
                'sink.bulk-flush.backoff.delay' = '1000',
                'format' = 'json'
            )
    """

    t_env.execute_sql(create_kafka_source_ddl)
    t_env.execute_sql(create_es_sink_ddl)

    t_env.from_path("wikipedia_events").window(
        Tumble.over(lit(10).seconds).on(col("createTime")).alias("ten_second_window")
    ).group_by(col("domain"), col("ten_second_window")).select(
        col("domain"),
        col("ten_second_window").end.alias("ten_second_window"),
        col("domain").count.alias("count_actions")
    ).execute_insert(
        "es_sink_wikipedia_window"
    )


if __name__ == "__main__":
    log_processing()
