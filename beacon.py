"""Beacon scheduler: transmits each enabled band in turn, one at a time.

Only one output is ever enabled at once because the Si5351 outputs leak into
each other (see PLAN.md, "Crosstalk between outputs"). Keying switches the
output enable bit, so the carrier is gated cleanly without retuning.
"""
import time

import config
import morse


def _wait_until(deadline):
    """Sleep until a ticks_us() deadline, busy-waiting the last stretch."""
    while True:
        remaining = time.ticks_diff(deadline, time.ticks_us())
        if remaining <= 0:
            return
        if remaining > 200:
            time.sleep_us(remaining - 100)


class Beacon:
    def __init__(self, clk, cfg):
        config.validate(cfg)
        self.clk = clk
        self.cfg = cfg
        self.stop = False

    def transmit(self, name):
        """Send one transmission on a band, then switch every output off."""
        spec = config.BANDS[name]
        band = self.cfg["bands"][name]
        ch = spec["ch"]
        clk = self.clk
        clk.disable_all()
        try:
            clk.set_frequency(ch, band["freq"] // spec["mult"],
                              pll=spec["pll"], enable=False)
            self._wait_lock(spec["pll"])
            if band["mode"] == "morse":
                self._send_morse(ch, config.message(self.cfg))
            else:
                self._send_carrier(ch, band["carrier_s"])
        finally:
            clk.disable_all()

    def _wait_lock(self, pll, timeout_ms=100):
        start = time.ticks_ms()
        while not self.clk.locked(pll):
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                raise OSError("PLL did not lock")
            time.sleep_ms(1)

    def _send_morse(self, ch, text):
        dit = morse.dit_us(self.cfg["wpm"])
        deadline = time.ticks_us()
        for element in morse.timing(text):
            if self.stop:
                break
            self.clk.enable(ch, element > 0)
            deadline = time.ticks_add(deadline, abs(element) * dit)
            _wait_until(deadline)

    def _send_carrier(self, ch, seconds):
        self.clk.enable(ch)
        deadline = time.ticks_add(time.ticks_us(), seconds * 1000000)
        while not self.stop and time.ticks_diff(deadline, time.ticks_us()) > 0:
            time.sleep_ms(10)

    def _pause(self, seconds):
        for _ in range(int(seconds * 10)):
            if self.stop:
                return
            time.sleep_ms(100)

    def run(self, max_cycles=None):
        """Loop over the enabled bands until stop is set (or max_cycles)."""
        cycles = 0
        while not self.stop and (max_cycles is None or cycles < max_cycles):
            sent = False
            for name in config.BAND_ORDER:
                if self.stop:
                    break
                if self.cfg["bands"][name]["enabled"]:
                    self.transmit(name)
                    sent = True
                    self._pause(self.cfg["gap_s"])
            cycles += 1
            self._pause(self.cfg["interval_s"] if sent else 1)
