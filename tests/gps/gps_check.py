#!/usr/bin/env python3
"""Check the GPS module wiring: NMEA over UART1 (GP8 TX, GP9 RX) and the 1PPS pulse on GP10.

Runs from the PC. The beacon firmware is stopped (as in the bench runs), a small reader runs on the Pico, and the NMEA is
parsed here. The board is rebooted at the end so the beacon comes back. Nothing is written to the Pico's files.

    python3 tests/gps/gps_check.py [--seconds 60] [--baud 9600] [--port /dev/ttyACM0] [--raw]

Prints one status line per second: fix, satellites, HDOP, UTC time, and the number of PPS pulses seen. If nothing valid
arrives in the first few seconds it tries other common baud rates, and says what to check.
"""
import argparse
import ast
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))
from benchlib.pico import Pico  # noqa: E402

PICO_CODE = """
from machine import UART, Pin
import array
u = UART(1, baudrate=%(baud)d, tx=Pin(8), rx=Pin(9), rxbuf=2048)
pps_n = 0
pps_t = array.array('I', [0] * 64)
def _pps(p):
    global pps_n
    pps_t[pps_n & 63] = time.ticks_us()
    pps_n += 1
pin = Pin(10, Pin.IN)
pin.irq(trigger=Pin.IRQ_RISING, handler=_pps)
def poll():
    d = u.read(u.any()) or b''
    print(repr(d))
    print(pps_n)
    print(list(pps_t))
"""


def checksum_ok(line):
    if not line.startswith("$") or "*" not in line:
        return False
    body, _, cs = line[1:].partition("*")
    calc = 0
    for ch in body:
        calc ^= ord(ch)
    try:
        return calc == int(cs[:2], 16)
    except ValueError:
        return False


def fields(line):
    return line[1:].split("*")[0].split(",")


class State:
    def __init__(self):
        self.fix = 0
        self.sats_used = None
        self.hdop = None
        self.utc = None
        self.alt = None
        self.status = "?"
        self.date = None
        self.lat = None
        self.lon = None
        self.in_view = {}
        self.counts = {}
        self.bad = 0
        self.valid = 0

    def feed(self, line):
        if not checksum_ok(line):
            self.bad += 1
            return
        self.valid += 1
        f = fields(line)
        kind = f[0][2:]
        self.counts[kind] = self.counts.get(kind, 0) + 1
        talker = f[0][:2]
        if kind == "GGA" and len(f) > 9:
            self.utc = f[1]
            self.fix = int(f[6] or 0)
            self.sats_used = f[7]
            self.hdop = f[8]
            self.alt = f[9]
            self.lat, self.lon = (f[2] + f[3]).strip(), (f[4] + f[5]).strip()
        elif kind == "RMC" and len(f) > 9:
            self.status = f[2]
            self.date = f[9]
        elif kind == "GSV" and len(f) > 3 and f[3]:
            self.in_view[talker] = int(f[3])


def pps_stats(times):
    """Intervals in us from the Pico's ticks_us (wraps at 2**30), for the pulses seen in order."""
    iv = [(b - a) % (1 << 30) for a, b in zip(times, times[1:])]
    return iv


def run(args):
    pico = Pico(args.port)
    try:
        bauds = [args.baud] + [b for b in (9600, 115200, 38400, 57600, 4800) if b != args.baud]
        for baud in bauds:
            pico.run(PICO_CODE % {"baud": baud})
            st, lines, buf = State(), 0, ""
            t_start = time.time()
            t_end = t_start + 6          # probe; extended once valid sentences arrive
            last_print = 0
            seen_pps, pps_times = 0, []
            print("--- UART1 at %d baud ---" % baud)
            while time.time() < t_end:
                time.sleep(1)
                out = pico.run("poll()").splitlines()
                data = ast.literal_eval(out[0]).decode("ascii", "replace")
                total = int(out[1])
                ring = ast.literal_eval(out[2])
                new = total - seen_pps
                if new > 0:
                    n = min(new, 64)
                    for k in range(total - n, total):
                        pps_times.append(ring[k & 63])
                    seen_pps = total
                buf += data
                *done, buf = buf.split("\n")
                for ln in done:
                    ln = ln.strip()
                    if args.raw and ln:
                        print("   ", ln)
                    if ln.startswith("$"):
                        st.feed(ln)
                        lines += 1
                if st.valid:
                    t_end = t_start + args.seconds
                if time.time() - last_print >= 1:
                    last_print = time.time()
                    view = ",".join("%s:%d" % kv for kv in sorted(st.in_view.items())) or "-"
                    print("fix=%d (%s) used=%s view=[%s] hdop=%s utc=%s date=%s pps=%d  sentences=%d bad=%d" % (
                        st.fix, st.status, st.sats_used or "-", view, st.hdop or "-", st.utc or "-",
                        st.date or "-", total, st.valid, st.bad))
            if st.valid or baud == bauds[-1]:
                break
            print("nothing valid at %d baud (bytes seen: %s)" % (baud, "some, corrupted" if lines else "none"))
        print()
        print("sentences by type:", ", ".join("%s %d" % kv for kv in sorted(st.counts.items())) or "none")
        print("checksum errors:", st.bad)
        if st.valid == 0:
            print("NO valid NMEA. Check: module TXD -> GP9 (pin 12), module RXD -> GP8 (pin 11), 3V3 and GND connected, "
                  "and that the board is powered (most modules have a flashing LED once they have a fix).")
        iv = pps_stats(pps_times)
        if iv:
            print("PPS: %d pulses, interval mean %.1f us, min %d, max %d (from the Pico's own clock)" % (
                len(pps_times), sum(iv) / len(iv), min(iv), max(iv)))
        else:
            print("PPS: %d pulses seen%s" % (seen_pps, " (none: normal until there is a fix; check the PPS wire to GP10, pin 14, if there is a fix)" if not seen_pps else ""))
        if st.fix:
            print("position: %s %s, altitude %s m" % (st.lat, st.lon, st.alt))
    finally:
        try:
            pico.close(reboot=True)
        except Exception:
            pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--raw", action="store_true", help="also print every NMEA sentence")
    run(ap.parse_args())
