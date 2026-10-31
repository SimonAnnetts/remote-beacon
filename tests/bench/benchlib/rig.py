"""A rig: one Si5351 output, the analyser and the chain between them."""
import sys
import time

from benchlib import setups, spectrum
from benchlib.results import REPO

sys.path.insert(0, str(REPO))
import config as fw_config  # noqa: E402  (the firmware's own band table, one source of truth)


class Rig:
    def __init__(self, setup, analyser, pico, sleep=time.sleep):
        self.setup = setup
        self.output = setup["output"]
        spec = fw_config.BANDS[self.output]
        self.ch, self.pll, self.mult = spec["ch"], spec["pll"], spec["mult"]
        self.band_lo_hz, self.band_hi_hz = spec["lo"], spec["hi"]
        self.analyser, self.pico, self.sleep = analyser, pico, sleep
        self.pad_db = setups.pad_db(setup)
        self._rbw = None
        self.max_level_dbm = -999.0

    @property
    def band_centre_mhz(self):
        return (self.band_lo_hz + self.band_hi_hz) / 2e6

    def use_rbw(self, khz):
        if self._rbw != khz:
            self.analyser.set_rbw_khz(khz)
            self._rbw = khz

    def set_wanted(self, fo_hz, drive):
        """Tune so the wanted output is at fo_hz. Returns (carrier_hz, wanted_hz) as actually set."""
        carrier = self.pico.set_output(self.ch, self.pll, int(round(fo_hz / self.mult)), drive)
        return carrier, carrier * self.mult

    def off(self):
        self.pico.off()

    def sweep_avg(self, start_hz, stop_hz, points, n=1):
        """Power-averaged n sweeps: (freqs_hz, dbm)."""
        traces = []
        for _ in range(n):
            pts = self.analyser.scan(int(start_hz), int(stop_hz), points)
            traces.append([p[1] for p in pts])
        db = traces[0] if n == 1 else spectrum.power_average(traces)
        self.max_level_dbm = max(self.max_level_dbm, max(db))
        return [p[0] for p in pts], db

    def window_peak(self, f_hz, half_hz=150e3, points=41, n=2):
        """Peak and median floor in a narrow window around f_hz."""
        _, db = self.sweep_avg(f_hz - half_hz, f_hz + half_hz, points, n)
        return max(db), spectrum.median(db)

    @property
    def max_freq_hz(self):
        return self.analyser.max_freq_hz
