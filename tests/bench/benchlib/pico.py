"""Control the Pico's Si5351 from the PC over one persistent raw-REPL session.

The beacon firmware is stopped for the duration (Ctrl-C ends main.py, whose
shutdown code stops the core-1 beacon thread). close() reboots the board so the
beacon and its web interface come back.
"""
import time

import serial

SETUP_CODE = """
import time
from machine import I2C, Pin
from si5351 import Si5351
import config
_cfg = config.load()
clk = Si5351(I2C(0, sda=Pin(4), scl=Pin(5), freq=400000), correction_ppb=_cfg['correction_ppb'])
def out(ch, pll, hz, drive):
    for c in (0, 1, 2):
        if c != ch:
            clk.enable(c, False)
    clk.set_drive(ch, drive)
    clk.set_frequency(ch, hz, pll=pll, enable=False)
    t0 = time.ticks_ms()
    while not clk.locked(pll):
        if time.ticks_diff(time.ticks_ms(), t0) > 300:
            raise OSError('PLL did not lock')
        time.sleep_ms(1)
    clk.enable(ch)
    return clk.frequency(ch)
def off():
    clk.disable_all()
"""

STOP_BEACON = """
try:
    beacon.stop = True
    for _ in range(40):
        if not beacon.running:
            break
        time.sleep_ms(50)
except NameError:
    pass
"""


class PicoError(RuntimeError):
    pass


class Pico:
    def __init__(self, port="/dev/ttyACM0"):
        self.port = port
        self._s = serial.Serial(port, 115200, timeout=0.1)
        self._s.write(b"\r\x03\x03")            # interrupt main.py
        time.sleep(3)                           # let its shutdown stop the beacon thread
        self._s.reset_input_buffer()
        self._s.write(b"\x01")                  # Ctrl-A: raw REPL
        self._until(b"raw REPL; CTRL-B to exit\r\n>", 5)
        self.run("import time")
        self.run(STOP_BEACON)
        self.run(SETUP_CODE)

    def _until(self, token, timeout):
        buf, end = b"", time.time() + timeout
        while time.time() < end:
            buf += self._s.read(4096)
            if token in buf:
                return buf
        raise PicoError("timed out waiting for %r (got %r)" % (token, buf[-200:]))

    def run(self, code, timeout=20):
        self._s.write(code.encode() + b"\x04")
        buf = self._until(b"\x04>", timeout)
        body = buf[buf.index(b"OK") + 2:]
        parts = body.split(b"\x04")
        if parts[1].strip():
            raise PicoError(parts[1].decode(errors="replace"))
        return parts[0].decode(errors="replace").strip()

    def set_output(self, ch, pll, carrier_hz, drive):
        """Tune one Si5351 output, switch every other output off; returns the actual Hz."""
        return int(self.run("print(out(%d, %d, %d, %d))" % (ch, pll, carrier_hz, drive)))

    def off(self):
        self.run("off()")

    def info(self):
        version = self.run("import sys; print('.'.join(str(x) for x in sys.implementation.version[:3]))").splitlines()[-1]
        ppb = int(self.run("print(_cfg['correction_ppb'])"))
        return {"micropython": version, "correction_ppb": ppb}

    def close(self, reboot=True):
        try:
            self.off()
        except Exception:
            pass
        if reboot:
            self._s.write(b"import machine\nmachine.reset()\x04")
            time.sleep(0.3)
        else:
            self._s.write(b"\x02")
        self._s.close()
