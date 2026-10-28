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

import clock
import config
import morse
import wspr


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
        self._state = {"band": None, "waiting": None, "error": None, "cycles": 0,
                       "last_tx_ms": None}

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
            if (self._state["band"] is not None or self._state["waiting"] is not None
                    or self._manual is not None):
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
        cfg = self.cfg
        mode = cfg["bands"][name]["mode"]
        # WSPR waits for its time slot before it is "on air".
        self._set_state(**({"waiting": name} if mode == "wspr" else {"band": name}))
        spec = config.BANDS[name]
        band = cfg["bands"][name]
        ch = spec["ch"]
        clk = self.clk
        try:
            clk.disable_all()
            # Every transmission starts from a known drive level: the band's
            # setting, or for the AM modes their low level.
            clk.set_drive(ch, band["am_low_ma"] if mode in ("am", "mcw")
                          else band["drive_ma"])
            freq = band["freq"] + (config.WSPR_OFFSET_HZ if mode == "wspr" else 0)
            clk.set_frequency(ch, freq // spec["mult"], pll=spec["pll"], enable=False)
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
            elif mode == "fm":
                self._send_fm(spec, band)
            elif mode == "fmcw":
                self._send_fmcw(spec, band, config.message(cfg), cfg["wpm"])
            elif mode == "wspr":
                self._send_wspr(name, spec, band, cfg)
            else:
                self._send_fsk(spec, band, config.message(cfg), cfg["wpm"])
        finally:
            clk.disable_all()
            self._set_state(band=None, waiting=None, last_tx_ms=time.ticks_ms())

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

    def _wait_wspr_start(self):
        """Wait for second 1 of the next even UTC minute. False if stopped."""
        deadline = time.ticks_add(time.ticks_ms(), 125000)
        while self._active():
            if int(time.time()) % 120 == 1:
                return True
            if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                raise OSError("WSPR slot not reached")
            time.sleep_ms(5)
        return False

    def _send_wspr(self, name, spec, band, cfg):
        """Send one WSPR message: 162 symbols of 4-FSK, 0.683 s each, starting
        1 s into an even UTC minute. The output is tuned in millihertz because
        the tones are only 1.46 Hz apart."""
        if not clock.state["synced"]:
            raise OSError("WSPR needs the time to be synced (NTP)")
        ch = spec["ch"]
        symbols = wspr.encode(cfg["callsign"], cfg["locator"], band["wspr_dbm"])
        centre_mhz = (band["freq"] + config.WSPR_OFFSET_HZ) * 1000
        tones = [self.clk.tuning_mhz(ch, centre_mhz + (2 * k - 3) * 375000 // 512)
                 for k in range(4)]
        self.clk.retune(ch, tones[symbols[0]])  # first tone, output still off
        if not self._wait_wspr_start():
            return
        start = time.ticks_us()
        self._set_state(waiting=None, band=name)
        self.clk.enable(ch)
        for i in range(1, wspr.SYMBOLS):
            _wait_until(time.ticks_add(start, wspr.symbol_start_us(i)))
            if not self._active():
                return
            self.clk.retune(ch, tones[symbols[i]])
        _wait_until(time.ticks_add(start, wspr.symbol_start_us(wspr.SYMBOLS)))

    def _fm_tunings(self, spec, band):
        """Precomputed (centre, high, low) tunings for the FM modes."""
        ch, mult = spec["ch"], spec["mult"]
        freq, dev = band["freq"], band["fm_dev_hz"]
        return (self.clk.tuning(ch, freq // mult),
                self.clk.tuning(ch, (freq + dev) // mult),
                self.clk.tuning(ch, (freq - dev) // mult))

    def _fm_until(self, ch, tunings, band, end):
        """Alternate between the high and low frequency (a square-wave tone)
        until the ticks_us() deadline end, then return to the centre."""
        centre, high, low = tunings
        half = 1000000 // band["fm_hz"] // 2
        t = time.ticks_us()
        while self._active() and time.ticks_diff(end, t) > 0:
            self.clk.retune(ch, high)
            t = time.ticks_add(t, half)
            _wait_until(t if time.ticks_diff(end, t) > 0 else end)
            self.clk.retune(ch, low)
            t = time.ticks_add(t, half)
            _wait_until(t if time.ticks_diff(end, t) > 0 else end)
        self.clk.retune(ch, centre)

    def _send_fm(self, spec, band):
        ch = spec["ch"]
        tunings = self._fm_tunings(spec, band)
        self.clk.enable(ch)
        self._fm_until(ch, tunings, band, time.ticks_add(
            time.ticks_us(), band["carrier_s"] * 1000000))

    def _send_fmcw(self, spec, band, text, wpm):
        """Morse with an FM tone on key-down; the carrier stays on at the
        centre frequency during key-up."""
        ch = spec["ch"]
        tunings = self._fm_tunings(spec, band)
        dit = morse.dit_us(wpm)
        deadline = time.ticks_us()
        self.clk.enable(ch)
        for element in morse.timing(text):
            if not self._active():
                break
            deadline = time.ticks_add(deadline, abs(element) * dit)
            if element > 0:
                self._fm_until(ch, tunings, band, deadline)
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

    def _service_wspr(self):
        """Start a WSPR transmission when a scheduled slot is about to begin.
        transmit() prepares the tones, then waits for the exact second."""
        if not self.tx_enabled or not clock.state["synced"]:
            return
        now = int(time.time())
        for name in config.BAND_ORDER:
            band = self.cfg["bands"][name]
            if band["enabled"] and band["mode"] == "wspr":
                period = 120 * band["wspr_every"]
                into = now % period
                if into == 0 or into >= period - 3:
                    self._try_transmit(name)
                    return

    def _pause(self, seconds):
        for _ in range(int(seconds * 10)):
            self._apply_pending()
            self._service_manual()
            self._service_wspr()
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
            self._service_wspr()
            band = self.cfg["bands"][name]
            if band["enabled"] and band["mode"] != "wspr":  # WSPR runs by the clock
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
