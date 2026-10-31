"""Persistent raw-REPL session with the Pico, so frequencies can be stepped quickly."""
import serial, time

class Pico:
    def __init__(self, port="/dev/ttyACM0"):
        self.s = serial.Serial(port, 115200, timeout=0.1)
        self.s.write(b"\r\x03\x03")
        time.sleep(0.3)
        self.s.reset_input_buffer()
        self.s.write(b"\x01")                       # Ctrl-A: raw REPL
        self._until(b"raw REPL; CTRL-B to exit\r\n>", 5)

    def _until(self, token, timeout):
        buf, end = b"", time.time() + timeout
        while time.time() < end:
            buf += self.s.read(4096)
            if buf.endswith(token) or token in buf:
                return buf
        raise TimeoutError("waiting for %r, got %r" % (token, buf[-200:]))

    def run(self, code, timeout=15):
        self.s.write(code.encode() + b"\x04")
        buf = self._until(b"\x04>", timeout)
        # reply: OK <stdout> \x04 <stderr> \x04 >
        body = buf[buf.index(b"OK") + 2:]
        out, err = body.split(b"\x04")[0], body.split(b"\x04")[1]
        if err.strip():
            raise RuntimeError(err.decode())
        return out.decode().strip()

    def close(self):
        self.s.write(b"\x02")                       # Ctrl-B: back to the friendly REPL
        self.s.close()

SETUP = """
import time
from machine import I2C, Pin
from si5351 import Si5351
clk = Si5351(I2C(0, sda=Pin(4), scl=Pin(5), freq=400000), correction_ppb=151300)
def out(hz, drive=2):
    # tune CLK2 (PLLB) so the 3rd harmonic is at 3*hz/3... caller passes the CARRIER frequency
    clk.set_drive(2, drive)
    clk.set_frequency(2, hz, pll=1, enable=False)
    t0 = time.ticks_ms()
    while not clk.locked(1):
        if time.ticks_diff(time.ticks_ms(), t0) > 300: raise OSError('no lock')
        time.sleep_ms(1)
    clk.enable(2)
    return clk.frequency(2)
def off():
    clk.disable_all()
"""
