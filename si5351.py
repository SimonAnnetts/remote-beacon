"""Si5351 clock generator driver for MicroPython.

All frequency maths uses integers: MicroPython floats on the RP2040 are single
precision, which cannot represent VHF frequencies to the Hz.

PLL / MultiSynth allocation
---------------------------
The chip has two PLLs (VCO 600-900 MHz) and three MultiSynths (CLK0-2), each of
which can use either PLL. A MultiSynth can only divide by a fraction a+b/c when
a >= 8, so outputs above 112.5 MHz (900 MHz / 8) must use an integer divider of
6 (112.5-150 MHz) or 4 (150-200 MHz) and are tuned by moving their PLL instead.
Such an output "owns" its PLL: no other output may demand a different VCO.
Outputs below 112.5 MHz are "dependents" that sit on a PLL and are tuned with
their fractional divider. When an owner retunes its PLL, dependents on that PLL
are recalculated so they stay on frequency.

For the beacon: CLK1 (2m) owns PLLA, CLK2 (70cm, third harmonic) owns PLLB and
CLK0 (6m) is a dependent on either.
"""
import time

_MHZ = 1000000
_BILLION = 1000000000

_REG_STATUS = 0
_REG_OUTPUT_ENABLE = 3
_REG_CLK_CONTROL = 16
_REG_PLL_BASE = (26, 34)
_REG_MS_BASE = (42, 50, 58)
_REG_PLL_RESET = 177
_REG_XTAL_LOAD = 183

_PLL_RESET_BIT = (0x20, 0x80)
_LOAD_CAP = {6: 0x52, 8: 0x92, 10: 0xD2}

_C_MAX = 1048575
_VCO_MIN = 600 * _MHZ
_VCO_MAX = 900 * _MHZ
_FRACTIONAL_MIN_DIV = 8
_OWNER_MIN_HZ = _VCO_MAX // _FRACTIONAL_MIN_DIV  # 112.5 MHz
_OUT_MAX_HZ = 200 * _MHZ
_DEFAULT_DEPENDENT_VCO = 800 * _MHZ

_DRIVE_BITS = {2: 0, 4: 1, 6: 2, 8: 3}


def _encode(a, b, c, div4=False):
    """Pack a PLL or MultiSynth ratio a+b/c into its 8 register bytes."""
    if div4:
        p1, p2, p3 = 0, 0, 1
    else:
        f = 128 * b // c
        p1 = 128 * a + f - 512
        p2 = 128 * b - c * f
        p3 = c
    return bytes((
        (p3 >> 8) & 0xFF,
        p3 & 0xFF,
        ((p1 >> 16) & 0x03) | (0x0C if div4 else 0),
        (p1 >> 8) & 0xFF,
        p1 & 0xFF,
        ((p3 >> 12) & 0xF0) | ((p2 >> 16) & 0x0F),
        (p2 >> 8) & 0xFF,
        p2 & 0xFF,
    ))


def _fraction(num, den):
    """Split num/den into (a, b, c) with b/c the fraction, c <= 1048575."""
    a = num // den
    b = ((num - a * den) * _C_MAX + den // 2) // den
    if b >= _C_MAX:
        return a + 1, 0, 1
    if b == 0:
        return a, 0, 1
    return a, b, _C_MAX


class Si5351:
    PLLA = 0
    PLLB = 1

    def __init__(self, i2c, addr=0x60, xtal=25 * _MHZ, correction_ppb=0,
                 load_pf=8):
        """xtal is the nominal crystal frequency in Hz.

        correction_ppb is the measured crystal error in parts per billion
        (positive if the crystal runs fast); outputs are corrected to match.
        load_pf is the crystal load capacitance: 6, 8 or 10 pF.
        """
        self.i2c = i2c
        self.addr = addr
        self.xtal = xtal
        self.correction_ppb = correction_ppb
        self._pll_hz = [0, 0]
        self._owner = [None, None]
        self._pll_of = [None, None, None]
        self._target = [0, 0, 0]
        self._actual = [0, 0, 0]
        self._drive = [2, 2, 2]
        self._int_mode = [False, False, False]
        self._oe = 0xFF  # 1 = output disabled

        if addr not in i2c.scan():
            raise OSError("Si5351 not found at 0x%02X" % addr)
        self._wait_init()
        self._write(_REG_OUTPUT_ENABLE, bytes((0xFF,)))
        self._write(_REG_CLK_CONTROL, bytes((0x80,) * 8))
        self._write(_REG_XTAL_LOAD, bytes((_LOAD_CAP[load_pf],)))

    # -- low level ---------------------------------------------------------

    def _write(self, reg, data):
        self.i2c.writeto_mem(self.addr, reg, data)

    def _read(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def _wait_init(self, timeout_ms=1000):
        start = time.ticks_ms()
        while self._read(_REG_STATUS) & 0x80:
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                raise OSError("Si5351 did not finish initialising")
            time.sleep_ms(1)

    # -- planning (no I2C traffic) -----------------------------------------

    def _xtal_scaled(self):
        """Corrected crystal frequency as (numerator, denominator)."""
        return self.xtal * (_BILLION + self.correction_ppb), _BILLION

    def _plan_pll(self, vco_hz):
        if not _VCO_MIN <= vco_hz <= _VCO_MAX:
            raise ValueError("VCO %d Hz outside 600-900 MHz" % vco_hz)
        xn, xd = self._xtal_scaled()
        a, b, c = _fraction(vco_hz * xd, xn)
        if not 15 <= a <= 90:
            raise ValueError("PLL multiplier %d out of range" % a)
        # Actual VCO frequency produced by this ratio.
        actual = (xn * (a * c + b) + xd * c // 2) // (xd * c)
        return a, b, c, actual

    def _plan_dependent(self, vco_hz, hz):
        a, b, c = _fraction(vco_hz, hz)
        if a < _FRACTIONAL_MIN_DIV or a > 1800:
            raise ValueError("%d Hz is out of range for a %d Hz VCO" % (hz, vco_hz))
        return a, b, c

    @staticmethod
    def _output_hz(vco_hz, a, b, c):
        n = a * c + b
        return (vco_hz * c + n // 2) // n

    # -- register writes ---------------------------------------------------

    def _write_pll(self, pll, plan):
        a, b, c, actual = plan
        self._write(_REG_PLL_BASE[pll], _encode(a, b, c))
        self._pll_hz[pll] = actual

    def _write_ms(self, ch, a, b, c, div4=False):
        self._write(_REG_MS_BASE[ch], _encode(a, b, c, div4))
        self._int_mode[ch] = b == 0
        self._actual[ch] = self._output_hz(self._pll_hz[self._pll_of[ch]], a, b, c)

    def _write_clk_control(self, ch):
        value = 0x0C | _DRIVE_BITS[self._drive[ch]]
        if self._pll_of[ch] == self.PLLB:
            value |= 0x20
        if self._int_mode[ch]:
            value |= 0x40
        self._write(_REG_CLK_CONTROL + ch, bytes((value,)))

    def _write_oe(self):
        self._write(_REG_OUTPUT_ENABLE, bytes((self._oe,)))

    def _write_dependent(self, ch):
        a, b, c = self._plan_dependent(self._pll_hz[self._pll_of[ch]], self._target[ch])
        self._write_ms(ch, a, b, c)

    # -- public API --------------------------------------------------------

    def set_frequency(self, ch, hz, pll=None, reset=True):
        """Set CLK<ch> to hz and enable it. Returns the actual frequency in Hz.

        pll selects PLLA/PLLB for this output (default: the one it already
        uses, else PLLA). reset=False skips the PLL reset, which avoids a
        glitch for small retunes such as FSK.
        """
        hz = int(hz)
        if not 0 <= ch <= 2:
            raise ValueError("channel must be 0-2")
        if hz > _OUT_MAX_HZ:
            raise ValueError("%d Hz exceeds the 200 MHz output limit" % hz)
        if pll is None:
            pll = self._pll_of[ch] if self._pll_of[ch] is not None else self.PLLA

        if hz > _OWNER_MIN_HZ:
            self._set_owner(ch, hz, pll)
        else:
            self._set_dependent(ch, hz, pll)

        self._write_clk_control(ch)
        if reset:
            self._write(_REG_PLL_RESET, bytes((_PLL_RESET_BIT[pll],)))
        self.enable(ch)
        return self._actual[ch]

    def _set_owner(self, ch, hz, pll):
        if self._owner[pll] not in (None, ch):
            raise ValueError("PLL%s is already owned by CLK%d"
                             % ("AB"[pll], self._owner[pll]))
        div, div4 = (6, False) if hz <= 150 * _MHZ else (4, True)
        plan = self._plan_pll(div * hz)
        vco = plan[3]
        # Check dependents on this PLL can follow before touching anything.
        dependents = [(d, self._plan_dependent(vco, self._target[d]))
                      for d in range(3)
                      if d != ch and self._pll_of[d] == pll and self._target[d]]

        self._release(ch)
        self._owner[pll] = ch
        self._pll_of[ch] = pll
        self._target[ch] = hz
        self._write_pll(pll, plan)
        self._write_ms(ch, div, 0, 1, div4)
        for d, (a, b, c) in dependents:
            self._write_ms(d, a, b, c)
            self._write_clk_control(d)

    def _set_dependent(self, ch, hz, pll):
        if self._owner[pll] is None and not self._pll_hz[pll]:
            self._write_pll(pll, self._plan_pll(_DEFAULT_DEPENDENT_VCO))
        elif self._owner[pll] == ch:
            # Was driving this PLL at a high frequency; no longer needs to.
            self._owner[pll] = None
        plan = self._plan_dependent(self._pll_hz[pll], hz)
        self._release(ch)
        self._pll_of[ch] = pll
        self._target[ch] = hz
        self._write_ms(ch, *plan)

    def _release(self, ch):
        for pll in (0, 1):
            if self._owner[pll] == ch:
                self._owner[pll] = None

    def enable(self, ch, on=True):
        if on:
            self._oe &= ~(1 << ch)
        else:
            self._oe |= 1 << ch
        self._write_oe()

    def disable(self, ch):
        self.enable(ch, False)

    def disable_all(self):
        self._oe = 0xFF
        self._write_oe()

    def set_drive(self, ch, ma):
        """Output drive current: 2, 4, 6 or 8 mA."""
        if ma not in _DRIVE_BITS:
            raise ValueError("drive must be 2, 4, 6 or 8 mA")
        self._drive[ch] = ma
        if self._pll_of[ch] is not None:
            self._write_clk_control(ch)

    def frequency(self, ch):
        """Actual output frequency in Hz (0 if never set)."""
        return self._actual[ch]

    def status(self):
        s = self._read(_REG_STATUS)
        return {
            "sys_init": bool(s & 0x80),
            "lol_b": bool(s & 0x40),
            "lol_a": bool(s & 0x20),
            "los_xtal": bool(s & 0x08),
        }

    def locked(self):
        s = self.status()
        return not (s["lol_a"] or s["lol_b"] or s["los_xtal"])
