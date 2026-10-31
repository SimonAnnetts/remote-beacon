"""The bench web UI server: API, static files, and its refusal to serve anything outside webui/."""
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "bench"))

import run as bench_run  # noqa: E402
import serve  # noqa: E402
from benchlib.fakes import FakeAnalyser, FakePico, FakeWorld  # noqa: E402

SETUP = {"id": "server-test", "output": "70cm", "description": "simulated",
         "chain": [{"kind": "filter", "name": "SAW", "part": "unknown"}, {"kind": "attenuator", "db": 10}]}


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        world = FakeWorld()
        run, cls.path = bench_run.execute(SETUP, FakeAnalyser(world), FakePico(world), ["drive_levels", "spur_map"],
                                          {"spur_map": {"step": 2.0, "n": 1}}, results_dir=cls.dir, log=lambda m: None, sleep=lambda s: None)
        cls.run_id = run["run_id"]
        (Path(cls.dir) / "70cm" / "corrupt.json").write_text("{not json")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), serve.make_handler(serve.Store(cls.dir)))
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        shutil.rmtree(cls.dir)

    def get(self, path, data=None):
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base + path, data=data), timeout=10) as r:
                return r.status, r.read(), r.headers.get("Content-Type")
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers.get("Content-Type")

    def test_listing_skips_corrupt_files_and_carries_summary(self):
        code, body, ctype = self.get("/api/runs")
        runs = json.loads(body)
        self.assertEqual(code, 200)
        self.assertEqual([r["run_id"] for r in runs], [self.run_id])
        self.assertEqual(runs[0]["status"], "complete")
        self.assertEqual(runs[0]["tests"], ["drive_levels", "spur_map"])
        self.assertIn("spur_map.8mA.worst_dbc", runs[0]["summary"])
        self.assertIn("SAW", runs[0]["chain"])

    def test_run_detail_has_data_and_metrics(self):
        code, body, _ = self.get("/api/runs/" + self.run_id)
        d = json.loads(body)
        self.assertEqual(code, 200)
        self.assertEqual(d["run"]["setup"]["id"], "server-test")
        self.assertIn("spur_map", d["metrics"])
        self.assertIn("worst_by_fo", d["metrics"]["spur_map"]["8"])
        self.assertEqual(self.get("/api/runs/nope")[0], 404)

    def test_static_files(self):
        code, body, ctype = self.get("/")
        self.assertEqual(code, 200)
        self.assertIn(b"Bench results", body)
        self.assertIn("text/html", ctype)
        self.assertEqual(self.get("/app.js")[0], 200)
        self.assertEqual(self.get("/charts.js")[0], 200)
        self.assertEqual(self.get("/style.css")[0], 200)

    def test_nothing_outside_webui_is_served(self):
        for path in ("/../serve.py", "/..%2Fserve.py", "/../../../config.py", "/%2e%2e/serve.py", "/nonexistent.js"):
            self.assertEqual(self.get(path)[0], 404, path)

    def test_read_only(self):
        self.assertEqual(self.get("/api/runs", data=b"{}")[0], 405)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class WebUiSyntax(unittest.TestCase):
    def test_javascript_parses(self):
        for name in ("app.js", "charts.js"):
            r = subprocess.run(["node", "--check", str(ROOT / "tests" / "bench" / "webui" / name)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
