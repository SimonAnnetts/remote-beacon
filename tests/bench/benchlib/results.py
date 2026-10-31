"""Storing and listing bench runs (tests-results/<output>/<run id>.json)."""
import json
import re
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO / "tests-results"
SCHEMA = 1


def new_run_id(setup_id, when=None):
    return "%s__%s" % (time.strftime("%Y-%m-%dT%H-%M-%S", when or time.localtime()), re.sub(r"[^A-Za-z0-9._-]", "-", setup_id))


def path_for(run, results_dir=RESULTS_DIR):
    return Path(results_dir) / run["output"] / (run["run_id"] + ".json")


def save(run, results_dir=RESULTS_DIR):
    p = path_for(run, results_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(run, separators=(",", ":")))
    tmp.replace(p)
    return p


def load(path):
    return json.loads(Path(path).read_text())


def list_runs(results_dir=RESULTS_DIR):
    """Header information for every stored run, newest first."""
    out = []
    for p in Path(results_dir).glob("*/*.json"):
        try:
            r = load(p)
        except (OSError, ValueError):
            continue
        out.append({"run_id": r["run_id"], "output": r["output"], "started": r.get("started"),
                    "setup_id": r["setup"]["id"], "description": r["setup"].get("description", ""),
                    "tests": sorted(r.get("tests", {})), "path": str(p), "legacy": r.get("legacy", False),
                    "status": r.get("status", "complete")})
    out.sort(key=lambda h: h["started"] or "", reverse=True)
    return out


def git_info():
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True, timeout=5).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", ":!tests-results"], cwd=REPO, capture_output=True, text=True, timeout=5).stdout.strip())
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None}
