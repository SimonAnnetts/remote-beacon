#!/usr/bin/env python3
"""Convert the first (pre-framework) 70cm campaign data into the stored-run format.

Usage: python3 tests/bench/legacy_import.py docs/data/70cm-saw-2026-10-31.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchlib import results, setups, spectrum  # noqa: E402

STARTED = "2026-10-31T01:35:51"


def convert(old, setup, started=STARTED):
    saw = sorted(old["saw"], key=lambda x: x["fo_target"])
    orders = ["1", "2", "3", "4"]
    response = {"fo_mhz": [x["fo_target"] / 1e6 for x in saw], "carrier_hz": [x["carrier"] for x in saw],
                "orders": {k: {"dbm": [x["lev"].get(k) for x in saw], "floor": [x["floor"].get(k) for x in saw]} for k in orders}}
    wide_cfgs = []
    for w in old["wide"]:
        floors = [f[1] for f in w["floors"]]
        wide_cfgs.append({"fo_mhz": w["fo"], "drive": w["drive"], "wanted_hz": w["fo"] * 1e6, "carrier_hz": w["carrier"],
                          "peaks": w["peaks"], "floor_dbm": round(spectrum.median(floors), 1)})
    close = [{"fo_mhz": c["fo"], "drive": c["drive"], "wanted_hz": c["carrier_hz"], "carrier_dbm": c["carrier_dbm"],
              "floor_dbm": c["floor"], "spurs": [[o, dbc] for o, lev, dbc in c["spurs"]]} for c in old["close_in"]]
    run = {"schema": results.SCHEMA, "run_id": results.new_run_id(setup["id"], None), "started": started,
           "finished": "2026-10-31T01:48:12", "output": setup["output"], "setup": setup, "pad_db": setups.pad_db(setup),
           "legacy": True, "note": "Imported from docs/data/70cm-saw-2026-10-31.json (the pre-framework campaign). "
           "No spur map or full-resolution traces were recorded; the wide spectrum kept only its peak list. "
           "CAUTION: that peak list missed any peak on the first or last point of a scan window, so it MISSED the 725 MHz "
           "5th harmonic (-33 dBc); its out-of-band figures are too optimistic.",
           "environment": {"git": {"commit": "7859547", "dirty": None},
                           "pico": {"micropython": "1.29.0", "correction_ppb": 151300},
                           "analyser": {"model": "tinySA4", "firmware": "tinySA4_v1.4-200-g26fc821", "hardware": "V0.4.6", "attenuation_db": 0}},
           "tests": {
               "response": {"params": {"segments": [[340, 424, 1.0], [425, 445, 0.25], [446, 500, 1.0]], "drive": 8, "orders": [1, 2, 3, 4],
                                       "wanted_order": 3, "rbw_khz": 10, "half_khz": 150, "points": 41, "n": 2}, "data": response},
               "spectrum_close": {"params": {"configs": [[c["fo"], c["drive"]] for c in old["close_in"]], "window_mhz": 5.0, "points": 401, "n": 6,
                                             "store_traces": False, "top": 12}, "data": {"window_mhz": 5.0, "rbw_khz": 30, "guard_khz": 150, "configs": close}},
               "spectrum_wide": {"params": {"configs": [[w["fo"], w["drive"]] for w in old["wide"]], "start_mhz": 5.0, "stop_mhz": 800.0,
                                            "rbw_khz": 100, "points": 450, "n": 2}, "data": {"rbw_khz": 100, "configs": wide_cfgs}},
               "drive_levels": {"params": {"fo_mhz": 435.0, "drives": [2, 4, 6, 8], "orders": [1, 3], "rbw_khz": 10, "half_khz": 150, "points": 41, "n": 2}, "data": {"fo_mhz": 435.0, "rows": [{"drive": d["drive"], "lev": d["lev"]} for d in old["drive"]]}},
           }}
    run["run_id"] = "%s__%s" % (started.replace(":", "-"), setup["id"])
    return run


def main():
    src = Path(sys.argv[1])
    setup = setups.load("70cm-saw-unknown-10dB")
    run = convert(json.loads(src.read_text()), setup)
    print("saved", results.save(run))


if __name__ == "__main__":
    main()
