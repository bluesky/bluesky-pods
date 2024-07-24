import logging
import os
import uuid
from abc import ABC
from typing import Dict

import numpy as np
from bluesky_adaptive.agents.base import Agent, AgentConsumer
from bluesky_adaptive.server import register_variable, shutdown_decorator, startup_decorator
from bluesky_queueserver_api.http import REManagerAPI
from databroker.client import BlueskyRun
from tiled.client import from_uri

logger = logging.getLogger(__name__)


def perlin(x, y, seed=0):
    """Perlin noise implementation.
    https://stackoverflow.com/questions/42147776/producing-2d-perlin-noise-with-numpy
    """

    def lerp(a, b, x):
        "linear interpolation"
        return a + x * (b - a)

    def fade(t):
        "6t^5 - 15t^4 + 10t^3"
        return 6 * t**5 - 15 * t**4 + 10 * t**3

    def gradient(h, x, y):
        "grad converts h to the right gradient vector and return the dot product with (x,y)"
        vectors = np.array([[0, 1], [0, -1], [1, 0], [-1, 0]])
        g = vectors[h % 4]
        return g[:, :, 0] * x + g[:, :, 1] * y

    # permutation table
    np.random.seed(seed)
    p = np.arange(256, dtype=int)
    np.random.shuffle(p)
    p = np.stack([p, p]).flatten()
    # coordinates of the top-left
    xi, yi = x.astype(int), y.astype(int)
    # internal coordinates
    xf, yf = x - xi, y - yi
    # fade factors
    u, v = fade(xf), fade(yf)
    # noise components
    n00 = gradient(p[p[xi] + yi], xf, yf)
    n01 = gradient(p[p[xi] + yi + 1], xf, yf - 1)
    n11 = gradient(p[p[xi + 1] + yi + 1], xf - 1, yf - 1)
    n10 = gradient(p[p[xi + 1] + yi], xf - 1, yf)
    # combine noises
    x1 = lerp(n00, n10, u)
    x2 = lerp(n01, n11, u)
    return lerp(x1, x2, v)


class PodBaseAgent(Agent, ABC):
    def __init__(self, *args, metadata=None, **kwargs):
        metadata = metadata or {}
        _default_kwargs = self.get_beamline_objects()
        _default_kwargs.update(kwargs)
        super().__init__(*args, metadata=metadata, **_default_kwargs)

    @staticmethod
    def get_beamline_objects():
        qs = REManagerAPI(http_server_uri="http://qs_api:60610")
        qs.set_authorization_key(api_key=os.getenv("HTTPSERVER_API_KEY", "mad"))
        kafka_consumer = AgentConsumer(
            topics=[
                "mad.bluesky.documents",
            ],
            consumer_config={"auto.offset.reset": "earliest"},
            bootstrap_servers="kafka:29092",
            group_id=f"echo-{str(uuid.uuid4())[:8]}",
        )
        return dict(
            kafka_consumer=kafka_consumer,
            kafka_producer=None,
            tiled_data_node=from_uri("http://proxy:11973/tiled", api_key="ABCDABCD"),
            tiled_agent_node=from_uri("http://proxy:11973/tiled", api_key="ABCDABCD"),
            qserver=qs,
        )


class ReactiveAgent(Agent, ABC):
    """Build the Logic for the Reactive Random Walk Agent, that reacts to an observable and increases or decreases
    some position. This is only logic, but system agnostic."""

    def __init__(self, *, target, step_size=0.1, **kwargs):
        super().__init__(**kwargs)
        self._target = target
        self._step_size = step_size
        self._last_value = None

    @staticmethod
    def _make_perlin_noise():
        perlin_noise = np.zeros((100, 100))
        for i in range(4):
            freq = 2**i
            lin = np.linspace(0, freq, 100, endpoint=False)
            x, y = np.meshgrid(lin, lin)  # FIX3: I thought I had to invert x and y here but it was a mistake
            perlin_noise = perlin(x, y, seed=None) / freq + perlin_noise
        return perlin_noise

    def tell(self, x, y):
        self._last_value = y
        return dict(independent_variable=x, observable=y)

    def report(self, **kwargs) -> Dict:
        return dict(
            target=self._target,
            step_size=self._step_size,
            brain=self._make_perlin_noise(),
        )

    def ask(self, n):
        super().ask(n)
        """Generates a reactive walk, but logs some perlin noise as a proxy for decision logic"""
        if self._last_value is None:
            return (
                [
                    dict(
                        target=self._target,
                        step_size=self._step_size,
                        next_value=0.0,
                        brain=self._make_perlin_noise(),
                    )
                ],
                [0.0],
            )
        elif self._last_value > self._target:
            next_value = self._last_value - self._step_size
            logger.info(f"Decreasing value from {self._last_value} to {next_value}")
            return (
                [
                    dict(
                        target=self._target,
                        step_size=self._step_size,
                        next_value=next_value,
                        brain=self._make_perlin_noise(),
                    )
                ],
                [next_value],
            )
        else:
            next_value = self._last_value + self._step_size
            logger.info(f"Increasing value from {self._last_value} to {next_value}")
            return (
                [
                    dict(
                        target=self._target,
                        step_size=self._step_size,
                        next_value=next_value,
                        brain=self._make_perlin_noise(),
                    )
                ],
                [next_value],
            )

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, value):
        self._target = value

    @property
    def step_size(self):
        return self._step_size

    @step_size.setter
    def step_size(self, value):
        self._step_size = value

    def server_registrations(self) -> None:
        super().server_registrations()
        self._register_property("target")
        self._register_property("step_size")


class ReactiveRandomWalker(ReactiveAgent, PodBaseAgent):
    def __init__(self, *, detector="random_walk", read_key="random_walk_x", motor="motor", **kwargs):
        self._detector = detector
        self._motor = motor
        self._read_key = read_key
        super().__init__(**kwargs)

    def unpack_run(self, run: BlueskyRun):
        data = run.primary.data.read()
        x = float(data[self._motor].data)
        y = float(data[self._read_key].data)
        return x, y

    def measurement_plan(self, point):
        return "scan", [[self._detector], self._motor, point, point, 1], {}


# ==========================This is the necassary code to start the agent========================== #
agent = ReactiveRandomWalker(target=np.random.rand(), ask_on_tell=False)


@startup_decorator
def startup():
    agent.start()


@shutdown_decorator
def shutdown_agent():
    return agent.stop()


register_variable("Agent Name", agent, "instance_name")
# ==========================This is the necassary code to start the agent========================== #
