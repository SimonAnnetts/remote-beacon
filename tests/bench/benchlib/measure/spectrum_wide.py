"""Wide spectrum, 5 MHz to the analyser limit, for out-of-band emissions (harmonics and other spurs).

The strongest signals found are then re-measured with extra analyser attenuation. The TinySA corrects its readings back to
the input, so a REAL signal reads the same; a spur the analyser makes itself (from the strong wanted signal) falls.
"""
from benchlib import spectrum

NAME = "spectrum_wide"
VERSION = 2      # bump this when the procedure or its defaults change, so old and new runs are not compared as like for like
# v2: strongest out-of-band signals are re-measured with extra analyser attenuation (real or analyser-made)
TITLE = "Wide spectrum (out-of-band emissions)"

CENTRE = {"70cm": 435.0, "2m": 145.0, "6m": 51.0}


def defaults(rig):
    return {"configs": [[CENTRE[rig.output], 2], [CENTRE[rig.output], 8]], "start_mhz": 5.0, "stop_mhz": rig.max_freq_hz / 1e6,
            "rbw_khz": 100, "points": 450, "n": 2, "verify_top": 6, "verify_att_db": 10, "verify_min_dbc": -70.0}


def windows(p):
    step = p["rbw_khz"] * 1e3
    start, stop = p["start_mhz"] * 1e6, p["stop_mhz"] * 1e6
    out = []
    while start < stop:
        end = min(start + step * (p["points"] - 1), stop)
        out.append((start, end, int(round((end - start) / step)) + 1))
        start = end + step
    return out


def estimate_s(p):
    return len(p["configs"]) * (len(windows(p)) * p["n"] * 2.5 + p["verify_top"] * 2.5)


def verify(rig, p, wanted_hz, freq_mhz, dbm, log):
    """Re-measure the strongest out-of-band peaks with extra analyser attenuation: [{freq_mhz, base_dbm, att_dbm, att_db}]."""
    peaks, floor = spectrum.find_peaks(freq_mhz, dbm, 12.0)
    wanted = wanted_hz / 1e6
    ref = max((l for f, l in peaks if abs(f - wanted) <= 3.0), default=None)
    exclude = max(2.0, 0.03 * wanted)
    cands = sorted(((l, f) for f, l in peaks if abs(f - wanted) > exclude and ref is not None and l - ref >= p["verify_min_dbc"]), reverse=True)
    cands = [(f, l) for l, f in cands[:p["verify_top"]]]
    if not cands:
        return []
    base_att = rig.analyser.get_attenuation_db() if hasattr(rig.analyser, "get_attenuation_db") else 0
    base_att = base_att or 0
    out = []
    rig.use_rbw(10)
    try:
        for f, _ in cands:
            base = rig.window_peak(f * 1e6, 150e3, 41, 2)[0]
            rig.analyser.set_attenuation_db(base_att + p["verify_att_db"])
            att = rig.window_peak(f * 1e6, 150e3, 41, 2)[0]
            rig.analyser.set_attenuation_db(base_att)
            out.append({"freq_mhz": f, "base_dbm": round(base, 2), "att_dbm": round(att, 2), "att_db": p["verify_att_db"]})
            log("    %.1f MHz: %.1f dBm, with +%d dB analyser attenuation %.1f dBm" % (f, base, p["verify_att_db"], att))
    finally:
        rig.analyser.set_attenuation_db(base_att)
        rig.use_rbw(p["rbw_khz"])
    return out


def run(rig, p, log):
    rig.use_rbw(p["rbw_khz"])
    out = {"rbw_khz": p["rbw_khz"], "configs": []}
    for fo, drive in p["configs"]:
        carrier, wanted = rig.set_wanted(fo * 1e6, drive)
        rig.sleep(0.5)
        freq_mhz, dbm = [], []
        for start, end, pts in windows(p):
            if pts < 2:
                continue
            f, d = rig.sweep_avg(start, end, pts, p["n"])
            freq_mhz += [round(x / 1e6, 4) for x in f]
            dbm += [round(x, 1) for x in d]
        out["configs"].append({"fo_mhz": fo, "drive": drive, "wanted_hz": wanted, "carrier_hz": carrier, "freq_mhz": freq_mhz, "dbm": dbm,
                               "verify": verify(rig, p, wanted, freq_mhz, dbm, log) if p["verify_top"] else []})
        log("  %.2f MHz %d mA: %d points" % (fo, drive, len(dbm)))
    rig.off()
    return out
