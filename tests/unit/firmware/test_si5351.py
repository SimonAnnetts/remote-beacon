"""Host-side check of si5351.py: decode written registers independently."""
import sys, types, time
from fractions import Fraction

import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
time.ticks_ms = lambda: int(time.time() * 1000)
time.ticks_diff = lambda a, b: a - b
time.sleep_ms = lambda ms: None
import si5351


class FakeI2C:
    def __init__(self):
        self.regs = [0] * 256

    def scan(self):
        return [0x60]

    def writeto_mem(self, addr, reg, data):
        for i, v in enumerate(data):
            self.regs[reg + i] = v

    def readfrom_mem(self, addr, reg, n):
        return bytes(self.regs[reg:reg + n])


def decode(regs, base, ms=False):
    r = regs[base:base + 8]
    p3 = ((r[5] & 0xF0) << 12) | (r[0] << 8) | r[1]
    p1 = ((r[2] & 3) << 16) | (r[3] << 8) | r[4]
    p2 = ((r[5] & 0x0F) << 16) | (r[6] << 8) | r[7]
    if ms and (r[2] & 0x0C) == 0x0C:
        return Fraction(4)
    return Fraction(512 + p1, 128) + Fraction(p2, 128 * p3) if False else (
        Fraction(p1 + 512, 128) + Fraction(p2, 128 * p3))


def out_freq(i2c, ch, xtal=25_000_000, ppb=0):
    regs = i2c.regs
    ctrl = regs[16 + ch]
    assert not ctrl & 0x80, "powered down"
    pll = 1 if ctrl & 0x20 else 0
    mult = decode(regs, (26, 34)[pll])
    div = decode(regs, (42, 50, 58)[ch], ms=True)
    return xtal * (1 + Fraction(ppb, 10**9)) * mult / div


def check(label, got, want, tol=3):
    err = float(got - want)
    print("%-28s want %12d got %16.3f err %8.3f Hz" % (label, want, float(got), err))
    assert abs(err) <= tol, label


i2c = FakeI2C()
s = si5351.Si5351(i2c)
assert i2c.regs[3] == 0xFF and i2c.regs[16] == 0x80

# 6m alone on default PLL
a = s.set_frequency(0, 50_200_000, pll=s.PLLA)
check("CLK0 50.2 MHz", out_freq(i2c, 0), 50_200_000)
assert a == 50_200_000 or abs(a - 50_200_000) <= 1

# 2m owner on PLLA, 6m must follow
s.set_frequency(1, 144_500_000, pll=s.PLLA)
check("CLK1 144.5 MHz", out_freq(i2c, 1), 144_500_000)
check("CLK0 follows PLLA", out_freq(i2c, 0), 50_200_000)

# 70cm: carrier 145 MHz -> 435 MHz third harmonic, own PLLB
s.set_frequency(2, 145_000_000, pll=s.PLLB)
check("CLK2 145 MHz (x3=435)", out_freq(i2c, 2), 145_000_000)

# sweep the whole 2m and 70cm carrier ranges, PLL owners only
for f in range(143_333_333, 146_666_667, 100_001):
    s.set_frequency(1, f, pll=s.PLLA, reset=False)
    check("2m sweep", out_freq(i2c, 1), f)
    check("6m follows", out_freq(i2c, 0), 50_200_000)
for f in range(50_000_000, 52_000_001, 123_457):
    s.set_frequency(0, f)
    check("6m sweep", out_freq(i2c, 0), f)

# 200 MHz (divide by 4), PLL ownership conflicts, limits, ppm
s2 = si5351.Si5351(FakeI2C())
s2.set_frequency(1, 160_000_000, pll=0)
check("div4 160 MHz", out_freq(s2.i2c, 1), 160_000_000)
try:
    s2.set_frequency(2, 140_000_000, pll=0)
    raise SystemExit("expected conflict")
except ValueError as e:
    print("conflict OK:", e)
try:
    s2.set_frequency(0, 201_000_000)
    raise SystemExit("expected limit error")
except ValueError as e:
    print("limit OK:", e)

s3 = si5351.Si5351(FakeI2C(), correction_ppb=-12_345)
s3.set_frequency(1, 144_500_000)
check("ppb corrected", out_freq(s3.i2c, 1, ppb=-12_345), 144_500_000)

# control register bits
assert i2c.regs[17] & 0x0C == 0x0C and not i2c.regs[17] & 0x20  # CLK1 on PLLA
assert i2c.regs[18] & 0x20  # CLK2 on PLLB
assert (i2c.regs[3] & 7) == 0  # all enabled
# fast retune: precomputed single write lands on the right frequency
i3 = FakeI2C(); s4 = si5351.Si5351(i3)
s4.set_frequency(1, 144_450_000, pll=0)
s4.set_frequency(0, 50_050_000, pll=0)          # dependent on PLLA
for f in (144_450_000 + 3000, 144_450_000 - 3000, 144_450_000):
    t = s4.tuning(1, f); s4.retune(1, t)
    check("fast retune 2m", out_freq(i3, 1), f)
    assert abs(s4.frequency(1) - f) <= 3
s4.set_frequency(2, 145_000_000, pll=1)
for f in (145_000_000 + 1000, 145_000_000 - 1000):
    s4.retune(2, s4.tuning(2, f)); check("fast retune 70cm carrier", out_freq(i3, 2), f)
# bookkeeping stays coherent: after FM on 2m, 6m (sharing PLLA) is retuned correctly
s4.retune(1, s4.tuning(1, 144_450_000 + 3000))
s4.set_frequency(0, 50_050_000, pll=0)
check("6m after 2m was deviated", out_freq(i3, 0), 50_050_000)
# dependent fast retune
t = s4.tuning(0, 50_052_000); s4.retune(0, t); check("fast retune 6m", out_freq(i3, 0), 50_052_000)
for bad in ((1, 150_000_001), (1, 100_000_000), (0, 52_000_000 * 3)):
    try: s4.tuning(*bad); raise SystemExit("expected full retune error")
    except ValueError as e: print("OK:", e)
try: si5351.Si5351(FakeI2C()).tuning(1, 144_000_000); raise SystemExit("needs set_frequency")
except ValueError as e: print("OK:", e)
print("ALL OK")
