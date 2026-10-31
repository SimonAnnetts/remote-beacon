"""Minimal TinySA USB shell helper: send a command, return its reply text."""
import serial, time

PORT = "/dev/ttyACM1"

def open_port(port=PORT):
    s = serial.Serial(port, 115200, timeout=0.3)
    s.reset_input_buffer()
    s.write(b"\r")
    read_until_prompt(s)
    return s

def read_until_prompt(s, timeout=10.0):
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
            if buf.endswith(b"ch> "):
                return buf
    return buf

def command(s, text, timeout=10.0):
    s.reset_input_buffer()
    s.write(text.encode() + b"\r")
    raw = read_until_prompt(s, timeout)
    out = raw.decode(errors="replace").replace("\r\n", "\n")
    lines = out.split("\n")
    if lines and lines[0].strip() == text.strip():
        lines = lines[1:]
    return "\n".join(lines).replace("ch> ", "").strip()


def scan(s, start, stop, points, timeout=60.0):
    """One sweep with the current settings. Returns [(freq_hz, dbm), ...]."""
    text = command(s, "scan %d %d %d 3" % (start, stop, points), timeout)
    out = []
    for line in text.split("\n"):
        parts = line.split()
        if len(parts) >= 2:
            try:
                out.append((float(parts[0]), float(parts[1])))
            except ValueError:
                pass
    return out
