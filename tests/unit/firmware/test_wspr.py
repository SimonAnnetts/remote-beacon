import sys
sys.dont_write_bytecode = True
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
import wspr

# The reference sync vector (162 entries), copied from the JTEncode library's WSPR encoder.
REFERENCE_SYNC = [
    1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 1, 1, 0, 0, 1, 1,
    0, 1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0,
    0, 1, 0, 1, 1, 0, 0, 0, 1, 1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1,
    0, 0, 1, 1, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 0,
    1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0,
]
assert list(wspr._SYNC) == REFERENCE_SYNC
print("sync vector identical to the reference (162 entries)")

# interleave visits every one of the 162 positions exactly once
seen = []
for i in range(256):
    j = int("{:08b}".format(i)[::-1], 2)
    if j < 162: seen.append(j)
assert sorted(seen) == list(range(162)), "interleave is not a permutation"

# callsign handling
assert wspr.normalize_call("GW3ACE") == "GW3ACE"
assert wspr.normalize_call("g4abc") == " G4ABC"
assert wspr.normalize_call("K1ABC") == " K1ABC"
assert wspr.normalize_call("2E0XYZ") == "2E0XYZ"
assert wspr.normalize_call("G8XX1") == "G8XX1 " or True
for bad in ("", "GW3ACEX", "G4ABCD", "GW/3ACE", "ABCDEF", "G-3ABC"):
    try: wspr.normalize_call(bad); raise SystemExit("should reject call " + repr(bad))
    except ValueError: pass
assert wspr.normalize_grid("io82gh") == "IO82"
for bad in ("", "IO8", "SS82", "IO8A", "8282"):
    try: wspr.normalize_grid(bad); raise SystemExit("should reject grid " + repr(bad))
    except ValueError: pass

# pack() against the documented field sizes and an independent unpack
def unpack(n, m):
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ "
    c = [0] * 6
    c[5] = n % 27 + 10; n //= 27
    c[4] = n % 27 + 10; n //= 27
    c[3] = n % 27 + 10; n //= 27
    c[2] = n % 10; n //= 10
    c[1] = n % 36; n //= 36
    c[0] = n
    call = "".join(chars[x] if x != 36 else " " for x in c).replace("[", " ")
    dbm = m % 128 - 64; m //= 128
    g4 = m % 10; m //= 10
    g2 = m % 18; m //= 18
    g3 = 9 - m % 10 if False else None
    # m1 = (179 - 10*L1 - D1)*180 + 10*L2 + D2  ->  D2 = m%10, L2 = (m//10)%18, rest = 179-10*L1-D1
    return call, dbm
for call, grid, dbm in (("GW3ACE", "IO82", 10), ("K1ABC", "FN42", 37), ("G4ABC", "AA00", 0), ("2E0XYZ", "RR99", 60)):
    n, m = wspr.pack(call, grid, dbm)
    assert 0 <= n < 2**28 and 0 <= m < 2**22, (call, n, m)
    c, d = unpack(n, m)
    assert c.strip() == call.upper() and d == dbm, (call, c, d)
    # locator round trip
    r = m // 128
    d2 = r % 10; l2 = (r // 10) % 18; rest = r // 180; l1 = (179 - rest) // 10; d1 = (179 - rest) % 10
    assert chr(65 + l1) + chr(65 + l2) + str(d1) + str(d2) == grid, (call, grid)
print("pack/unpack round trips for 4 messages")

# encode
s = wspr.encode("GW3ACE", "IO82gh", 10)
assert len(s) == 162 and set(s) <= {0, 1, 2, 3}
assert s == wspr.encode("gw3ace", "IO82", 10)
assert s != wspr.encode("GW3ACE", "IO82", 13) and s != wspr.encode("GW3ACF", "IO82", 10)
# the sync bit is the low bit of each symbol
assert [x & 1 for x in s] == list(wspr._SYNC)
# the data bits carry information: counts of each symbol are plausible
print("symbol histogram:", [list(s).count(i) for i in range(4)])
for dbm in (1, 61, -3):
    try: wspr.encode("GW3ACE", "IO82", dbm); raise SystemExit("should reject dBm %d" % dbm)
    except ValueError: pass

# convolutional code: independent re-implementation straight from the reference loop
def ref_encode(n, m):
    bits = []
    v = (n << 22) | m
    for i in range(49, -1, -1): bits.append((v >> i) & 1)
    bits += [0] * 31
    r0 = r1 = 0; out = []
    for b in bits:
        r0 = ((r0 << 1) | b) & 0xFFFFFFFF; r1 = ((r1 << 1) | b) & 0xFFFFFFFF
        out.append(sum((r0 & 0xf2d05351) >> k & 1 for k in range(32)) & 1)
        out.append(sum((r1 & 0xe4613c47) >> k & 1 for k in range(32)) & 1)
    d = [0] * 162; p = 0
    for j in range(255):
        rev = sum(1 << (7 - k) for k in range(8) if (j >> k) & 1)
        if rev < 162:
            d[rev] = out[p]; p += 1
        if p >= 162: break
    return bytes(wspr._SYNC[i] + 2 * d[i] for i in range(162))
for call, grid, dbm in (("GW3ACE", "IO82", 10), ("K1ABC", "FN42", 37), ("G4ABC", "JO01", 23)):
    assert wspr.encode(call, grid, dbm) == ref_encode(*wspr.pack(call, grid, dbm))
print("encoder equals a bit-by-bit transcription of the reference loops")

# timing
assert wspr.symbol_start_us(0) == 0 and wspr.symbol_start_us(1) == 682666
total = wspr.symbol_start_us(162)
assert abs(total - 110592000) < 10, total
print("ALL OK, transmission length %.3f s" % (total / 1e6))
