"""Beacon scheduler: transmits each enabled band in turn, one at a time.

Only one output is ever enabled at once because the Si5351 outputs leak into
each other (see PLAN.md, "Crosstalk between outputs"). Keying switches the
output enable bit, so the carrier is gated cleanly without retuning.

Threading: run() is meant to be the only code that touches the Si5351 and the
flash, on core 1. Core 0 (the web server) talks to it only through
request_config(), emergency_stop() and status(). A new config is applied, and
saved to flash, between transmissions: a flash write stalls the other core and
would glitch the keying.
"""
import _thread
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
        self.running = False
        # Checked between Morse elements so it can cut a transmission short.
        self.tx_enabled = cfg["tx_enabled"]
        self._lock = _thread.allocate_lock()
        self._pending = None
        self._manual = None  # band queued by request_tx()
        self._state = {"band": None, "error": None, "cycles": 0, "last_tx_ms": None}

    # -- called from other cores ---------------------------------------------

    def request_config(self, cfg):
        """Queue a validated config; core 1 applies and saves it when idle."""
        config.validate(cfg)
        with self._lock:
            self._pending = cfg
        if not cfg["tx_enabled"]:
            self.tx_enabled = False  # switching off must not wait

    def current_config(self):
        """The newest config: the queued one if a change is waiting to be
        applied, else the active one. New changes must be built on this so a
        change made during a transmission is not lost."""
        with self._lock:
            return self._pending or self.cfg

    def request_tx(self, name):
        """Queue one immediate transmission on a band, whether or not that
        band is in the schedule. Refused unless transmitting is enabled and
        nothing is on air or already queued."""
        if name not in config.BANDS:
            raise ValueError("unknown band " + str(name))
        if not self.tx_enabled:
            raise ValueError("transmit is not enabled")
        with self._lock:
            if self._state["band"] is not None or self._manual is not None:
                raise ValueError("another transmission is already in progress")
            self._manual = name

    def emergency_stop(self):
        """Stop transmitting now and keep it off across a reboot."""
        self.tx_enabled = False
        with self._lock:
            new = config.copy(self._pending or self.cfg)
            new["tx_enabled"] = False
            self._pending = new
            self._manual = None

    def status(self):
        with self._lock:
            state = dict(self._state)
            state["queued"] = self._manual
        last = state.pop("last_tx_ms")
        state["last_tx_age_s"] = (None if last is None else
                                  time.ticks_diff(time.ticks_ms(), last) // 1000)
        state["tx_enabled"] = self.tx_enabled
        state["uptime_s"] = time.ticks_ms() // 1000
        return state

    # -- core 1 --------------------------------------------------------------

    def _set_state(self, **kw):
        with self._lock:
            self._state.update(kw)

    def _apply_pending(self):
        with self._lock:
            new, self._pending = self._pending, None
        if new is None:
            return
        self.cfg = new
        self.tx_enabled = new["tx_enabled"]
        try:
            config.save(new)
        except OSError as e:
            self._set_state(error="could not save config: %s" % e)

    def transmit(self, name):
        """Send one transmission on a band, then switch every output off."""
        if not self.tx_enabled:
            return
        self._set_state(band=name)
        cfg = self.cfg
        spec = config.BANDS[name]
        band = cfg["bands"][name]
        ch = spec["ch"]
        mode = band["mode"]
        clk = self.clk
        try:
            clk.disable_all()
            # Every transmission starts from a known drive level; the AM modes
            # start at their low level.
            clk.set_drive(ch, band["am_low_ma"] if mode in ("am", "mcw")
                          else config.DRIVE_MA)
            clk.set_frequency(ch, band["freq"] // spec["mult"],
                              pll=spec["pll"], enable=False)
            self._wait_lock(spec["pll"])
            if mode == "morse":
                self._send_morse(ch, config.message(cfg), cfg["wpm"])
            elif mode == "carrier":
                self._send_carrier(ch, band["carrier_s"])
            elif mode == "duty":
                self._send_duty(ch, band)
            elif mode == "am":
                self.clk.enable(ch)
                self._am_until(ch, band, time.ticks_add(
                    time.ticks_us(), band["carrier_s"] * 1000000))
            elif mode == "mcw":
                self._send_mcw(ch, band, config.message(cfg), cfg["wpm"])
            else:
                self._send_fsk(spec, band, config.message(cfg), cfg["wpm"])
        finally:
            clk.disable_all()
            self._set_state(band=None, last_tx_ms=time.ticks_ms())

    def _wait_lock(self, pll, timeout_ms=100):
        start = time.ticks_ms()
        while not self.clk.locked(pll):
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                raise OSError("PLL did not lock")
            time.sleep_ms(1)

    def _active(self):
        return self.tx_enabled and not self.stop

    def _send_morse(self, ch, text, wpm):
        dit = morse.dit_us(wpm)
        deadline = time.ticks_us()
        for element in morse.timing(text):
            if not self._active():
                break
            self.clk.enable(ch, element > 0)
            deadline = time.ticks_add(deadline, abs(element) * dit)
            _wait_until(deadline)

    def _send_carrier(self, ch, seconds):
        self.clk.enable(ch)
        deadline = time.ticks_add(time.ticks_us(), seconds * 1000000)
        while self._active() and time.ticks_diff(deadline, time.ticks_us()) > 0:
            time.sleep_ms(10)

    def _try_transmit(self, name):
        """transmit(), but report a failure instead of raising."""
        try:
            self.transmit(name)
            self._set_state(error=None)
            return True
        except Exception as e:  # keep the beacon alive, report it
            self._set_state(error="%s: %s" % (name, e))
            return False

    def _service_manual(self):
        with self._lock:
            name, self._manual = self._manual, None
        if name is not None and self.tx_enabled:
            self._try_transmit(name)

    def _send_duty(self, ch, band):
        """Key the carrier on and off at a fixed period and duty cycle."""
        period = band["period_ms"] * 1000
        on_us = period * band["duty_pct"] // 100
        t = time.ticks_us()
        end = time.ticks_add(t, band["carrier_s"] * 1000000)
        while self._active() and time.ticks_diff(end, t) > 0:
            self.clk.enable(ch)
            t = time.ticks_add(t, on_us)
            _wait_until(t)
            self.clk.enable(ch, False)
            t = time.ticks_add(t, period - on_us)
            _wait_until(t)

    def _am_until(self, ch, band, end):
        """Alternate the drive between its two levels until the ticks_us()
        deadline end, starting at the high level."""
        period = 1000000 // band["am_hz"]
        high_us = period * band["am_duty_pct"] // 100
        t = time.ticks_us()
        while self._active() and time.ticks_diff(end, t) > 0:
            self.clk.set_drive(ch, band["am_high_ma"])
            t = time.ticks_add(t, high_us)
            _wait_until(t if time.ticks_diff(end, t) > 0 else end)
            self.clk.set_drive(ch, band["am_low_ma"])
            t = time.ticks_add(t, period - high_us)
            _wait_until(t if time.ticks_diff(end, t) > 0 else end)

    def _send_mcw(self, ch, band, text, wpm):
        """Morse where key-down is the amplitude-modulated tone and key-up is
        no carrier."""
        dit = morse.dit_us(wpm)
        deadline = time.ticks_us()
        for element in morse.timing(text):
            if not self._active():
                break
            deadline = time.ticks_add(deadline, abs(element) * dit)
            if element > 0:
                self.clk.enable(ch)
                self._am_until(ch, band, deadline)
                self.clk.enable(ch, False)
            else:
                _wait_until(deadline)

    def _send_fsk(self, spec, band, text, wpm):
        """Send Morse as frequency shift keying: the carrier stays on, at the
        band frequency for key-down and shift_hz higher for key-up."""
        ch, pll, mult = spec["ch"], spec["pll"], spec["mult"]
        mark = band["freq"] // mult
        space = (band["freq"] + band["shift_hz"]) // mult
        dit = morse.dit_us(wpm)
        deadline = time.ticks_us()
        current = mark  # transmit() has already tuned to the mark frequency
        self.clk.enable(ch)
        for element in morse.timing(text):
            if not self._active():
                break
            tone = mark if element > 0 else space
            if tone != current:
                self.clk.set_frequency(ch, tone, pll=pll, reset=False, enable=False)
                current = tone
            deadline = time.ticks_add(deadline, abs(element) * dit)
            _wait_until(deadline)

    def _pause(self, seconds):
        for _ in range(int(seconds * 10)):
            self._apply_pending()
            self._service_manual()
            if not self._active():
                return
            time.sleep_ms(100)

    def _cycle(self):
        sent = False
        for name in config.BAND_ORDER:
            self._apply_pending()
            if not self._active():
                break
            self._service_manual()
            if self.cfg["bands"][name]["enabled"]:
                if not self._try_transmit(name):
                    self._pause(5)
                    continue
                sent = True
                self._pause(self.cfg["gap_s"])
        return sent

    def run(self, max_cycles=None):
        """Loop until stop is set (or max_cycles cycles have been sent).
        Idles, polling for a new config, while transmitting is disabled."""
        self.running = True
        cycles = 0
        try:
            while not self.stop and (max_cycles is None or cycles < max_cycles):
                self._apply_pending()
                if not self.tx_enabled:
                    time.sleep_ms(100)
                    continue
                self._service_manual()
                sent = self._cycle()
                cycles += 1
                self._set_state(cycles=cycles)
                self._pause(self.cfg["interval_s"] if sent else 1)
        finally:
            self.clk.disable_all()
            self.running = False
