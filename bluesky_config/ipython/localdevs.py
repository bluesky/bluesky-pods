"""Special use handler for training."""
import numpy as np

from ophyd import Device, Component as Cpt, Signal, DeviceStatus
from ophyd.device import Staged
from ophyd.signal import EpicsSignal, EpicsSignalRO

from nslsii.temperature_controllers import Eurotherm


class NewtonDirectSimulator(Device):
    gap = Cpt(Signal, value=0, kind="hinted")
    image = Cpt(Signal, kind="normal")

    @staticmethod
    def _newton(gap, R, k):
        """
        Simulate Newton's Rings.

        Parameters
        ----------
        gap : float
            The closest distance between the sphere and the surface

        R : float
            Radius of the sphere

        k : float
            Wave number of the incoming light

        """
        X, Y = np.ogrid[-10:10:128j, -10:10:128j]
        d = np.hypot(X, Y)
        phi = ((gap + d * np.tan(np.pi / 2 - np.arcsin(d / R))) * 2) * k

        return 1 + np.cos(phi)

    def _compute(self):

        self.image.put(self._newton(self.gap.get(), self._R, self._k))

    def __init__(self, R, k, **kwargs):
        super().__init__(**kwargs)
        self._R = R
        self._k = k
        self.image.put(self._compute())

    def trigger(self):
        if self._staged != Staged.yes:
            raise RuntimeError("This device must be staged before being triggered")
        st = DeviceStatus(self)
        self._compute()
        st.set_finished()
        return st


class Det(Device):
    det = Cpt(EpicsSignal, ":det", kind="hinted")
    exp = Cpt(EpicsSignal, ":exp", kind="config")


# here there be 🐉🐉🐉🐉🐉🐉


class Spot(Device):
    img = Cpt(EpicsSignal, ":det")
    roi = Cpt(EpicsSignal, ":img_sum", kind="hinted")
    exp = Cpt(EpicsSignal, ":exp", kind="config")
    shutter_open = Cpt(EpicsSignal, ":shutter_open", kind="config")
    array_size = Cpt(EpicsSignalRO, ":ArraySize_RBV", kind="config")

    def trigger(self):
        return self.img.trigger()


class Thermo(Eurotherm):
    # override these signals to account for different PV names
    readback = Cpt(EpicsSignal, "I", kind="hinted")
    setpoint = Cpt(EpicsSignal, "SP", kind="normal")

    # specific to the sumulator
    K = Cpt(EpicsSignal, "K", kind="config")
    omega = Cpt(EpicsSignal, "omega", kind="config")
    Tvar = Cpt(EpicsSignal, "Tvar", kind="config")

    # override these to set kind correctly, delete when nslsii updated
    equilibrium_time = Cpt(Signal, value=5, kind="config")
    timeout = Cpt(Signal, value=500, kind="config")
    tolerance = Cpt(Signal, value=1, kind="config")


class RandomWalk(Device):
    dt = Cpt(EpicsSignal, "dt", kind="config")
    x = Cpt(EpicsSignal, "x", kind="hinted")


class Simple(Device):
    A = Cpt(EpicsSignal, "A")
    B = Cpt(EpicsSignal, "B")
    C = Cpt(EpicsSignal, "C")


class TriggeredIOC(Device):
    gain = Cpt(EpicsSignal, 'gain', kind='config')
    exposure_time = Cpt(EpicsSignal, 'exposure_time', kind='config')
    enabled = Cpt(EpicsSignal, 'enabled', kind='config')
    enabled = Cpt(EpicsSignal, 'enabled', kind='config')

    reading = Cpt(EpicsSignal, 'reading', kind='hinted')

    acquire = Cpt(EpicsSignal, 'reading', kind='omitted', put_complete=True)

    def trigger(self, *args, **kwargs):
        return self.acquire.set(*args, **kwargs)
