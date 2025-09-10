from typing import Literal

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
import xarray as xr
from ophyd import Component as Cpt
from ophyd import Device, Signal, SoftPositioner
from scipy.spatial import ConvexHull


class DiffractionWaferSim:
    def __init__(self, ground_truth: xr.Dataset):
        """
        A simulated wafer that can be scanned over in x and y, returning EDX, phase fractions, and I(q).
        Datasets are available assets as .nc files.
        The wafer is circular with x/y coordinates about (0,0), and a dataset filled with nearest neighbors outside
        the convex hull of the data points.
        Practically, it is unlikely that the phase fractions can be measured directly,
        but they are included here for completeness in testing and simulation.

        The dataset must contain the following keys:
        - x: x coordinates of measurement points
        - y: y coordinates of measurement points
        - element_weights: EDX element weights at each measurement point
        - phase_weights: phase fractions at each measurement point
        - iq: I(q) at each measurement point, shape (n_points, n_q)
        - xy: 2D array of shape (n_points, 2) for convex hull calculations
        """

        self.ground_truth = ground_truth
        self.iq_shape = self.ground_truth["iq"].shape[
            1:
        ]  # Extract the shape (tuple_index, q_points)

        self.convex_hull = ConvexHull(self.ground_truth["coords_valid"].values)

        self.radius = (self.ground_truth.x.max() - self.ground_truth.x.min()) / 2

    def in_hull(self, test_points, tol=1e-12):
        """
        test_points: (m, d) array of query points (or shape (d,) for one point)
        tol: numerical tolerance for the half-space test
        """
        A = self.convex_hull.equations[:, :-1]  # normals
        b = self.convex_hull.equations[:, -1]  # offsets
        X = np.atleast_2d(test_points)
        return np.all(A @ X.T + b[:, None] <= tol, axis=0)

    def _get_value_at_coordinates(
        self,
        x_coord: float,
        y_coord: float,
        key: Literal["element_weights", "phase_weights", "iq"],
    ):
        """Get value for a given key at the specified x and y coordinates.

        Parameters
        ----------
        x_coord : float
        y_coord :
        key : Literal["element_weights", "phase_weights", "iq

        Returns
        -------
        np.ndarray
            The value at the specified coordinates, or zeros with noise if outside the wafer.
        """
        if x_coord**2 + y_coord**2 > self.radius**2:
            arr = np.zeros_like(self.ground_truth[key][0, 0])
            return arr + np.random.randn(*arr.shape) * 0.01
        elif self.in_hull(np.array([x_coord, y_coord])):
            return (
                self.ground_truth[key]
                .interp(x=x_coord, y=y_coord, method="linear")
                .values
            )
        else:
            return (
                self.ground_truth[key]
                .interp(x=x_coord, y=y_coord, method="nearest")
                .values
            )


wafer_x = SoftPositioner(name="wafer_x", init_pos=0, limits=(-5, 5))
wafer_y = SoftPositioner(name="wafer_y", init_pos=0, limits=(-5, 5))

WAFER_SIM = DiffractionWaferSim(
    ground_truth=xr.open_dataset(
        "/usr/local/share/sim_datasets/AlLiFe-diffraction-filled.nc"
    )
)


class WaferSimEDX(Signal):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wafer_sim = WAFER_SIM
        self._readback = self.get()

    def get(self):
        return np.array(
            self.wafer_sim._get_value_at_coordinates(
                wafer_x.position, wafer_y.position, "element_weights"
            )
        )


class WaferSimPhases(WaferSimEDX):
    def get(self):
        return np.array(
            self.wafer_sim._get_value_at_coordinates(
                wafer_x.position, wafer_y.position, "phase_weights"
            )
        )


class WaferSimXRD(WaferSimEDX):
    def get(self):
        return np.array(
            self.wafer_sim._get_value_at_coordinates(
                wafer_x.position, wafer_y.position, "iq"
            )
        )


class WaferMeasurement(Device):
    edx = Cpt(WaferSimEDX, name="edx")
    phases = Cpt(WaferSimPhases, name="phases")
    ioq = Cpt(WaferSimXRD, name="ioq")


wafer_measurement = WaferMeasurement(name="wafer_measurement")


def wafer_move_and_measure(*, x: float, y: float, md: None | dict = None):
    """Simple plan to move to an (x,y) position on the simulated wafer and take a measurement.

    Parameters
    ----------
    x : float
        x coordinate to move to
    y : float
        y coordinate to move to
    md : None | dict, optional
        metadata to add to the run, by default None

    Returns
    -------
    generator
        generator that can be yielded from in a bluesky run

    """
    _md = md or {}

    @bpp.run_decorator(md=_md)
    def inner():
        yield from bps.declare_stream(
            wafer_x, wafer_y, wafer_measurement, name="primary"
        )
        yield from bps.mv(wafer_x, x)
        yield from bps.mv(wafer_y, y)
        yield from bps.trigger_and_read([wafer_x, wafer_y, wafer_measurement])

    return (yield from inner())
