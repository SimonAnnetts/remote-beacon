"""Descriptions of the signal chain between an Si5351 output and the analyser."""
import json
from pathlib import Path

SETUP_DIR = Path(__file__).resolve().parent.parent / "setups"
LOSSY = ("attenuator", "cable")


def load(name_or_path):
    p = Path(name_or_path)
    if not p.exists():
        p = SETUP_DIR / (str(name_or_path) + ".json")
    setup = json.loads(p.read_text())
    validate(setup)
    return setup


def list_setups():
    out = []
    for p in sorted(SETUP_DIR.glob("*.json")):
        s = json.loads(p.read_text())
        out.append({"id": s.get("id", p.stem), "output": s.get("output"), "description": s.get("description", "")})
    return out


def validate(s):
    for key in ("id", "output", "chain"):
        if key not in s:
            raise ValueError("setup is missing %r" % key)
    if s["output"] not in ("6m", "2m", "70cm"):
        raise ValueError("setup output must be 6m, 2m or 70cm")
    for item in s["chain"]:
        if item.get("kind") not in ("filter", "amplifier", "attenuator", "cable", "other"):
            raise ValueError("chain item has an unknown kind: %r" % (item,))


def pad_db(setup):
    """Loss between the last filter/amplifier and the analyser, to add back to readings."""
    total = 0.0
    for item in reversed(setup["chain"]):
        if item["kind"] in LOSSY:
            total += float(item.get("db", item.get("loss_db", 0)))
        else:
            break
    return total


def describe(setup):
    parts = ["Si5351 " + setup["output"]]
    for item in setup["chain"]:
        label = item.get("name") or item["kind"]
        if item["kind"] in LOSSY and "db" in item:
            label += " %g dB" % item["db"]
        parts.append(label)
    parts.append("analyser")
    return " -> ".join(parts)
