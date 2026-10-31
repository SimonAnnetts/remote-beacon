"""Host-side tests of the Pico firmware's logic (Morse, config, scheduler, web API, WSPR encoder, Si5351 maths).

The scripts in firmware/ run the firmware modules on the PC with a simulated chip and clock. This wrapper runs each of
them and, if `wsprd` (the WSJT-X WSPR decoder) is installed, also decodes our WSPR symbols with the real decoder.

    python3 -m unittest discover -s tests/unit -v
"""
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class FirmwareScripts(unittest.TestCase):
    def run_script(self, name):
        r = subprocess.run([sys.executable, str(HERE / "firmware" / name)], capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        self.assertIn("ALL OK", r.stdout)

    def test_si5351_register_maths(self):
        self.run_script("test_si5351.py")

    def test_morse_config_scheduler_web_and_modes(self):
        self.run_script("test_beacon.py")

    def test_wspr_encoder(self):
        self.run_script("test_wspr.py")


@unittest.skipUnless(shutil.which("wsprd"), "wsprd (WSJT-X) is not installed")
class WsprDecodeTest(unittest.TestCase):
    """Synthesise the audio our WSPR symbols describe and decode it with the real WSPR decoder."""

    def test_decoder_reads_our_message(self):
        sys.path.insert(0, str(ROOT))
        import wspr
        symbols = wspr.encode("GW3ACE", "IO82gh", 10)
        fs, pcm, phase = 12000, [0.0] * (120 * 12000), 0.0
        for i, s in enumerate(symbols):
            f = 1500.0 + (s - 1.5) * wspr.TONE_SPACING_NUM / wspr.TONE_SPACING_DEN
            a = fs + wspr.symbol_start_us(i) * fs // 1000000
            b = fs + wspr.symbol_start_us(i + 1) * fs // 1000000
            for k in range(a, b):
                phase += 2 * math.pi * f / fs
                pcm[k] = math.sin(phase)
        with tempfile.TemporaryDirectory() as d:
            with wave.open(str(Path(d) / "261028_2158.wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(fs)
                w.writeframes(b"".join(struct.pack("<h", int(0.3 * v * 32000)) for v in pcm))
            r = subprocess.run(["wsprd", "-f", "50.293", "261028_2158.wav"], cwd=d, capture_output=True, text=True, timeout=120)
            self.assertIn("GW3ACE IO82 10", r.stdout, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
