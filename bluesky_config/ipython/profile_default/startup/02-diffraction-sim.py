from pathlib import Path

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
import xarray as xr
from ophyd import Component as Cpt
from ophyd import Device, Signal, SoftPositioner
from scipy.interpolate import griddata
from scipy.spatial import ConvexHull


class WaferSim:
    def __init__(self, ground_truth):
        """ground_truth is the netcdf file that gets loaded of the wafer, with a specific format"""
        """ Has a dataset (knows everything) and a sample (knows only what has been measured) """

        self.ground_truth = ground_truth
        self.iq_shape = self.ground_truth["iq"].shape[1:]  # Extract the shape (tuple_index, q_points)

    def _is_inside_convex_hull(self, x_coord, y_coord, coords):
        """checks if points are inside the wafer"""
        hull = ConvexHull(coords)  # can access vertices and simplices (edges) as attributes

        # here we check if inside using the winding number algorithm
        n = len(hull.vertices)
        winding_number = 0

        for i in range(n):
            x1, y1 = hull.points[hull.vertices[i]]
            x2, y2 = hull.points[hull.vertices[(i + 1) % n]]

            if y1 <= y_coord:
                if y2 > y_coord and (x2 - x1) * (y_coord - y1) - (x_coord - x1) * (y2 - y1) > 0:
                    winding_number += 1
            else:
                if y2 <= y_coord and (x2 - x1) * (y_coord - y1) - (x_coord - x1) * (y2 - y1) < 0:
                    winding_number -= 1

        return winding_number != 0

    def _get_value_at_coordinates(self, x_coord, y_coord, key, method="interpolate"):
        """given x and y, return a tuple of numpy arrays (q, Iq)"""

        if method == "nearest":
            distances = np.sqrt(
                (self.ground_truth["x"].values - x_coord) ** 2 + (self.ground_truth["y"].values - y_coord) ** 2
            )
            nearest_index = int(distances.argmin())
            nearest_value = self.ground_truth[key].isel(index=nearest_index).values
            return nearest_value
        elif method == "interpolate":
            if self._is_inside_convex_hull(x_coord, y_coord, self.ground_truth["xy"].values):
                interpolated_value = griddata(
                    points=(self.ground_truth["x"].values, self.ground_truth["y"].values),
                    values=self.ground_truth[key].values,
                    xi=(x_coord, y_coord),
                    method="linear",
                )
                return interpolated_value
            else:
                raise ValueError(
                    f"xy position {x_coord, y_coord} outside bounds - enter coordinates within bounds"
                )
        else:
            raise NameError(f"method not recognized - must be 'nearest' or 'interpolate' and input was {method}")


wafer_x = SoftPositioner(name="wafer_x", init_pos=0, limits=(-5, 5))
wafer_y = SoftPositioner(name="wafer_y", init_pos=0, limits=(-5, 5))

WAFER_SIM = WaferSim(ground_truth=xr.open_dataset(Path(__file__).parent / "AlLiFe-sim-ds.nc"))


class WaferSimEDX(Signal):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wafer_sim = WAFER_SIM
        self._readback = self.get()

    def get(self):
        return np.array(
            self.wafer_sim._get_value_at_coordinates(wafer_x.position, wafer_y.position, "element_weights")
        )


class WaferSimPhases(WaferSimEDX):
    def get(self):
        return np.array(
            self.wafer_sim._get_value_at_coordinates(wafer_x.position, wafer_y.position, "phase_weights")
        )


class WaferSimXRD(WaferSimEDX):
    def get(self):
        return np.array(self.wafer_sim._get_value_at_coordinates(wafer_x.position, wafer_y.position, "iq"))


class WaferMeasurement(Device):
    edx = Cpt(WaferSimEDX, name="edx")
    phases = Cpt(WaferSimPhases, name="phases")
    ioq = Cpt(WaferSimXRD, name="ioq")


wafer_measurement = WaferMeasurement(name="wafer_measurement")


def agent_move_and_measure(*, x, y, md=None):
    _md = md or {}

    @bpp.run_decorator(md=_md)
    def inner():
        # yield from bps.open_run()
        yield from bps.declare_stream(wafer_x, wafer_y, wafer_measurement, name="primary")
        yield from bps.mv(wafer_x, x)
        yield from bps.mv(wafer_y, y)
        yield from bps.trigger_and_read([wafer_x, wafer_y, wafer_measurement])
        # yield from bps.close_run()

    return (yield from inner())
