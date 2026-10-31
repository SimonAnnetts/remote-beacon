"""Level of the wanted signal and its other orders against Si5351 drive strength."""
NAME = "drive_levels"
VERSION = 1      # bump this when the procedure or its defaults change, so old and new runs are not compared as like for like
TITLE = "Level against drive strength"

CENTRE = {"70cm": 435.0, "2m": 145.0, "6m": 51.0}


def defaults(rig):
    return {"fo_mhz": CENTRE[rig.output], "drives": [2, 4, 6, 8], "orders": sorted({1, rig.mult}), "rbw_khz": 10,
            "half_khz": 150, "points": 41, "n": 2}


def estimate_s(p):
    return len(p["drives"]) * (0.3 + len(p["orders"]) * p["n"] * 0.32)


def run(rig, p, log):
    rig.use_rbw(p["rbw_khz"])
    rows = []
    for drive in p["drives"]:
        carrier, wanted = rig.set_wanted(p["fo_mhz"] * 1e6, drive)
        rig.sleep(0.3)
        lev = {}
        for k in p["orders"]:
            fk = k * carrier
            if fk <= rig.max_freq_hz:
                lev[str(k)] = round(rig.window_peak(fk, p["half_khz"] * 1e3, p["points"], p["n"])[0], 2)
        rows.append({"drive": drive, "lev": lev})
        log("  %d mA: %s" % (drive, lev))
    rig.off()
    return {"fo_mhz": p["fo_mhz"], "rows": rows}
