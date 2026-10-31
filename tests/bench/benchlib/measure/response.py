"""Filter / chain response: step the wanted frequency and read the level at each order of the carrier.

For a harmonic output (70cm) the wanted signal is the 3rd harmonic of the carrier, so this traces the filter's
passband and skirts and shows how much of the fundamental and other orders gets through at each step.
"""
NAME = "response"
# v2: also reads the 5th order of the carrier (for 70cm, 717-783 MHz: the filter's rejection of the carrier's 5th harmonic)
VERSION = 2      # bump this when the procedure or its defaults change, so old and new runs are not compared as like for like
TITLE = "Chain response (stepped carrier)"

# The Si5351 produces frequencies in two ways: below 100 MHz with a fractional MultiSynth divider on an 800 MHz VCO, and from
# 113 MHz up by moving the PLL (integer divider 6, or 4 above 150 MHz). Nothing can be made between 100 and 112.5 MHz, so the
# plans for 6m and 2m step over that gap.
SEGMENTS = {
    "70cm": [[340, 424, 1.0], [425, 445, 0.25], [446, 500, 1.0]],
    "2m": [[60, 100, 2.0], [113, 140, 1.0], [140, 150, 0.25], [151, 200, 1.0]],
    "6m": [[10, 45, 1.0], [45, 56, 0.25], [57, 100, 1.0], [113, 140, 3.0]],
}


def expand(segments):
    seen = {}
    for start, stop, step in segments:
        n = int(round((stop - start) / step))
        for i in range(n + 1):
            seen[round(start + i * step, 6)] = True
    return sorted(seen)


def defaults(rig):
    return {"segments": SEGMENTS[rig.output], "drive": 8, "orders": [1, 2, 3, 4, 5], "wanted_order": rig.mult,
            "rbw_khz": 10, "half_khz": 150, "points": 41, "n": 2}


def estimate_s(p):
    return len(expand(p["segments"])) * (0.15 + len(p["orders"]) * p["n"] * 0.32)


def run(rig, p, log):
    rig.use_rbw(p["rbw_khz"])
    fos = expand(p["segments"])
    data = {"fo_mhz": [], "carrier_hz": [], "orders": {str(k): {"dbm": [], "floor": []} for k in p["orders"]}}
    for i, fo in enumerate(fos):
        carrier, wanted = rig.set_wanted(fo * 1e6, p["drive"])
        rig.sleep(0.05)
        data["fo_mhz"].append(fo)
        data["carrier_hz"].append(carrier)
        for k in p["orders"]:
            fk = k * carrier
            if fk > rig.max_freq_hz:
                data["orders"][str(k)]["dbm"].append(None)
                data["orders"][str(k)]["floor"].append(None)
                continue
            peak, floor = rig.window_peak(fk, p["half_khz"] * 1e3, p["points"], p["n"])
            data["orders"][str(k)]["dbm"].append(round(peak, 2))
            data["orders"][str(k)]["floor"].append(round(floor, 2))
        if i % 20 == 0:
            log("  %.2f MHz (%d/%d)" % (fo, i + 1, len(fos)))
    rig.off()
    return data
