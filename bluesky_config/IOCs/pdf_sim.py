#!/usr/bin/env python3
import time
import functools
import contextvars

import numpy as np

from caproto.server import pvproperty, PVGroup, SubGroup, ioc_arg_parser, run
from caproto import ChannelType

from caproto.server import pvproperty, PVGroup, SubGroup, ioc_arg_parser, run
from textwrap import dedent
from caproto.server.records import MotorFields

internal_process = contextvars.ContextVar("internal_process", default=False)


def no_reentry(func):
    @functools.wraps(func)
    async def inner(*args, **kwargs):
        if internal_process.get():
            return
        try:
            internal_process.set(True)
            return await func(*args, **kwargs)
        finally:
            internal_process.set(False)

    return inner


async def broadcast_precision_to_fields(record):
    """Update precision of all fields to that of the given record."""

    precision = record.precision
    for field, prop in record.field_inst.pvdb.items():
        if hasattr(prop, "precision"):
            await prop.write_metadata(precision=precision)


# lifted from https://github.com/caproto/caproto/pull/626/
# Modifications will make it back eventually
class FakeMotor(PVGroup):
    motor = pvproperty(value=0.0, name="", record="motor", precision=3)

    def __init__(
        self,
        *args,
        velocity=0.1,
        precision=3,
        acceleration=1.0,
        resolution=1e-6,
        tick_rate_hz=10.0,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.tick_rate_hz = tick_rate_hz
        self.defaults = {
            "velocity": velocity,
            "precision": precision,
            "acceleration": acceleration,
            "resolution": resolution,
        }
        self.stale = True

    @motor.putter
    async def motor(self, instance, value):
        self.stale = True
        return value

    @motor.startup
    async def motor(self, instance, async_lib):
        self.async_lib = async_lib

        await self.motor.write_metadata(precision=self.defaults["precision"])
        await broadcast_precision_to_fields(self.motor)

        fields = self.motor.field_inst  # type: MotorFields
        await fields.velocity.write(self.defaults["velocity"])
        await fields.seconds_to_velocity.write(self.defaults["acceleration"])
        await fields.motor_step_size.write(self.defaults["resolution"])

        while True:
            dwell = 1.0 / self.tick_rate_hz
            target_pos = self.motor.value
            diff = target_pos - fields.user_readback_value.value
            # compute the total movement time based an velocity
            total_time = abs(diff / fields.velocity.value)
            # compute how many steps, should come up short as there will
            # be a final write of the return value outside of this call
            num_steps = int(total_time // dwell)
            if abs(diff) < 1e-9 and not self.stale:
                if fields.stop.value != 0:
                    await fields.stop.write(0)
                await async_lib.library.sleep(dwell)
                continue

            # make sure we win the race
            if fields.stop.value != 0:
                await fields.stop.write(0)

            await fields.done_moving_to_value.write(0)
            await fields.motor_is_moving.write(1)

            readback = fields.user_readback_value.value
            step_size = diff / num_steps if num_steps > 0 else 0.0
            resolution = max((fields.motor_step_size.value, 1e-10))

            for _ in range(num_steps):
                if fields.stop.value != 0:
                    await fields.stop.write(0)
                    await self.motor.write(readback)
                    break
                if fields.stop_pause_move_go.value == "Stop":
                    await self.motor.write(readback)
                    break

                readback += step_size
                raw_readback = readback / resolution
                await fields.user_readback_value.write(readback)
                await fields.dial_readback_value.write(readback)
                await fields.raw_readback_value.write(raw_readback)
                await async_lib.library.sleep(dwell)
            else:
                # Only executed if we didn't break
                await fields.user_readback_value.write(target_pos)

            await fields.motor_is_moving.write(0)
            await fields.done_moving_to_value.write(1)
            self.stale = False


def _arrayify(func):
    @functools.wraps(func)
    def inner(*args):
        return func(*(np.asarray(a) for a in args))

    return inner


class SampleDetector(PVGroup):
    # clear the detector history
    reset_history = pvproperty(value=0, dtype=int, record="bi")

    # shutter
    shutter = pvproperty(
        value="Open",
        enum_strings=["Open", "Closed"],
        record="bi",
        dtype=ChannelType.ENUM,
    )

    # with accounting logic
    @shutter.putter
    async def shutter(self, instance, value):
        if value == "Open":
            if len(self.history["light"]) and len(self.history["light"][-1]) == 1:
                pass
            else:
                self.history["light"].append((time.monotonic(),))

        if value == "Closed":
            if len(self.history["light"]) and len(self.history["light"][-1]) == 1:
                (opened_time,) = self.history["light"].pop()
                self.history["light"].append((opened_time, time.monotonic()))
            else:
                pass
        print(self.history)
        return value

    sample = pvproperty(value=0, dtype=int, record="ai")

    @sample.putter
    async def sample(self, instance, value):
        current_value = instance.value
        if current_value != value:  # check if need to change anything
            if current_value:
                (loaded_time,) = self.history["sample"].pop()
                self.history["sample"].append((loaded_time, time.monotonic()))
            if value:
                self.history["sample"].append((time.monotonic(),))
                self.history["image"].append(self.patterns[value])

        return value

    @reset_history.putter
    async def reset_history(self, instance, async_lib):
        self.history = {
            "sample": [],
            "light": [],
            "image": [],
            "decay_a": 1000,
            "panel_amp": 50,
            "panel_oset": 10,
            "panel_wid": 128,
            "noise": 50,
            "panel_wl": 80000,
            "action_time": 0.5,
            "perfect_data": False,
        }

    exposure_time = pvproperty(value=0.1, dtype=float, record="ai")
    num_images = pvproperty(value=10, dtype=int, record="ai")
    image = pvproperty(
        value=[], dtype=int, alarm_group="acq", max_length=1_000 * 1_000, read_only=True
    )
    image_h = pvproperty(
        value=0, dtype=int, alarm_group="acq", max_length=1, read_only=True
    )
    image_w = pvproperty(
        value=0, dtype=int, alarm_group="acq", max_length=1, read_only=True
    )
    total = pvproperty(value=0, dtype=int, record="ao", read_only=True)

    acquire = pvproperty(
        value="idle",
        enum_strings=["idle", "acquiring"],
        dtype=ChannelType.ENUM,
        alarm_group="acq",
    )

    enabled = pvproperty(
        value="on",
        enum_strings=["off", "on"],
        dtype=ChannelType.ENUM,
        alarm_group="acq",
    )

    @acquire.putter
    @no_reentry
    async def acquire(self, instance, value):
        if self.enabled.value == "off":
            raise RuntimeError("Device must be enabled")
        if not instance.ev.is_set():
            await instance.ev.wait()
            return "idle"

        if value == "acquiring":
            instance.ev.clear()
            try:
                await instance.write(1)
                f = make_illumination_combinations(
                    self.history["sample"],
                    self.history["image"],
                    self.history["light"],
                    self.history["decay_a"],
                )
                arr = f(time.monotonic())
                # add panel effect to image
                varying_pan_amp = (
                    np.sin(time.monotonic() * (2.0 * np.pi / self.history["panel_wl"]))
                    + 1.0
                )

                arr += det_panels(
                    arr.shape,
                    oset=self.history["panel_oset"],
                    wid=self.history["panel_wid"],
                    amp=varying_pan_amp * self.history["panel_amp"],
                )

                # add noisy effect to image
                arr += noisy_im(arr.shape, noise=self.history["noise"])

                await instance.async_lib.library.sleep(
                    self.exposure_time.value * self.num_images.value
                )
                h, w = arr.shape
                await self.image_h.write(h)
                await self.image_w.write(w)
                await self.total.write(arr.sum())
                await self.image.write(arr.ravel())

            finally:
                instance.ev.set()

        return "idle"

    @acquire.startup
    async def acquire(self, instance, async_lib):
        # monkey patch the instance like whoa
        instance.async_lib = async_lib
        instance.ev = async_lib.Event()
        instance.ev.set()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.history = {
            "sample": [],
            "light": [],
            "image": [],
            "decay_a": 1000,
            "panel_amp": 50,
            "panel_oset": 10,
            "panel_wid": 128,
            "noise": 50,
            "panel_wl": 80000,
            "action_time": 0.5,
            "perfect_data": False,
        }

        # Map samples to patterns.
        SHAPE = (640, 380)
        self.patterns = {}
        self.intensities = {}

        x = np.linspace(0, 30, num=301)
        for i in range(1, 5):
            intensity = make_random_peaks(x) * 1000.0
            image = generate_image(x, intensity, SHAPE)
            self.intensities[i] = intensity
            self.patterns[i] = image


def det_panels(shape, oset=1, wid=32, amp=2000):
    det_im = np.zeros(shape)
    # print ('amp '+str(amp))
    for x in range(shape[1]):
        det_im[: int(shape[0] / 2), x] = amp * np.mod(x, wid) ** 0.5 + oset
        det_im[int(shape[0] / 2) :, x] = amp * np.mod(shape[1] - x, wid) ** 0.5 + oset
    return det_im


def make_random_peaks(
    x, xmin=None, xmax=None, peak_chance=0.1, return_pristine_peaks=False
):

    # select boundaries for peaks
    if xmin is None:
        xmin = np.percentile(x, 10)
    if xmax is None:
        xmax = np.percentile(x, 90)

    y = np.zeros(len(x))

    # make peak positions
    peak_pos = np.array(np.random.random(len(x)) < peak_chance)
    peak_pos[x < xmin] = False
    peak_pos[x > xmax] = False

    for peak_idex in [i for i, x in enumerate(peak_pos) if x]:
        y += gaussian(x, c=x[peak_idex], sig=0.1, amp=(1 / x[peak_idex]) ** 0.5)

    # now for any diffuse low-Q component
    y += gaussian(x, c=0, sig=3, amp=0.1)

    return y


def gaussian(x, c=0, sig=1, amp=None):

    if amp is None:
        amp = 1 / (np.sqrt(2.0 * np.pi) * sig)

    return amp * np.exp(-(((x - c) / sig) ** 2.0) / 2)


def generate_flat_field(shape):
    num_bands = shape[0] // 20 + 1
    values = np.random.RandomState(0).random(num_bands) * 10
    # Tile values into bands.
    return np.broadcast_to(np.repeat(values, 20)[: shape[0]], shape).copy()


def generate_image(x, intensity, shape):
    """
    Given a 1D array of intensity, generate a 2D diffraction image.
    """
    xL, yL = shape[0] // 2, shape[1] // 2  # half-lengths of each dimension
    x_, y_ = np.mgrid[-xL:xL, -yL:yL]
    ordinal_r = np.hypot(x_, y_)
    unit_r = ordinal_r / ordinal_r.max()
    r = unit_r * x.max()
    return np.interp(r, x, intensity)


def make_simple_decay_func(I0, a=10, t1=2, t2=10, s=10):
    def decay_func(x):
        # rise = np.exp((x-t1)*s)/(1+np.exp((x-t1)*s)) * (x>=t1) * (x<=t2)
        rise = 1.0 * (x >= t1) * (x <= t2)
        fall = np.exp(-a * (x - t2) / I0) * (x > t2)
        return I0 * (rise + fall)

    return decay_func


def make_decay_func(I0, a=10, t1=2, t2=10):
    def decay_func(x):
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            pre = np.nan_to_num(I0 ** 2 / a * np.exp(-(a * x / I0)))

            f1 = np.heaviside(t1 - t2, 1) * np.heaviside(x - t2, 1)
            f1a = np.exp(a * t2 / I0) - np.exp(a * x / I0)
            f1b = (np.exp(x * a / I0) - np.exp(a * t1 / I0)) * np.heaviside(-t1 + x, 1)
            f1 *= f1a + f1b

            f2 = np.heaviside(t2 - t1, 1) * np.heaviside(x - t1, 1)
            f2a = np.exp(t1 * a / I0) - np.exp(x * a / I0)
            f2b = (np.exp(x * a / I0) - np.exp(t2 * a / I0)) * np.heaviside(x - t2, 1)
            f2 *= f2a + f2b

        return np.nan_to_num(pre * (f1 - f2))

    return decay_func


def make_illumination_combinations(
    sample_history, im_history, light_history, a, tmax=9999.0
):
    sample_history = sample_history.copy()
    im_history = im_history.copy()
    light_history = light_history.copy()
    decay_func_list = []
    tmax = time.monotonic()

    # check for empty lists
    if len(sample_history) > 0 and len(light_history) > 0:
        if len(sample_history[-1]) == 1:
            sample_history[-1] = (sample_history[-1][0], tmax)
            # print ('setting max time to sample_history '+str(sample_history[-1]))

        if len(light_history[-1]) == 1:
            light_history[-1] = (light_history[-1][0], tmax)

        for i in range(len(sample_history)):
            this_im = im_history[i]
            # make a series of tuples
            im_tstart = sample_history[i][0]
            im_tend = sample_history[i][1]

            my_list = []
            # see if a time exists in a light_loop
            for j in range(len(light_history)):
                light_tstart = light_history[j][0]  # light on
                light_tend = light_history[j][1]  # light off

                # first, check if image ends before light starts
                if light_tstart > im_tend or light_tend < im_tstart:
                    # print ('this light does not overlap sample')
                    pass
                else:  # have some overlap
                    # determine start
                    use_start = im_tstart
                    if im_tstart < light_tstart:
                        use_start = light_tstart
                    use_end = im_tend
                    if im_tend > light_tend:
                        use_end = light_tend
                    my_list.append((use_start, use_end))

            for k in range(len(my_list)):
                # print(
                #     "making a decay func for times "
                #     + str(my_list[k][0])
                #     + " "
                #     + str(my_list[k][1])
                # )
                # make a decay func for these
                decay_func_list.append(
                    # make_decay_func(this_im, a=a, t1=my_list[k][0], t2=my_list[k][1])
                    make_simple_decay_func(
                        this_im, a=a, t1=my_list[k][0], t2=my_list[k][1], s=10
                    )
                )
        # print ("total length of combination list is "+str(len(my_list)))

    else:
        # print ('something empty')
        pass

    def f(t):
        return sum(f(t) for f in decay_func_list)

    return f


def noisy_im(shape, noise=10):
    return np.random.random(shape) * noise


class PDF(PVGroup):

    # simple axis
    motor1 = SubGroup(FakeMotor, velocity=1, precision=3, prefix="fly")
    motor2 = SubGroup(FakeMotor, velocity=0.1, precision=3, prefix="step")

    det = SubGroup(SampleDetector, prefix="pe1c:")


if __name__ == "__main__":
    ioc_options, run_options = ioc_arg_parser(
        default_prefix="PDF:", desc=("An IOC that provides a simulated PDF.")
    )

    ioc = PDF(**ioc_options)
    run(ioc.pvdb, **run_options)
