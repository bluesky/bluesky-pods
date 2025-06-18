import logging
import os

import numpy as np

from bluesky_adaptive.utils.offline import OfflineAgent
from bluesky_adaptive.agents.sklearn import ClusterAgentBase
from bluesky_adaptive.server import (
    register_variable,
    shutdown_decorator,
    startup_decorator,
)
from tiled.client import from_profile, from_uri
from httpx import ConnectError, HTTPStatusError

from sklearn.cluster import KMeans

logger = logging.getLogger(__name__)


class ClusterAgentMock(ClusterAgentBase, OfflineAgent):
    """Mock agent for testing purposes. Inherits from ClusterAgentBase and OfflineAgent."""

    def __init__(self, k_clusters: int, *args, use_tiled: bool = False, **kwargs):
        """Initialize the mock agent with optional metadata.
        Parameters
        ----------
        use_tiled : bool, optional
            Whether to use Tiled for writing agent data to storage, by default False.
            Does not read exp data from storage regardless.
        """
        estimator = KMeans(k_clusters, n_init="auto", random_state=42)
        if use_tiled:
            logger.info("Using Tiled for agent data storage.")
            try:
                tiled_container = from_uri(
                    "http://tiled_local:8000", api_key="ABCDABCD"
                )
            except ConnectError or HTTPStatusError:
                tiled_container = from_profile("MAD")
            kwargs["tiled_agent_node"] = tiled_container
        super().__init__(
            *args,
            estimator=estimator,
            loop_consumer_on_start=True,
            **kwargs,
        )

    @property
    def name(self) -> str:
        """Short string name"""
        return "MockClusterAgent"

    # ==========================Useful behavior for clustering, caching, restarting ========================== #
    def clear_caches(self):
        self.independent_cache = []
        self.dependent_cache = []

    def close_and_restart(self, *, clear_tell_cache=False, retell_all=False, reason=""):
        if clear_tell_cache:
            self.clear_caches()
        return super().close_and_restart(
            clear_tell_cache=clear_tell_cache, retell_all=retell_all, reason=reason
        )

    @property
    def n_clusters(self):
        return self.model.n_clusters

    @n_clusters.setter
    def n_clusters(self, value):
        self.model.set_params(n_clusters=int(value))
        self.close_and_restart()

    def server_registrations(self) -> None:
        self._register_method("clear_caches")
        self._register_property("n_clusters")
        return super().server_registrations()

    # ==========================Useful behavior for clustering, caching, restarting ========================== #

    def unpack_run(self, *args, **kwargs):
        """Mock unpack run method for clustering that returns a [2,] array for x and a [1, 10] array for y."""
        x = np.random.rand(2)
        y = np.random.rand(1, 10)
        return x, y

    def measurement_plan(self, point):
        """Mock simply acceptable measurement plan, that as is, is not used."""
        return "scan", [["random_walk"], "random_walk_k", 0.0, 1.0, 1], {}


# ==========================This is the necessary code to start the agent========================== #

use_tiled = os.getenv("USE_TILED", None) in (True, "yes", 1, "True", "true") or False
agent = ClusterAgentMock(k_clusters=3, use_tiled=use_tiled)


@startup_decorator
def startup():
    agent.start()


@shutdown_decorator
def shutdown_agent():
    return agent.stop()


register_variable("Agent Name", agent, "instance_name")
# ==========================This is the necessary code to start the agent========================== #
