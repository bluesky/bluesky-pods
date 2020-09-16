import argparse
import datetime
from functools import partial

import msgpack
import msgpack_numpy as mpn

from bluesky_kafka import RemoteDispatcher

parser = argparse.ArgumentParser(
    description="monogo consumer process",
)
parser.add_argument(
    "--kafka_server", type=str, help="bootstrap server to connect to.",
    default="127.0.0.1:9092"
)

args = parser.parse_args()

bootstrap_servers = args.kafka_server


kafka_dispatcher = RemoteDispatcher(
    topics=["mad.bluesky.documents"],
    bootstrap_servers=bootstrap_servers,
    group_id="kafka-unit-test-group-id",
    # "latest" should always work but
    # has been failing on Linux, passing on OSX
    consumer_config={"auto.offset.reset": "latest"},
    polling_duration=1.0,
    deserializer=partial(msgpack.loads, object_hook=mpn.decode),
)


def echo(name, doc):
    ts = doc.get("time", 0)
    print(
        f"{datetime.datetime.now().isoformat()}: "
        f"({datetime.datetime.fromtimestamp(ts)})"
        f" {name} "
    )


kafka_dispatcher.subscribe(echo)
kafka_dispatcher.start()
