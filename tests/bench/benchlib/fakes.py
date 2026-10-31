"""Simulated Pico and analyser for testing the bench framework without hardware.

The model is deliberately simple but has the features the tests look for: a
trapezoidal passband on the wanted frequency, weak harmonics of the carrier, and
close-in spurs whose offset and level depend on the carrier frequency.
"""
import math
import sys
import time

from benchlib.results import REPO

BASE_DBM = {2: -34.7, 4: -32.2, 6: -32.7, 8: -29.2}     # wanted level through the chain, by drive
FLOOR_DBM = -100.0


class FakeWorld:
    def __init__(self, mult=3, passband_mhz=(421.0, 444.0), skirt_db_per_mhz=20.0, gain_db=0.0):
        self.mult = mult
        self.gain_db = gain_db       # extra level at the analyser, to simulate too little attenuation
        self.passband = passband_mhz
        self.skirt = skirt_db_per_mhz
        self.state = {"ch": None, "carrier": 0, "drive": 2, "on": False}
        self.analyser_lines = []     # (freq_hz, dbm at 0 dB attenuation) of spurs generated inside the analyser

    def response_db(self, f_mhz):
        lo, hi = self.passband
        if lo <= f_mhz <= hi:
            return 0.0
        d = lo - f_mhz if f_mhz < lo else f_mhz - hi
        return -min(50.0, d * self.skirt)

    def lines(self):
        s = self.state
        if not s["on"]:
            return []
        carrier = s["carrier"]
        wanted = carrier * self.mult
        base = BASE_DBM[s["drive"]] + self.gain_db
        out = [(wanted, base + self.response_db(wanted / 1e6))]
        for k, lev in ((1, -77.0), (4, -84.0)):
            if k != self.mult:
                out.append((k * carrier, lev))
        # close-in spurs: offsets and level depend on where the carrier is (bounded, and shaped by the filter)
        f_mhz = wanted / 1e6
        d = max(-5.0, min(5.0, f_mhz - 435.0))
        spread = 0.65 + 0.1 * d
        strength = -53.0 + 1.5 * max(0.0, min(3.0, f_mhz - 436.0))
        for sign in (-1, 1):
            for mult, extra in ((1, 0.0), (2, -4.0)):
                f = wanted + sign * mult * spread * 1e6
                out.append((f, base + strength + extra + self.response_db(f / 1e6)))
        return out


class FakePico:
    def __init__(self, world):
        self.world = world
        self.closed = False
        self.rebooted = None
        self.calls = []

    def set_output(self, ch, pll, carrier_hz, drive):
        self.calls.append((ch, pll, carrier_hz, drive))
        self.world.state.update(ch=ch, carrier=int(carrier_hz), drive=drive, on=True)
        return int(carrier_hz)

    def off(self):
        self.world.state["on"] = False

    def info(self):
        return {"micropython": "fake", "correction_ppb": 151300}

    def close(self, reboot=True):
        self.off()
        self.closed = True
        self.rebooted = reboot


class _RecordingI2C:
    def __init__(self):
        self.regs = [0] * 256

    def scan(self):
        return [0x60]

    def writeto_mem(self, addr, reg, data):
        for i, v in enumerate(data):
            self.regs[reg + i] = v

    def readfrom_mem(self, addr, reg, n):
        return bytes(self.regs[reg:reg + n])


class HostChipPico(FakePico):
    """A simulated Pico that runs the real firmware driver (si5351.py) on the PC, so every frequency a plan asks for is
    checked against the driver's real limits (for example, nothing can be made between 100 and 112.5 MHz)."""

    def __init__(self, world, correction_ppb=151300):
        super().__init__(world)
        if not hasattr(time, "ticks_ms"):          # MicroPython's clock functions, which the driver uses
            time.ticks_ms = lambda: int(time.time() * 1000)
            time.ticks_diff = lambda a, b: a - b
            time.sleep_ms = lambda ms: None
        sys.path.insert(0, str(REPO))
        import si5351
        self.clk = si5351.Si5351(_RecordingI2C(), correction_ppb=correction_ppb)

    def set_output(self, ch, pll, carrier_hz, drive):
        self.calls.append((ch, pll, carrier_hz, drive))
        for c in (0, 1, 2):
            if c != ch:
                self.clk.enable(c, False)
        self.clk.set_drive(ch, drive)
        actual = self.clk.set_frequency(ch, carrier_hz, pll=pll, enable=False)
        self.clk.enable(ch)
        self.world.state.update(ch=ch, carrier=actual, drive=drive, on=True)
        return actual


class FakeAnalyser:
    max_freq_hz = 790e6

    def __init__(self, world):
        self.world = world
        self.rbw_khz = 100.0
        self.attenuation = 0
        self.scans = 0

    def info(self):
        return {"model": "fakeSA", "firmware": "fake", "hardware": "fake", "attenuation_db": self.attenuation}

    def set_rbw_khz(self, khz):
        self.rbw_khz = float(khz)
        return self.rbw_khz

    def set_attenuation_db(self, db):
        self.attenuation = db

    def get_attenuation_db(self):
        return self.attenuation

    def set_lna(self, on):
        pass

    def snapshot(self):
        return {"sweep": [1, 2, 3], "rbw_khz": self.rbw_khz, "attenuation_db": self.attenuation}

    def restore(self, snap):
        self.rbw_khz = snap["rbw_khz"]

    def close(self):
        pass

    def scan(self, start, stop, points):
        self.scans += 1
        lines = self.world.lines()
        rbw = self.rbw_khz * 1000.0
        out = []
        for i in range(points):
            f = start + (stop - start) * i / (points - 1)
            p = 10 ** ((FLOOR_DBM + 0.3 * math.sin(f / 7.3e3)) / 10)
            for lf, ldb in lines:
                p += 10 ** ((ldb - min(150.0, 12.0 * ((f - lf) / rbw) ** 2)) / 10)
            for lf, ldb in self.world.analyser_lines:      # products the analyser makes itself fall as its attenuation is raised
                p += 10 ** ((ldb - self.attenuation - min(150.0, 12.0 * ((f - lf) / rbw) ** 2)) / 10)
            out.append((f, 10 * math.log10(p)))
        return out
