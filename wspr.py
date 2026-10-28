"""WSPR type 1 message encoder (callsign, 4-character locator, power in dBm).

Produces the 162 channel symbols (0-3). Symbol s is sent on a tone
s * TONE_SPACING above the lowest tone; each symbol lasts SYMBOL_US.
Compound callsigns (with /) and 6-character locators are type 2/3 messages and
are not supported.
"""

SYMBOLS = 162
# 12000 / 8192 Hz, as the exact fraction 375/256.
TONE_SPACING_NUM = 375
TONE_SPACING_DEN = 256
# One symbol is 8192 / 12000 s.
SYMBOL_US_NUM = 8192 * 1000000
SYMBOL_US_DEN = 12000

VALID_DBM = (0, 3, 7, 10, 13, 17, 20, 23, 27, 30, 33, 37, 40, 43, 47, 50, 53, 57, 60)

_SYNC = bytes((
    1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0, 0,
    1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0,
    0, 0, 0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 0, 1,
    0, 0, 0, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0,
    1, 1, 0, 0, 0, 1, 1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1,
    0, 0, 1, 0, 0, 1, 1, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 0, 0, 1,
    1, 1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0,
    1, 1, 0, 1, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0,
))


def _code(ch):
    if "0" <= ch <= "9":
        return ord(ch) - 48
    if "A" <= ch <= "Z":
        return ord(ch) - 55
    return 36  # space


def _letter_code(ch):
    """Code for a position that may only hold a letter or a space (0-26)."""
    if ch == " ":
        return 26
    if "A" <= ch <= "Z":
        return ord(ch) - 65
    raise ValueError("callsign: expected a letter or space, got %r" % ch)


def normalize_call(call):
    """Return the callsign padded to the 6 characters of a type 1 message:
    the third character must be a digit."""
    call = call.upper()
    if not call or len(call) > 6 or not all(c.isdigit() or "A" <= c <= "Z" for c in call):
        raise ValueError("WSPR callsign must be 1-6 letters and digits")
    if len(call) > 2 and call[1].isdigit() and "A" <= call[2] <= "Z":
        call = " " + call
    call += " " * (6 - len(call))
    if not call[2].isdigit() or len(call) != 6:
        raise ValueError("WSPR callsign needs a digit as its 2nd or 3rd character")
    return call


def normalize_grid(grid):
    grid = grid.upper()[:4]
    if (len(grid) != 4 or not ("A" <= grid[0] <= "R" and "A" <= grid[1] <= "R")
            or not (grid[2].isdigit() and grid[3].isdigit())):
        raise ValueError("WSPR needs a locator starting with 2 letters A-R and 2 digits")
    return grid


def pack(call, grid, dbm):
    """Return the 50 message bits as (callsign_28_bits, locator_power_22_bits)."""
    if dbm not in VALID_DBM:
        raise ValueError("WSPR power must be one of %s dBm" % (VALID_DBM,))
    call = normalize_call(call)
    grid = normalize_grid(grid)
    n = _code(call[0])
    n = n * 36 + _code(call[1])
    n = n * 10 + _code(call[2])
    n = n * 27 + _letter_code(call[3])
    n = n * 27 + _letter_code(call[4])
    n = n * 27 + _letter_code(call[5])
    m = ((179 - 10 * (ord(grid[0]) - 65) - int(grid[2])) * 180
         + 10 * (ord(grid[1]) - 65) + int(grid[3]))
    m = m * 128 + dbm + 64
    return n, m


def _parity(x):
    return bin(x).count("1") & 1


def encode(call, grid, dbm):
    """Return the 162 channel symbols (each 0-3) as bytes."""
    n, m = pack(call, grid, dbm)
    # 50 message bits followed by 31 zero bits flush the encoder.
    bits = (((n << 22) | m) << 31)
    reg = 0
    coded = []
    for i in range(80, -1, -1):
        reg = ((reg << 1) | ((bits >> i) & 1)) & 0xFFFFFFFF
        coded.append(_parity(reg & 0xF2D05351))
        coded.append(_parity(reg & 0xE4613C47))
    # Interleave: write bit p to the bit-reversed position, skipping positions >= 162.
    inter = [0] * SYMBOLS
    p = 0
    for i in range(256):
        j = 0
        for k in range(8):  # reverse the 8 bits of i
            j |= ((i >> k) & 1) << (7 - k)
        if j < SYMBOLS:
            inter[j] = coded[p]
            p += 1
    return bytes(_SYNC[i] + 2 * inter[i] for i in range(SYMBOLS))


def symbol_start_us(i):
    """Offset of symbol i from the start of the transmission, in microseconds."""
    return i * SYMBOL_US_NUM // SYMBOL_US_DEN
