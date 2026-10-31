#!/usr/bin/env python3
"""Local web UI for the bench results, served from this PC (never from the Pico).

  python3 tests/bench/serve.py            # http://127.0.0.1:3333
  python3 tests/bench/serve.py --port 3333 --results-dir tests-results

Read-only: it lists the runs stored in tests-results/, computes their metrics and draws them. Standard library only.
"""
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchlib import metrics, results, setups  # noqa: E402

WEB = Path(__file__).resolve().parent / "webui"
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".svg": "image/svg+xml", ".json": "application/json"}


class Store:
    """Runs on disk, with parsed results and metrics cached until a file changes."""

    def __init__(self, results_dir):
        self.dir = Path(results_dir)
        self._cache = {}

    def _entry(self, path):
        mtime = path.stat().st_mtime
        hit = self._cache.get(path)
        if hit and hit["mtime"] == mtime:
            return hit
        run = results.load(path)
        m = metrics.compute(run)
        hit = {"mtime": mtime, "run": run, "metrics": m, "summary": metrics.summary(run, m)}
        self._cache[path] = hit
        return hit

    def paths(self):
        return sorted(self.dir.glob("*/*.json"))

    def listing(self):
        out = []
        for p in self.paths():
            try:
                e = self._entry(p)
            except (OSError, ValueError):
                continue
            r = e["run"]
            out.append({"run_id": r["run_id"], "output": r["output"], "started": r.get("started"), "finished": r.get("finished"),
                        "setup_id": r["setup"]["id"], "chain": setups.describe(r["setup"]), "tests": sorted(r.get("tests", {})),
                        "status": r.get("status", "complete"), "legacy": r.get("legacy", False), "note": r.get("note", ""),
                        "summary": e["summary"]})
        out.sort(key=lambda h: h["started"] or "", reverse=True)
        return out

    def get(self, run_id):
        for p in self.paths():
            if p.stem == run_id:
                e = self._entry(p)
                return {"run": e["run"], "metrics": e["metrics"], "summary": e["summary"], "chain": setups.describe(e["run"]["setup"])}
        return None


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, separators=(",", ":")).encode(), "application/json")

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            try:
                if path == "/api/runs":
                    return self._json(store.listing())
                if path.startswith("/api/runs/"):
                    got = store.get(path[len("/api/runs/"):])
                    return self._json(got) if got else self._json({"error": "no such run"}, 404)
                if path == "/api/setups":
                    return self._json(setups.list_setups())
            except (OSError, ValueError, KeyError) as e:
                return self._json({"error": str(e)}, 500)
            name = "index.html" if path in ("/", "") else path.lstrip("/")
            target = (WEB / name).resolve()
            if WEB.resolve() not in target.parents or not target.is_file():
                return self._send(404, b"not found", "text/plain")
            self._send(200, target.read_bytes(), TYPES.get(target.suffix, "application/octet-stream"))

        def do_POST(self):
            self._send(405, b"read only", "text/plain")

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=3333)
    ap.add_argument("--host", default="127.0.0.1", help="keep this as 127.0.0.1 unless you mean to share the results on your network")
    ap.add_argument("--results-dir", default=str(results.RESULTS_DIR))
    a = ap.parse_args()
    server = ThreadingHTTPServer((a.host, a.port), make_handler(Store(a.results_dir)))
    print("bench results at http://%s:%d  (Ctrl+C to stop)" % (a.host, a.port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
