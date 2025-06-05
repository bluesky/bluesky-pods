"""Special use handler for training."""

import threading
import numpy as np

from ophyd import Device, Component as Cpt, Signal, DeviceStatus
from ophyd.device import Staged
from ophyd.signal import EpicsSignal, EpicsSignalRO


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


class SetInProgress(RuntimeError): ...


class Eurotherm(Device):
    """
    Copied from nslsii package to remove dependency on nslsii.

    This class is used for integrating with Eurotherm controllers.

    This is used for Eurotherm controllers and is designed to ensure that the
    set returns 'done' status only after the temperature has reached
    equilibrium at the required value not when it first reaches the required
    value. This is done via the attributes `self.equilibrium_time` and
    `self.tolerance`. It only returns `done` if `self.readback` remains within
    `self.tolerance` of `self.setpoint` over `self.equilibrium_time`. A third
    attribute, `self.timeout`, is used to determeine the maximum time to wait
    for equilibrium. If it takes longer than this it raises a TimeoutError.

    Parameters
    ----------
    pv_prefix : str.
        The PV prefix that is common to the readback and setpoint PV's.
    """

    def __init__(self, pv_prefix, **kwargs):
        super().__init__(pv_prefix, **kwargs)
        self._set_lock = threading.Lock()

        # defining these here so that they can be used by `set` and `start`
        self._cb_timer = None
        self._cid = None

    # Setup some new signals required for the moving indicator logic
    equilibrium_time = Cpt(Signal, value=5, kind="config")
    timeout = Cpt(Signal, value=500, kind="config")
    tolerance = Cpt(Signal, value=1, kind="config")

    # Add the readback and setpoint components
    setpoint = Cpt(EpicsSignal, "T-SP", kind="normal")
    readback = Cpt(EpicsSignal, "T-RB", kind="hinted")

    # define the new set method with the new moving indicator
    def set(self, value):
        # check that a set is not in progress, and if not set the lock.
        if not self._set_lock.acquire(blocking=False):
            raise SetInProgress(
                "attempting to set {} ".format(self.name) + "while a set is in progress"
            )

        # define some required values
        set_value = value
        status = DeviceStatus(self)

        initial_timestamp = None

        # grab these values here to avoidmutliple calls.
        equilibrium_time = self.equilibrium_time.get()
        tolerance = self.tolerance.get()

        # setup a cleanup function for the timer, this matches including
        # timeout in `status` but also ensures that the callback is removed.
        def timer_cleanup():
            print(
                "Set of {} timed out after {} s".format(self.name, self.timeout.get())
            )
            self._set_lock.release()
            self.readback.clear_sub(status_indicator)
            status._finished(success=False)

        self._cb_timer = threading.Timer(self.timeout.get(), timer_cleanup)

        # set up the done moving indicator logic
        def status_indicator(value, timestamp, **kwargs):
            # add a Timer to ensure that timeout occurs.
            if not self._cb_timer.is_alive():
                self._cb_timer.start()

            nonlocal initial_timestamp
            if abs(value - set_value) < tolerance:
                if initial_timestamp:
                    if (timestamp - initial_timestamp) > equilibrium_time:
                        status._finished()
                        self._cb_timer.cancel()
                        self._set_lock.release()
                        self.readback.clear_sub(status_indicator)
                else:
                    initial_timestamp = timestamp
            else:
                initial_timestamp = None

        # Start the move.
        self.setpoint.put(set_value)

        # subscribe to the read value to indicate the set is done.
        self._cid = self.readback.subscribe(status_indicator)

        # hand the status object back to the RE
        return status

    def stop(self, success=False):
        # overide the lock, cancel the timer and remove the subscription on any
        # in progress sets
        self._set_lock.release()
        self._cb_timer.cancel()
        self.readback.unsubscribe(self._cid)
        # set the controller to the current value (best option we came up with)
        self.set(self.readback.get())


class Thermo(Eurotherm):
    # override these signals to account for different PV names
    readback = Cpt(EpicsSignal, "I", kind="hinted")
    setpoint = Cpt(EpicsSignal, "SP", kind="normal")

    # specific to the sumulator
    K = Cpt(EpicsSignal, "K", kind="config")
    omega = Cpt(EpicsSignal, "omega", kind="config")
    Tvar = Cpt(EpicsSignal, "Tvar", kind="config")


class RandomWalk(Device):
    dt = Cpt(EpicsSignal, "dt", kind="config")
    x = Cpt(EpicsSignal, "x", kind="hinted")


class Simple(Device):
    A = Cpt(EpicsSignal, "A")
    B = Cpt(EpicsSignal, "B")
    C = Cpt(EpicsSignal, "C")


class TriggeredIOC(Device):
    gain = Cpt(EpicsSignal, "gain", kind="config")
    exposure_time = Cpt(EpicsSignal, "exposure_time", kind="config")
    enabled = Cpt(EpicsSignal, "enabled", kind="config")
    enabled = Cpt(EpicsSignal, "enabled", kind="config")

    reading = Cpt(EpicsSignal, "reading", kind="hinted")

    acquire = Cpt(EpicsSignal, "reading", kind="omitted", put_complete=True)

    def trigger(self, *args, **kwargs):
        return self.acquire.set(*args, **kwargs)
