import logging
import os
import uuid
from abc import ABC
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
from bluesky_adaptive.agents.base import Agent, AgentConsumer
from bluesky_adaptive.agents.sklearn import ClusterAgentBase
from bluesky_adaptive.server import register_variable, shutdown_decorator, startup_decorator
from bluesky_queueserver_api.http import REManagerAPI
from databroker.client import BlueskyRun
from numpy.polynomial.polynomial import polyfit, polyval
from numpy.typing import ArrayLike
from scipy.stats import rv_discrete
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from tiled.client import from_uri

logger = logging.getLogger(__name__)


def discretize(value: np.typing.ArrayLike, resolution: np.typing.ArrayLike):
    return np.floor(value / resolution)


def make_hashable(x):
    try:
        return tuple(map(float, x))
    except TypeError:
        return float(x)


def make_wafer_grid_list(x_min, x_max, y_min, y_max, step):
    """
    Make the list of all of the possible 2d points that lie within a circle of the origin
    """
    x = np.arange(x_min, x_max, step)
    y = np.arange(y_min, y_max, step)
    xx, yy = np.meshgrid(x, y)
    center = np.array([x_min + (x_max - x_min) / 2, y_min + (y_max - y_min) / 2])
    distance = np.sqrt((xx - center[0]) ** 2 + (yy - center[1]) ** 2)
    radius = min((x_max - x_min) / 2, (y_max - y_min) / 2) * 0.95
    return np.array([xx[distance < radius], yy[distance < radius]]).T


class PodBaseAgent(Agent, ABC):
    def __init__(
        self,
        *args,
        motor_names=["wafer_x", "wafer_y"],
        motor_origins=[0.0, 0.0],
        motor_resolution=0.1,
        data_key: str = "wafer_measurement_ioq",
        metadata=None,
        **kwargs,
    ):
        self._motor_names = motor_names
        self._motor_resolution = motor_resolution
        self._motor_origins = np.array(motor_origins)
        self._data_key = data_key
        _default_kwargs = self.get_beamline_objects()
        _default_kwargs.update(kwargs)

        md = dict(
            motor_names=self.motor_names,
            motor_resolution=self.motor_resolution,
        )
        metadata = metadata or {}
        md.update(metadata)
        super().__init__(*args, metadata=md, **_default_kwargs)

    def server_registrations(self) -> None:
        self._register_property("motor_resolution")
        self._register_property("motor_names")
        self._register_property("data_key")
        return super().server_registrations()

    @property
    def motor_names(self):
        """Name of motor to be used as the independent variable in the experiment"""
        return self._motor_names

    @motor_names.setter
    def motor_names(self, value: str):
        self._motor_names = value

    @property
    def motor_resolution(self):
        """Minimum resolution for measurement in milimeters, i.e. (beam width)/2"""
        return self._motor_resolution

    @motor_resolution.setter
    def motor_resolution(self, value: float):
        self._motor_resolution = value

    @property
    def data_key(self):
        return self._data_key

    @data_key.setter
    def data_key(self, value: str):
        self._data_key = value
        self.close_and_restart(clear_tell_cache=True)

    def unpack_run(self, run):
        data = run["primary"]["data"].read()
        x = np.array([data[motor_name].data for motor_name in self.motor_names]).flatten()
        y = np.array(data[self.data_key])
        if y.ndim == 3:
            y = y[0]
        if y.ndim == 2:
            y = y[1]
        return x, y

    def measurement_plan(self, point):
        return "agent_move_and_measure", [], {"x": point[0], "y": point[1]}

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
            tiled_data_node=from_uri("http://tld:8000/", api_key="ABCDABCD"),
            tiled_agent_node=from_uri("http://tld:8000/", api_key="ABCDABCD"),
            qserver=qs,
        )


class PassiveKmeansAgent(PodBaseAgent, ClusterAgentBase):
    def __init__(self, k_clusters, *args, **kwargs):
        estimator = KMeans(k_clusters, n_init="auto")
        _default_kwargs = self.get_beamline_objects()
        _default_kwargs.update(kwargs)
        super().__init__(*args, estimator=estimator, **kwargs)

    def clear_caches(self):
        self.independent_cache = []
        self.dependent_cache = []

    def close_and_restart(self, *, clear_tell_cache=False, retell_all=False, reason=""):
        if clear_tell_cache:
            self.clear_caches()
        return super().close_and_restart(clear_tell_cache=clear_tell_cache, retell_all=retell_all, reason=reason)

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

    def tell(self, x, y):
        """Update tell using relative info"""
        x = x - self._motor_origins
        doc = super().tell(x, y)
        doc["absolute_position_offset"] = self._motor_origins
        return doc

    def report(self, **kwargs):
        arr = np.array(self.observable_cache)
        self.model.fit(arr)
        return dict(
            cluster_centers=self.model.cluster_centers_,
            cache_len=len(self.independent_cache),
            latest_data=self.tell_cache[-1],
        )

    @classmethod
    def hud_from_report(
        cls,
        run: BlueskyRun,
        report_idx=None,
        scaler: float = 1000.0,
        offset: float = 1.0,
        reorder_labels: bool = True,
    ):
        """Creates waterfall plot of spectra from a previously generated agent report.
        Waterfall plot of spectra will use 'scaler' to rescale each spectra prior to plotting.
        Waterfall plot will then use 'offset' to offset each spectra.

        Parameters
        ----------
        run : BlueskyRun
            Agent run to reference
        report_idx : int, optional
            Report index, by default most recent
        scaler : float, optional
            Rescaling of each spectra prior to plotting, by default 1000.0
        offset : float, optional
            Offset of plots to be tuned with scaler for waterfal, by default 1.0
        reorder_labels : bool, optional
            Optionally reorder the labelling so the first label appears first in the list, by default True

        Returns
        -------
        _type_
            _description_
        """
        _, data = cls.remodel_from_report(run, idx=report_idx)
        labels = data["clusters"]
        # distances = data["distances"]
        # cluster_centers = data["cluster_centers"]
        independent_vars = data["independent_vars"]
        observables = data["observables"]

        if reorder_labels:
            labels = cls.ordered_relabeling(labels)

        fig = plt.figure(dpi=100)
        ax = fig.add_subplot(2, 1, 1)
        for i in range(len(labels)):
            ax.scatter(independent_vars[i], labels[i], color=f"C{labels[i]}")
        ax.set_xlabel("measurement axis")
        ax.set_ylabel("K-means label")

        ax = fig.add_subplot(2, 1, 2)
        for i in range(len(observables)):
            plt.plot(
                np.arange(observables.shape[1]),
                scaler * observables[i] + i * offset,
                color=f"C{labels[i]}",
                alpha=0.1,
            )
        ax.set_xlabel("Dataset index")
        ax.set_ylabel("Intensity")
        fig.tight_layout()

        return fig

    @staticmethod
    def ordered_relabeling(x):
        """assume x is a list of labels,
        return same labeling structure, but with label names introduced sequentially.

        e.g. [4,4,1,1,2,1,3] -> [1,1,2,2,3,2,4]"""
        convert_dict = {}
        next_label = 0
        new_x = []
        for i in range(len(x)):
            if x[i] not in convert_dict.keys():
                convert_dict[x[i]] = next_label
                next_label += 1
            # x[i] = convert_dict[x[i]]

        for i in range(len(x)):
            new_x.append(convert_dict[x[i]])

        return new_x


class ActiveKmeansAgent(PassiveKmeansAgent):
    def __init__(self, *args, bounds: ArrayLike, **kwargs):
        super().__init__(*args, **kwargs)
        self._bounds = bounds
        self.knowledge_cache = set()  # Discretized knowledge cache of previously asked/told points

    @property
    def name(self):
        return "ActiveKMeans"

    @property
    def bounds(self):
        return self._bounds

    @bounds.setter
    def bounds(self, value: ArrayLike):
        self._bounds = value

    def server_registrations(self) -> None:
        self._register_property("bounds")
        return super().server_registrations()

    def tell(self, x, y):
        """A tell that adds to the local discrete knowledge cache, as well as the standard caches"""
        doc = super().tell(x, y)
        self.knowledge_cache.add(make_hashable(discretize(doc["independent_variable"], self.motor_resolution)))
        return doc

    def _sample_uncertainty_proxy(self, batch_size=1):
        """Some Dan Olds magic to cast the distance from a cluster as an uncertainty. Then sample there

        Parameters
        ----------
        batch_size : int, optional

        Returns
        -------
        samples : ArrayLike
        centers : ArrayLike
            Kmeans centers for logging
        """
        # Borrowing from Dan's jupyter fun
        # from measurements, perform k-means
        try:
            sorted_independents, sorted_observables = zip(
                *sorted(zip(self.independent_cache, self.observable_cache))
            )
        except ValueError:
            # Multidimensional case
            sorted_independents, sorted_observables = zip(
                *sorted(zip(self.independent_cache, self.observable_cache), key=lambda x: (x[0][0], x[0][1]))
            )

        sorted_independents = np.array(sorted_independents)
        sorted_observables = np.array(sorted_observables)
        self.model.fit(sorted_observables)
        # retreive centers
        centers = self.model.cluster_centers_

        if self.bounds.size == 2:
            # One dimensional case, Use the Dan Olds approach
            # calculate distances of all measurements from the centers
            distances = self.model.transform(sorted_observables)
            # determine golf-score of each point (minimum value)
            min_landscape = distances.min(axis=1)
            # Assume a 1d scan
            # generate 'uncertainty weights' - as a polynomial fit of the golf-score for each point
            _x = np.arange(*self.bounds, self.motor_resolution)
            if batch_size is None:
                batch_size = len(_x)
            uwx = polyval(_x, polyfit(sorted_independents, min_landscape, deg=5))
            # Chose from the polynomial fit
            return pick_from_distribution(_x, uwx, num_picks=batch_size), centers
        else:
            # assume a 2d scan, use a linear model to predict the uncertainty
            grid = make_wafer_grid_list(*self.bounds.ravel(), step=self.motor_resolution)
            labels = self.model.predict(sorted_observables)
            proby_preds = LogisticRegression().fit(sorted_independents, labels).predict_proba(grid)
            shannon = -np.sum(proby_preds * np.log(1 / proby_preds), axis=-1)
            top_indicies = np.argsort(shannon) if batch_size is None else np.argsort(shannon)[-batch_size:]
            return grid[top_indicies], centers

    def ask(self, batch_size=1):
        """Get's a relative position from the agent. Returns a document and hashes the suggestion for redundancy"""
        suggestions, centers = self._sample_uncertainty_proxy(None)
        kept_suggestions = []
        if not isinstance(suggestions, Iterable):
            suggestions = [suggestions]
        # Keep non redundant suggestions and add to knowledge cache
        for suggestion in suggestions:
            hashable_suggestion = make_hashable(discretize(suggestion, self.motor_resolution))
            if hashable_suggestion in self.knowledge_cache:
                logger.warn(
                    f"Suggestion {suggestion} is ignored as already in the knowledge cache: {hashable_suggestion}"
                )
                continue
            else:
                self.knowledge_cache.add(hashable_suggestion)
                kept_suggestions.append(suggestion)
            if len(kept_suggestions) >= batch_size:
                break

        base_doc = dict(
            cluster_centers=centers,
            cache_len=(
                len(self.independent_cache)
                if isinstance(self.independent_cache, list)
                else self.independent_cache.shape[0]
            ),
            latest_data=self.tell_cache[-1],
            requested_batch_size=batch_size,
            redundant_points_discarded=batch_size - len(kept_suggestions),
            absolute_position_offset=self._motor_origins,
        )
        docs = [dict(suggestion=suggestion, **base_doc) for suggestion in kept_suggestions]

        return docs, kept_suggestions

    def measurement_plan(self, relative_point: ArrayLike):
        """Send measurement plan absolute point from reltive position"""
        absolute_point = relative_point + self._motor_origins
        return super().measurement_plan(absolute_point)


def current_dist_gen(x, px):
    """from distribution defined by p(x), produce a discrete generator.
    This helper function will normalize px as required, and return the generator ready for use.

    use:

    my_gen = current_dist(gen(x,px))

    my_gen.rvs() = xi # random variate of given type

    where xi is a random discrete value, taken from the set x, with probability px.

    my_gen.rvs(size=10) = np.array([xi1, xi2, ..., xi10]) # a size=10 array from distribution.

    If you want to return the probability mass function:

    my_gen.pmf

    See more in scipy.stats.rv_discrete
    """
    px[px < 0] = 0  # ensure non-negativitiy
    return rv_discrete(name="my_gen", values=(x, px / sum(px)))


def pick_from_distribution(x, px, num_picks=1):
    my_gen = current_dist_gen(x, px)
    if num_picks != 1:
        return my_gen.rvs(size=num_picks)
    else:
        return my_gen.rvs()


agent = ActiveKmeansAgent(
    bounds=np.array([(-5, 5), (-5, 5)]),
    k_clusters=3,
    ask_on_tell=False,
    report_on_tell=False,
)


@startup_decorator
def startup():
    agent.start()


@shutdown_decorator
def shutdown_agent():
    return agent.stop()


register_variable("Tell Cache", agent, "tell_cache")
register_variable("Agent Name", agent, "instance_name")
