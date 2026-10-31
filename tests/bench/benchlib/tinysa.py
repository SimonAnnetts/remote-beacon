"""TinySA Ultra driver over its USB serial shell."""
import re
import time

import serial

PROMPT = b"ch> "
MAX_FREQ_HZ = 790e6        # the low input stops at 800 MHz


class TinySAError(RuntimeError):
    pass


def _parse_khz(text):
    m = re.search(r"([\d.]+)\s*(k?)Hz", text)
    if not m:
        return None
    value = float(m.group(1))
    return value if m.group(2) == "k" else value / 1000.0


def to_float(token):
    """Parse a number from the instrument.

    The firmware's formatter prints a value that rounds up to 10 with the character after "9", so -99.99999 comes out
    as "-:.000000e+01" (which is -100.0). Treat ":" as the two digits "10".
    """
    return float(token.replace(":", "10", 1)) if ":" in token else float(token)


class TinySA:
    max_freq_hz = MAX_FREQ_HZ

    def __init__(self, port="/dev/ttyACM1"):
        self.port = port
        self._s = serial.Serial(port, 115200, timeout=0.3)
        self._s.reset_input_buffer()
        self._s.write(b"\r")
        self._read_until_prompt(5)
        self._rbw_khz = None

    def _read_until_prompt(self, timeout):
        buf, end = b"", time.time() + timeout
        while time.time() < end:
            chunk = self._s.read(4096)
            if chunk:
                buf += chunk
                if buf.endswith(PROMPT):
                    return buf
        return buf

    def command(self, text, timeout=10.0):
        self._s.reset_input_buffer()
        self._s.write(text.encode() + b"\r")
        raw = self._read_until_prompt(timeout).decode(errors="replace").replace("\r\n", "\n")
        lines = raw.split("\n")
        if lines and lines[0].strip() == text.strip():
            lines = lines[1:]
        return "\n".join(lines).replace("ch> ", "").strip()

    # -- identity and settings -------------------------------------------------

    def info(self):
        version = self.command("version").splitlines()
        first = version[0] if version else ""
        return {"model": first.split("_v")[0], "firmware": first,
                "hardware": version[1].split(":", 1)[-1].strip() if len(version) > 1 else "",
                "attenuation_db": self.get_attenuation_db()}

    def get_attenuation_db(self):
        last = self.command("attenuate").splitlines()[-1].strip()
        try:
            return int(last)
        except ValueError:
            return None

    def set_attenuation_db(self, db):
        self.command("attenuate %d" % db)

    def set_lna(self, on):
        self.command("lna %s" % ("on" if on else "off"))

    def get_rbw_khz(self):
        return _parse_khz(self.command("rbw").splitlines()[-1])

    def set_rbw_khz(self, khz):
        """Select an RBW and return the value the instrument actually uses."""
        self.command("rbw %g" % khz)
        self._rbw_khz = self.get_rbw_khz()
        return self._rbw_khz

    # -- measuring ---------------------------------------------------------------

    def scan(self, start_hz, stop_hz, points, tries=3, warn=print):
        """One sweep with the current settings: [(freq_hz, dbm), ...].

        The serial link occasionally returns a short reply, so a wrong point count is retried.
        """
        for attempt in range(1, tries + 1):
            text = self.command("scan %d %d %d 3" % (start_hz, stop_hz, points), timeout=120.0)
            out = []
            for line in text.split("\n"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        out.append((to_float(parts[0]), to_float(parts[1])))
                    except ValueError:
                        pass
            if len(out) == points:
                return out
            warn("TinySA returned %d of %d points (attempt %d of %d)" % (len(out), points, attempt, tries))
            time.sleep(0.5)
        raise TinySAError("expected %d points, got %d after %d tries" % (points, len(out), tries))

    # -- keep the user's settings ------------------------------------------------

    def snapshot(self):
        sweep = self.command("sweep").split()
        return {"sweep": [int(x) for x in sweep[:3]] if len(sweep) >= 3 else None,
                "rbw_khz": self.get_rbw_khz(), "attenuation_db": self.get_attenuation_db()}

    def restore(self, snap):
        if snap.get("sweep"):
            self.command("sweep %d %d %d" % tuple(snap["sweep"]))
        if snap.get("rbw_khz"):
            self.command("rbw %g" % snap["rbw_khz"])
        if snap.get("attenuation_db") is not None:
            self.command("attenuate %d" % snap["attenuation_db"])

    def close(self):
        self._s.close()
