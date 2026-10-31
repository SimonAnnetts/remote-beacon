#!/usr/bin/env python3
"""Run bench measurements on one Si5351 output and store the result in tests-results/.

Examples:
  python3 tests/bench/run.py --list
  python3 tests/bench/run.py --setup 70cm-saw-unknown-10dB --dry-run
  python3 tests/bench/run.py --setup 70cm-saw-unknown-10dB --tests spur_map,drive_levels
  python3 tests/bench/run.py --setup 70cm-saw-unknown-10dB --set spur_map.step=0.5 --note "after re-seating the SAW"

The Pico's beacon firmware is stopped while this runs and the board is rebooted at the end. Only the Si5351 output
named in the setup is enabled, one frequency at a time.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchlib import results, setups  # noqa: E402
from benchlib.measure import DEFAULT_ORDER, MEASUREMENTS  # noqa: E402
from benchlib.rig import Rig  # noqa: E402


OVERLOAD_DBM = -25.0       # above this at the TinySA input its front end starts to make its own spurs


class OverloadError(RuntimeError):
    pass


def top_drive(rows):
    """Highest Si5351 drive strength any of the planned measurements will use."""
    drive = 2
    for _, params, _ in rows:
        for d in params.get("drives", []):
            drive = max(drive, d)
        drive = max(drive, params.get("drive", 2))
        for c in params.get("configs", []):
            drive = max(drive, c[1])
    return drive


def headroom_level(rig, drive):
    """Level at the analyser, at the band centre, for the highest drive the plan will use."""
    rig.use_rbw(10)
    carrier, wanted = rig.set_wanted(rig.band_centre_mhz * 1e6, drive)
    rig.sleep(0.3)
    return rig.window_peak(wanted, 150e3, 41, 2)[0]


def _iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))


def reference_point(rig, drive=2):
    """Wanted level at the band centre: measured at the start and the end of a run to show drift."""
    rig.use_rbw(10)
    carrier, wanted = rig.set_wanted(rig.band_centre_mhz * 1e6, drive)
    rig.sleep(0.3)
    peak, floor = rig.window_peak(wanted, 150e3, 41, 3)
    return {"fo_mhz": rig.band_centre_mhz, "drive": drive, "wanted_dbm": round(peak, 2), "floor_dbm": round(floor, 2)}


def parse_overrides(items):
    out = {}
    for item in items or []:
        key, _, raw = item.partition("=")
        test, _, param = key.partition(".")
        if not param:
            raise SystemExit("--set needs test.param=value, got %r" % item)
        try:
            value = json.loads(raw)
        except ValueError:
            value = raw
        out.setdefault(test, {})[param] = value
    return out


def plan(rig, names, overrides):
    rows = []
    for name in names:
        mod = MEASUREMENTS[name]
        params = mod.defaults(rig)
        params.update(overrides.get(name, {}))
        rows.append((name, params, mod.estimate_s(params)))
    return rows


def execute(setup, analyser, pico, names, overrides=None, results_dir=results.RESULTS_DIR, note="",
            log=print, sleep=time.sleep, force=False):
    """Run the named measurements and save the result after each one. Returns (run, path).

    Refuses (raising OverloadError, saving nothing) if the signal at the highest planned drive would overload the analyser,
    unless force is set."""
    overrides = overrides or {}
    rig = Rig(setup, analyser, pico, sleep=sleep)
    snap = analyser.snapshot()
    started = time.time()
    run = {"schema": results.SCHEMA, "run_id": results.new_run_id(setup["id"], time.localtime(started)), "started": _iso(started),
           "output": setup["output"], "setup": setup, "pad_db": rig.pad_db, "note": note,
           "environment": {"git": results.git_info(), "pico": pico.info(), "analyser": analyser.info()}, "tests": {}}
    path = results.path_for(run, results_dir)
    run["status"] = "incomplete"
    refused = False
    try:
        analyser.set_attenuation_db(setup.get("analyser", {}).get("attenuation_db", 0))
        analyser.set_lna(bool(setup.get("analyser", {}).get("lna", False)))
        rows = plan(rig, names, overrides)
        top = top_drive(rows)
        level = headroom_level(rig, top)
        run["environment"]["headroom"] = {"drive": top, "level_dbm": round(level, 1), "limit_dbm": OVERLOAD_DBM}
        log("headroom: %.1f dBm at the analyser with %d mA (limit %.0f dBm)" % (level, top, OVERLOAD_DBM))
        if level > OVERLOAD_DBM and not force:
            refused = True
            raise OverloadError("the signal at the analyser would be %.1f dBm at %d mA, above the %.0f dBm limit where its front end "
                                "distorts. Add attenuation (and say so in the setup), or restrict the drives, e.g. "
                                "--set spur_map.drives=[2]; or run with --force to measure anyway." % (level, top, OVERLOAD_DBM))
        log("reference point at the start")
        run["environment"]["reference_start"] = reference_point(rig)
        for name, params, est in rows:
            log("== %s (%s), about %d s" % (name, MEASUREMENTS[name].TITLE, est))
            t0 = time.time()
            data = MEASUREMENTS[name].run(rig, params, log)
            run["tests"][name] = {"version": MEASUREMENTS[name].VERSION, "params": params, "data": data, "duration_s": round(time.time() - t0, 1)}
            results.save(run, results_dir)
        log("reference point at the end")
        run["environment"]["reference_end"] = reference_point(rig)
        a, b = run["environment"]["reference_start"]["wanted_dbm"], run["environment"]["reference_end"]["wanted_dbm"]
        run["environment"]["drift_db"] = round(b - a, 2)
        if abs(b - a) > 1.0:
            log("WARNING: the reference level drifted by %.1f dB during the run" % (b - a))
        run["status"] = "complete"
        run["environment"]["max_level_dbm"] = round(rig.max_level_dbm, 1)
        if rig.max_level_dbm > OVERLOAD_DBM:
            log("WARNING: the analyser saw up to %.1f dBm (limit %.0f): treat the close-in spurs with caution" % (rig.max_level_dbm, OVERLOAD_DBM))
    except Exception as e:
        run["status"] = "failed"
        run["error"] = "%s: %s" % (type(e).__name__, e)
        raise
    finally:
        try:
            rig.off()
        except Exception:
            pass
        try:
            analyser.restore(snap)
        except Exception:
            pass
        run["finished"] = _iso()
        if not refused:
            results.save(run, results_dir)
    return run, path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--setup", help="setup id (tests/bench/setups/<id>.json) or a path")
    ap.add_argument("--tests", default="all", help="comma list of: %s (default all)" % ", ".join(MEASUREMENTS))
    ap.add_argument("--set", action="append", metavar="TEST.PARAM=VALUE", help="override a test parameter (JSON value)")
    ap.add_argument("--note", default="", help="free text stored with the run")
    ap.add_argument("--force", action="store_true", help="measure even if the analyser input would exceed -25 dBm")
    ap.add_argument("--dry-run", action="store_true", help="show what would run and how long it takes")
    ap.add_argument("--list", action="store_true", help="list tests and setups")
    ap.add_argument("--fake", action="store_true", help="use simulated instruments (no hardware)")
    ap.add_argument("--no-reboot", action="store_true", help="leave the Pico in the raw REPL instead of rebooting it")
    ap.add_argument("--pico-port", default="/dev/ttyACM0")
    ap.add_argument("--analyser-port", default=None)
    ap.add_argument("--results-dir", default=str(results.RESULTS_DIR))
    a = ap.parse_args()

    if a.list:
        print("tests:")
        for n, m in MEASUREMENTS.items():
            print("  %-15s %s" % (n, m.TITLE))
        print("setups:")
        for s in setups.list_setups():
            print("  %-28s %-5s %s" % (s["id"], s["output"], s["description"]))
        return 0
    if not a.setup:
        ap.error("--setup is required")
    setup = setups.load(a.setup)
    names = DEFAULT_ORDER if a.tests == "all" else [t.strip() for t in a.tests.split(",") if t.strip()]
    for n in names:
        if n not in MEASUREMENTS:
            ap.error("unknown test %r" % n)
    overrides = parse_overrides(a.set)

    if a.dry_run:
        from benchlib.fakes import FakeAnalyser, FakePico, FakeWorld
        world = FakeWorld()
        rig = Rig(setup, FakeAnalyser(world), FakePico(world))
        total = 0
        print("setup:", setups.describe(setup), "(pad %.1f dB)" % rig.pad_db)
        for name, params, est in plan(rig, names, overrides):
            print("  %-15s about %4d s   %s" % (name, est, json.dumps({k: v for k, v in params.items() if k != "segments"})))
            total += est
        print("total about %d min" % round(total / 60))
        return 0

    if a.fake:
        from benchlib.fakes import FakeAnalyser, FakePico, FakeWorld
        world = FakeWorld()
        analyser, pico, sleep = FakeAnalyser(world), FakePico(world), (lambda s: None)
    else:
        from benchlib.pico import Pico
        from benchlib.tinysa import TinySA
        analyser = TinySA(a.analyser_port or setup.get("analyser", {}).get("port", "/dev/ttyACM1"))
        pico, sleep = Pico(a.pico_port), time.sleep

    def log(msg):
        print(time.strftime("%H:%M:%S"), msg, flush=True)

    log("setup: " + setups.describe(setup))
    try:
        run, path = execute(setup, analyser, pico, names, overrides, a.results_dir, a.note, log, sleep, force=a.force)
        log("saved %s" % path)
    finally:
        try:
            pico.close(reboot=not a.no_reboot)
        finally:
            analyser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
