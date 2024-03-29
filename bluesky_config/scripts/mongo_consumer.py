import argparse
from functools import partial
import logging
from pprint import pprint
import time

import msgpack
import msgpack_numpy as mpn

from bluesky_kafka import MongoConsumer


logging.basicConfig(level=logging.DEBUG)
logging.getLogger("bluesky.kafka").setLevel("DEBUG")

parser = argparse.ArgumentParser(
    description="monogo consumer process",
)
parser.add_argument(
    "--kafka_server",
    type=str,
    help="bootstrap server to connect to.",
    default="127.0.0.1:9092",
)
parser.add_argument(
    "--kafka_group",
    type=str,
    help="bootstrap server to connect to.",
    default="mongo-consumers",
)
parser.add_argument(
    "--mongo_uri",
    type=str,
    help="bootstrap server to connect to.",
    default="mongodb://localhost:27017",
)

args = parser.parse_args()

mongo_uri = args.mongo_uri
bootstrap_servers = args.kafka_server

kafka_deserializer = partial(msgpack.loads, object_hook=mpn.decode)
auto_offset_reset = "earliest"
topics = ["^.*bluesky.documents"]
topic_database_map = {"mad.bluesky.documents": "mad-bluesky-documents"}
# Create a MongoConsumer that will automatically listen to new beamline topics.
# The parameter metadata.max.age.ms determines how often the consumer will check for
# new topics. The default value is 5000ms.
settings = dict(
    topics=topics,
    topic_database_map=topic_database_map,
    bootstrap_servers=bootstrap_servers,
    group_id=args.kafka_group,
    mongo_uri=mongo_uri,
    consumer_config={"auto.offset.reset": auto_offset_reset},
    polling_duration=1.0,
    deserializer=kafka_deserializer,
)
pprint(settings)

mongo_consumer = MongoConsumer(**settings)
last_call = 0


def work_while_waiting():
    global last_call
    if (now := time.monotonic()) > last_call + 10:
        attached_topics = set(mongo_consumer._consumer.list_topics().topics)
        if set(topics) - attached_topics:
            mongo_consumer._consumer.subscribe(topics=topics)
        last_call = now


mongo_consumer.start(None, work_while_waiting)
