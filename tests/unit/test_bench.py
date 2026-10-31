"""Tests of the bench framework against simulated instruments (no hardware needed).

Run from the repo root:  python3 -m unittest discover -s tests/unit -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "bench"))

from benchlib import metrics, results, setups, spectrum  # noqa: E402
from benchlib.fakes import FakeAnalyser, FakePico, FakeWorld, HostChipPico  # noqa: E402
from benchlib.measure import MEASUREMENTS  # noqa: E402
from benchlib.rig import Rig  # noqa: E402
import run as bench_run  # noqa: E402

SETUP = {"id": "unit-test-setup", "output": "70cm", "description": "simulated",
         "chain": [{"kind": "filter", "name": "SAW"}, {"kind": "attenuator", "db": 10}]}


def fake_rig():
    world = FakeWorld()
    return Rig(SETUP, FakeAnalyser(world), FakePico(world), sleep=lambda s: None), world


class SetupTests(unittest.TestCase):
    def test_pad_is_the_loss_after_the_last_filter(self):
        s = {"id": "x", "output": "6m", "chain": [{"kind": "attenuator", "db": 3}, {"kind": "filter"},
                                                  {"kind": "attenuator", "db": 10}, {"kind": "cable", "db": 0.5}]}
        self.assertEqual(setups.pad_db(s), 10.5)
        self.assertEqual(setups.pad_db({"id": "x", "output": "6m", "chain": [{"kind": "filter"}]}), 0)

    def test_validation(self):
        with self.assertRaises(ValueError):
            setups.validate({"id": "x", "output": "4m", "chain": []})
        with self.assertRaises(ValueError):
            setups.validate({"id": "x", "output": "6m", "chain": [{"kind": "magic"}]})

    def test_shipped_setups_are_valid(self):
        for p in setups.SETUP_DIR.glob("*.json"):
            setups.load(p)
        self.assertIn("->", setups.describe(SETUP))


class SpectrumTests(unittest.TestCase):
    def test_extract_spurs_ignores_the_carrier_skirt(self):
        freqs = [i * 25e3 for i in range(401)]
        db = [-100.0] * 401
        db[200] = -30.0
        db[202] = -75.0            # 50 kHz from the carrier: inside the guard, ignored
        db[230] = -80.0            # 750 kHz away
        c, f, floor, spurs = spectrum.extract_spurs(freqs, db, 150e3)
        self.assertEqual(c, -30.0)
        self.assertEqual(len(spurs), 1)
        self.assertAlmostEqual(spurs[0][0], 750e3)
        self.assertAlmostEqual(spurs[0][1], -50.0)

    def test_rbw_not_narrower_than_step(self):
        self.assertEqual(spectrum.rbw_for_step(25e3), 30)
        self.assertEqual(spectrum.rbw_for_step(10e3), 10)
        self.assertEqual(spectrum.rbw_for_step(2.5e3), 3)


class MeasurementTests(unittest.TestCase):
    def run_one(self, name, **overrides):
        rig, world = fake_rig()
        params = MEASUREMENTS[name].defaults(rig)
        params.update(overrides)
        data = MEASUREMENTS[name].run(rig, params, lambda m: None)
        self.assertFalse(world.state["on"], "the output must be left off")
        return params, data

    def test_response_finds_the_passband(self):
        params, data = self.run_one("response")
        m = metrics.response(params, data)
        self.assertAlmostEqual(m["edge_lo_3"], 421 - 3 / 20, delta=0.3)      # fake skirt is 20 dB per MHz
        self.assertAlmostEqual(m["edge_hi_3"], 444 + 3 / 20, delta=0.3)
        self.assertAlmostEqual(m["bw3_mhz"], 23.3, delta=0.5)
        self.assertAlmostEqual(m["centre_mhz"], 432.5, delta=0.3)
        self.assertGreater(m["reject_low_db"], 40)
        self.assertGreater(m["reject_high_db"], 40)
        self.assertIn("1", m["other_orders"])
        self.assertAlmostEqual(m["other_orders"]["1"]["median_dbm"], -77.0, delta=1.5)

    def test_spur_map_sees_the_frequency_dependence(self):
        params, data = self.run_one("spur_map", step=1.0, n=1)
        m = metrics.spur_map(params, data)
        for drive in ("2", "8"):
            self.assertTrue(-58 < m[drive]["best_dbc"] < -51, m[drive]["best_dbc"])   # fake spurs are about -53 dBc up to 436 MHz
            self.assertGreater(m[drive]["worst_dbc"], m[drive]["best_dbc"] + 2)   # and get worse above it
            self.assertGreaterEqual(m[drive]["worst_fo_mhz"], 438)
        s = data["series"][0]
        self.assertEqual(len(s["trace_dbc"]), len(s["fo_mhz"]))
        self.assertEqual(len(s["trace_dbc"][0]), params["points"])
        # at 435 MHz the spurs are at +/-0.65 MHz, as the fake world puts them
        i = s["fo_mhz"].index(435.0)
        offsets = [abs(o) for o, d in s["spurs"][i]]
        self.assertTrue(any(abs(o - 0.65) < 0.05 for o in offsets), offsets)

    def test_wide_spectrum_finds_the_fundamental_and_fourth_harmonic(self):
        params, data = self.run_one("spectrum_wide")
        m = metrics.spectrum_wide(params, data)["configs"][0]
        found = {o["order"]: o for o in m["out_of_band"]}
        self.assertIn(1, found)
        self.assertIn(4, found)
        self.assertAlmostEqual(found[1]["freq_mhz"], 145.0, delta=0.2)
        self.assertAlmostEqual(found[4]["freq_mhz"], 580.0, delta=0.2)
        self.assertLess(found[4]["dbc"], found[1]["dbc"])

    def test_drive_levels_are_reported_per_drive(self):
        params, data = self.run_one("drive_levels")
        m = metrics.drive_levels(params, data)
        self.assertEqual(m["wanted_order"], "3")
        self.assertAlmostEqual(m["wanted_dbm_by_drive"]["8"], -29.2, delta=0.5)
        self.assertFalse(m["monotonic"])        # the fake (like the real 3rd harmonic) is not monotonic in drive

    def test_close_in_spectrum(self):
        params, data = self.run_one("spectrum_close", n=1)
        m = metrics.spectrum_close(params, data)
        self.assertEqual(len(m["rows"]), len(params["configs"]))
        self.assertTrue(all(r["worst_dbc"] is not None for r in m["rows"]))


OUTPUTS = {
    # output: (setup, simulated world). The world mimics each output's chain: a low-pass for 6m, a band-pass for 2m, the SAW for 70cm.
    "6m": ({"id": "t6", "output": "6m", "chain": [{"kind": "filter"}, {"kind": "attenuator", "db": 10}]}, dict(mult=1, passband_mhz=(0.0, 64.0))),
    "2m": ({"id": "t2", "output": "2m", "chain": [{"kind": "filter"}, {"kind": "attenuator", "db": 10}]}, dict(mult=1, passband_mhz=(143.0, 147.0))),
    "70cm": ({"id": "t70", "output": "70cm", "chain": [{"kind": "filter"}, {"kind": "attenuator", "db": 10}]}, dict(mult=3)),
}


class AllOutputsTests(unittest.TestCase):
    def test_every_output_runs_every_measurement_through_the_real_driver(self):
        sys.path.insert(0, str(ROOT))
        import config as fw
        quick = {n: {"n": 1} for n in ("spur_map", "spectrum_close", "spectrum_wide", "response", "drive_levels")}
        for out, (setup, world_kw) in OUTPUTS.items():
            with self.subTest(output=out):
                world = FakeWorld(**world_kw)
                pico = HostChipPico(world)
                with tempfile.TemporaryDirectory() as d:
                    run, path = bench_run.execute(setup, FakeAnalyser(world), pico, list(MEASUREMENTS), quick, results_dir=d,
                                                  log=lambda m: None, sleep=lambda s: None)
                    self.assertEqual(run["status"], "complete")
                    self.assertEqual(sorted(run["tests"]), sorted(MEASUREMENTS))
                    spec = fw.BANDS[out]
                    # the rig must command the channel and PLL the firmware uses for this band, and the carrier = wanted / harmonic
                    self.assertEqual({(c[0], c[1]) for c in pico.calls}, {(spec["ch"], spec["pll"])})
                    mid = pico.calls[0][2] * spec["mult"] / 1e6
                    self.assertTrue(spec["lo"] / 1e6 - 1 <= mid <= spec["hi"] / 1e6 + 1, mid)
                    m = metrics.compute(results.load(path))
                    self.assertFalse([k for k, v in m.items() if "error" in v], m)
                    self.assertTrue(metrics.summary(run, m))
                    self.assertFalse(world.state["on"])

    def test_the_driver_really_cannot_make_frequencies_between_100_and_112_5_MHz(self):
        pico = HostChipPico(FakeWorld(mult=1))
        pico.set_output(0, 0, 100_000_000, 2)           # 800 MHz VCO / 8: fine
        pico.set_output(0, 0, 113_000_000, 2)           # owner of the PLL: fine
        with self.assertRaises(ValueError):
            HostChipPico(FakeWorld(mult=1)).set_output(0, 0, 105_000_000, 2)

    def test_response_plans_avoid_that_gap_for_6m_and_2m(self):
        from benchlib.measure import response
        for out in ("6m", "2m"):
            fos = response.expand(response.SEGMENTS[out])
            self.assertFalse([f for f in fos if 100 < f < 113], out)

    def test_low_pass_response_reports_its_cutoff(self):
        world = FakeWorld(mult=1, passband_mhz=(0.0, 64.0))
        rig = Rig(OUTPUTS["6m"][0], FakeAnalyser(world), HostChipPico(world), sleep=lambda s: None)
        p = MEASUREMENTS["response"].defaults(rig)
        p["n"] = 1
        m = metrics.response(p, MEASUREMENTS["response"].run(rig, p, lambda s: None))
        self.assertAlmostEqual(m["lowpass_cutoff_mhz"], 64.15, delta=0.7)
        self.assertIsNone(m["bw3_mhz"])
        self.assertLess(m["ripple_db"], 0.5)
        self.assertGreater(m["reject_high_db"], 40)

    def test_harmonic_labels_use_an_absolute_tolerance(self):
        freqs = [round(5 + 0.1 * i, 1) for i in range(7851)]
        dbm = [-100.0] * len(freqs)

        def put(f, level):
            dbm[freqs.index(round(f, 1))] = level
        put(51.0, -24.0)        # wanted (6m)
        put(102.0, -75.0)       # 2nd harmonic
        put(459.0, -80.0)       # 9th harmonic
        put(120.0, -80.0)       # NOT a harmonic of 51 MHz
        put(450.0, -80.0)       # 9 MHz from the 9th: not a harmonic either
        data = {"configs": [{"fo_mhz": 51.0, "drive": 2, "wanted_hz": 51e6, "carrier_hz": 51_000_000, "freq_mhz": freqs, "dbm": dbm}]}
        oob = {o["freq_mhz"]: o["order"] for o in metrics.spectrum_wide({}, data)["configs"][0]["out_of_band"]}
        self.assertEqual(oob[102.0], 2)
        self.assertEqual(oob[459.0], 9)
        self.assertIsNone(oob[120.0])
        self.assertIsNone(oob[450.0])


class ProtocolVersionTests(unittest.TestCase):
    def test_every_measurement_has_a_version_and_runs_record_it(self):
        for name, m in MEASUREMENTS.items():
            self.assertIsInstance(m.VERSION, int, name)
        world = FakeWorld()
        with tempfile.TemporaryDirectory() as d:
            run, path = bench_run.execute(SETUP, FakeAnalyser(world), FakePico(world), ["drive_levels"], results_dir=d,
                                          log=lambda m: None, sleep=lambda s: None)
        self.assertEqual(run["tests"]["drive_levels"]["version"], MEASUREMENTS["drive_levels"].VERSION)


class VerifyTests(unittest.TestCase):
    def test_real_and_analyser_made_signals_are_told_apart(self):
        world = FakeWorld()                                   # carrier ~145 MHz: real lines at 145 (1x) and 580 (4x)
        world.analyser_lines = [(725e6, -62.0)]               # a spur the analyser itself makes
        rig = Rig(SETUP, FakeAnalyser(world), FakePico(world), sleep=lambda s: None)
        p = MEASUREMENTS["spectrum_wide"].defaults(rig)
        p.update(configs=[[435.0, 8]], n=1)
        data = MEASUREMENTS["spectrum_wide"].run(rig, p, lambda m: None)
        self.assertEqual(rig.analyser.attenuation, 0, "attenuation must be put back")
        oob = {round(o["freq_mhz"]): o for o in metrics.spectrum_wide(p, data)["configs"][0]["out_of_band"]}
        self.assertIs(oob[145]["real"], True)
        self.assertIs(oob[580]["real"], True)
        self.assertIs(oob[725]["real"], False)
        self.assertEqual(oob[725]["order"], 5)

    def test_verification_can_be_switched_off(self):
        rig, world = fake_rig()
        p = MEASUREMENTS["spectrum_wide"].defaults(rig)
        p.update(configs=[[435.0, 8]], n=1, verify_top=0)
        data = MEASUREMENTS["spectrum_wide"].run(rig, p, lambda m: None)
        self.assertEqual(data["configs"][0]["verify"], [])
        self.assertTrue(all(o["real"] is None for o in metrics.spectrum_wide(p, data)["configs"][0]["out_of_band"]))


class HeadroomTests(unittest.TestCase):
    def run_with_gain(self, gain, **kw):
        world = FakeWorld(gain_db=gain)
        with tempfile.TemporaryDirectory() as d:
            try:
                run, path = bench_run.execute(SETUP, FakeAnalyser(world), FakePico(world), ["drive_levels"], results_dir=d,
                                              log=lambda m: None, sleep=lambda s: None, **kw)
                return run, len(list(Path(d).glob("*/*.json"))), world
            except bench_run.OverloadError as e:
                return e, len(list(Path(d).glob("*/*.json"))), world

    def test_refuses_when_the_analyser_would_be_overloaded(self):
        err, files, world = self.run_with_gain(10.0)          # 8 mA would be about -19 dBm at the analyser
        self.assertIsInstance(err, bench_run.OverloadError)
        self.assertIn("-19", str(err))
        self.assertEqual(files, 0, "a refused run must not leave a result file")
        self.assertFalse(world.state["on"])

    def test_force_overrides_and_records_it(self):
        run, files, world = self.run_with_gain(10.0, force=True)
        self.assertEqual(run["status"], "complete")
        self.assertEqual(files, 1)
        self.assertGreater(run["environment"]["headroom"]["level_dbm"], run["environment"]["headroom"]["limit_dbm"])
        self.assertGreater(run["environment"]["max_level_dbm"], -25)

    def test_normal_level_passes(self):
        run, files, world = self.run_with_gain(0.0)
        self.assertEqual(run["status"], "complete")
        self.assertLess(run["environment"]["headroom"]["level_dbm"], -25)


class AnalyserDriverTests(unittest.TestCase):
    def _sa(self, replies):
        from benchlib.tinysa import TinySA
        sa = object.__new__(TinySA)
        calls = []
        sa.command = lambda text, timeout=10.0: (calls.append(text), replies.pop(0))[1]
        return sa, calls

    @staticmethod
    def _text(n):
        return "\n".join("%d %.1f" % (430_000_000 + i * 1000, -90.0) for i in range(n))

    def test_firmware_number_formatting_quirk(self):
        from benchlib.tinysa import to_float
        self.assertEqual(to_float("-:.000000e+01"), -100.0)       # real reply: the formatter rounded -99.99999 up to "10"
        self.assertAlmostEqual(to_float("-8.253125e+01"), -82.53125)
        self.assertEqual(to_float("435000000"), 435e6)
        sa, calls = self._sa(["430000003 -8.2e+01 0.000000000 \n430025003 -:.000000e+01 0.000000000 \n430050003 -1.02e+02 0.0"])
        pts = sa.scan(430_000_003, 430_050_003, 3)
        self.assertEqual([round(p[1], 1) for p in pts], [-82.0, -100.0, -102.0])

    def test_a_short_reply_is_retried(self):
        sa, calls = self._sa([self._text(397), self._text(401)])
        msgs = []
        pts = sa.scan(430_000_000, 434_000_000, 401, warn=msgs.append)
        self.assertEqual(len(pts), 401)
        self.assertEqual(len(calls), 2)
        self.assertIn("397 of 401", msgs[0])

    def test_gives_up_after_three_short_replies(self):
        from benchlib.tinysa import TinySAError
        sa, calls = self._sa([self._text(397)] * 3)
        with self.assertRaises(TinySAError):
            sa.scan(430_000_000, 434_000_000, 401, warn=lambda m: None)
        self.assertEqual(len(calls), 3)


class RunnerTests(unittest.TestCase):
    def test_execute_saves_a_complete_run_and_tidies_up(self):
        world = FakeWorld()
        analyser, pico = FakeAnalyser(world), FakePico(world)
        with tempfile.TemporaryDirectory() as d:
            run, path = bench_run.execute(SETUP, analyser, pico, ["drive_levels", "spur_map"],
                                          {"spur_map": {"step": 2.0, "n": 1}}, results_dir=d, note="unit test",
                                          log=lambda m: None, sleep=lambda s: None)
            self.assertTrue(Path(path).exists())
            stored = results.load(path)
            self.assertEqual(stored["setup"]["id"], "unit-test-setup")
            self.assertEqual(stored["note"], "unit test")
            self.assertEqual(sorted(stored["tests"]), ["drive_levels", "spur_map"])
            self.assertEqual(stored["status"], "complete")
            self.assertIn("reference_start", stored["environment"])
            self.assertLess(abs(stored["environment"]["drift_db"]), 0.5)
            self.assertEqual(stored["environment"]["pico"]["correction_ppb"], 151300)
            self.assertFalse(world.state["on"])
            self.assertEqual(analyser.rbw_khz, 100.0)           # the analyser's own settings were restored
            summary = metrics.summary(stored)
            self.assertIn("spur_map.8mA.worst_dbc", summary)
            self.assertIn("drive.8mA.wanted_dbm", summary)
            listed = results.list_runs(d)
            self.assertEqual([h["run_id"] for h in listed], [stored["run_id"]])
            self.assertEqual(listed[0]["tests"], ["drive_levels", "spur_map"])

    def test_a_failing_measurement_still_switches_the_output_off(self):
        world = FakeWorld()
        analyser, pico = FakeAnalyser(world), FakePico(world)

        def boom(*a, **k):
            raise RuntimeError("analyser went away")
        analyser.scan = boom
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                bench_run.execute(SETUP, analyser, pico, ["drive_levels"], results_dir=d, log=lambda m: None, sleep=lambda s: None)
            self.assertFalse(world.state["on"])
            files = list(Path(d).glob("*/*.json"))
            self.assertEqual(len(files), 1)                               # partial run still saved
            self.assertEqual(results.load(files[0])["status"], "failed")
            self.assertIn("analyser went away", results.load(files[0])["error"])

    def test_parse_overrides(self):
        o = bench_run.parse_overrides(["spur_map.step=0.5", "spur_map.drives=[2]", "response.note=hello"])
        self.assertEqual(o, {"spur_map": {"step": 0.5, "drives": [2]}, "response": {"note": "hello"}})


if __name__ == "__main__":
    unittest.main()
