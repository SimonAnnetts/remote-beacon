"""Spur map: the strongest close-in spur at each carrier frequency across the band.

The spur pattern of a fractional-N PLL changes with the carrier frequency, so a single-frequency measurement can
mislead. This steps across the band and records the whole +/-window spectrum at each frequency.
"""
from benchlib import spectrum

NAME = "spur_map"
VERSION = 1      # bump this when the procedure or its defaults change, so old and new runs are not compared as like for like
TITLE = "Spur map (close-in spurs against carrier frequency)"

BANDS = {
    "70cm": {"start": 430.0, "stop": 440.0, "step": 0.25, "window_mhz": 5.0},
    "2m": {"start": 144.0, "stop": 146.0, "step": 0.1, "window_mhz": 2.0},
    "6m": {"start": 50.0, "stop": 52.0, "step": 0.1, "window_mhz": 2.0},
}


def frequencies(p):
    n = int(round((p["stop"] - p["start"]) / p["step"]))
    return [round(p["start"] + i * p["step"], 6) for i in range(n + 1)]


def defaults(rig):
    p = dict(BANDS[rig.output])
    p.update({"drives": [2, 8], "points": 401, "n": 3, "store_traces": True, "top": 8})
    return p


def estimate_s(p):
    return len(frequencies(p)) * len(p["drives"]) * (0.3 + p["n"] * 1.7)


def run(rig, p, log):
    step_hz = 2 * p["window_mhz"] * 1e6 / (p["points"] - 1)
    rbw = spectrum.rbw_for_step(step_hz)
    rig.use_rbw(rbw)
    guard = max(5 * rbw * 1e3, 100e3)      # closer than this the analyser's own filter skirt is indistinguishable from a spur
    fos = frequencies(p)
    out = {"window_mhz": p["window_mhz"], "rbw_khz": rbw, "guard_khz": guard / 1e3,
           "offsets_mhz": [round(-p["window_mhz"] + 2 * p["window_mhz"] * i / (p["points"] - 1), 4) for i in range(p["points"])],
           "series": []}
    for drive in p["drives"]:
        s = {"drive": drive, "fo_mhz": [], "carrier_dbm": [], "floor_dbm": [], "spurs": [], "trace_dbc": []}
        for i, fo in enumerate(fos):
            carrier, wanted = rig.set_wanted(fo * 1e6, drive)
            rig.sleep(0.3)
            freqs, db = rig.sweep_avg(wanted - p["window_mhz"] * 1e6, wanted + p["window_mhz"] * 1e6, p["points"], p["n"])
            c_dbm, c_hz, floor, spurs = spectrum.extract_spurs(freqs, db, guard, 8.0, p["top"])
            s["fo_mhz"].append(fo)
            s["carrier_dbm"].append(round(c_dbm, 2))
            s["floor_dbm"].append(round(floor, 2))
            s["spurs"].append([[round(o / 1e6, 3), round(d, 1)] for o, d in spurs])
            if p["store_traces"]:
                s["trace_dbc"].append([round(x - c_dbm, 1) for x in db])
            if i % 10 == 0:
                log("  %d mA %.2f MHz (%d/%d): carrier %.1f dBm, worst spur %s dBc" % (
                    drive, fo, i + 1, len(fos), c_dbm, "%.1f" % spurs[0][1] if spurs else "none above floor"))
        out["series"].append(s)
    rig.off()
    return out
