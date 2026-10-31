"""Close-in spectra at fixed frequencies and drives (+/- a window around the carrier)."""
from benchlib import spectrum

NAME = "spectrum_close"
VERSION = 1      # bump this when the procedure or its defaults change, so old and new runs are not compared as like for like
TITLE = "Close-in spectrum at chosen frequencies"

CONFIGS = {
    "70cm": [[432.45, 2], [432.45, 8], [435.0, 2], [435.0, 4], [435.0, 6], [435.0, 8], [438.0, 2], [438.0, 8]],
    "2m": [[145.0, 2], [145.0, 4], [145.0, 6], [145.0, 8]],
    "6m": [[51.0, 2], [51.0, 4], [51.0, 6], [51.0, 8]],
}
WINDOW = {"70cm": 5.0, "2m": 2.0, "6m": 2.0}


def defaults(rig):
    return {"configs": CONFIGS[rig.output], "window_mhz": WINDOW[rig.output], "points": 401, "n": 6, "store_traces": True, "top": 12}


def estimate_s(p):
    return len(p["configs"]) * (0.5 + p["n"] * 1.7)


def run(rig, p, log):
    step_hz = 2 * p["window_mhz"] * 1e6 / (p["points"] - 1)
    rbw = spectrum.rbw_for_step(step_hz)
    rig.use_rbw(rbw)
    guard = max(5 * rbw * 1e3, 100e3)      # closer than this the analyser's own filter skirt is indistinguishable from a spur
    out = {"window_mhz": p["window_mhz"], "rbw_khz": rbw, "guard_khz": guard / 1e3,
           "offsets_mhz": [round(-p["window_mhz"] + 2 * p["window_mhz"] * i / (p["points"] - 1), 4) for i in range(p["points"])],
           "configs": []}
    for fo, drive in p["configs"]:
        carrier, wanted = rig.set_wanted(fo * 1e6, drive)
        rig.sleep(0.5)
        freqs, db = rig.sweep_avg(wanted - p["window_mhz"] * 1e6, wanted + p["window_mhz"] * 1e6, p["points"], p["n"])
        c_dbm, c_hz, floor, spurs = spectrum.extract_spurs(freqs, db, guard, 8.0, p["top"])
        entry = {"fo_mhz": fo, "drive": drive, "wanted_hz": wanted, "carrier_dbm": round(c_dbm, 2), "floor_dbm": round(floor, 2),
                 "spurs": [[round(o / 1e6, 3), round(d, 1)] for o, d in spurs]}
        if p["store_traces"]:
            entry["trace_dbc"] = [round(x - c_dbm, 1) for x in db]
        out["configs"].append(entry)
        log("  %.2f MHz %d mA: carrier %.1f dBm, worst spur %s dBc" % (fo, drive, c_dbm, "%.1f" % spurs[0][1] if spurs else "none above floor"))
    rig.off()
    return out
