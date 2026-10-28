"""Beacon configuration: band definitions, defaults, validation, persistence."""
import json

CONFIG_FILE = "config.json"

# Output channel and PLL are fixed by the hardware (see PLAN.md). mult is the
# harmonic used: 70cm is the third harmonic of a carrier on CLK2. lo/hi are the
# UK allocations in Hz of the transmitted frequency.
BANDS = {
    "6m": {"ch": 0, "pll": 0, "mult": 1, "lo": 50000000, "hi": 52000000},
    "2m": {"ch": 1, "pll": 0, "mult": 1, "lo": 144000000, "hi": 146000000},
    "70cm": {"ch": 2, "pll": 1, "mult": 3, "lo": 430000000, "hi": 440000000},
}
BAND_ORDER = ("6m", "2m", "70cm")

MODES = ("morse", "carrier")


def defaults():
    return {
        "callsign": "",
        "locator": "",
        # Template for the Morse ID.
        "message": "VVV DE {call} {loc}",
        "wpm": 12,
        # Measured crystal error in ppb; 151300 is this development board.
        "correction_ppb": 151300,
        # Seconds between transmissions of consecutive bands, and between cycles.
        "gap_s": 2,
        "interval_s": 30,
        "bands": {
            "6m": {"enabled": False, "mode": "morse", "freq": 50050000, "carrier_s": 5},
            "2m": {"enabled": False, "mode": "morse", "freq": 144450000, "carrier_s": 5},
            "70cm": {"enabled": False, "mode": "morse", "freq": 432450000, "carrier_s": 5},
        },
    }


def validate(cfg):
    """Raise ValueError if cfg could not be transmitted safely."""
    call = cfg.get("callsign", "")
    if not call or not all(c.isalpha() or c.isdigit() or c == "/" for c in call):
        raise ValueError("a callsign is required (letters, digits and / only)")
    if not 5 <= cfg["wpm"] <= 30:
        raise ValueError("wpm must be 5-30")
    if cfg["gap_s"] < 0 or cfg["interval_s"] < 0:
        raise ValueError("gap_s and interval_s must not be negative")
    for name, spec in BANDS.items():
        band = cfg["bands"][name]
        if band["mode"] not in MODES:
            raise ValueError("%s: mode must be one of %s" % (name, MODES))
        if not spec["lo"] <= band["freq"] <= spec["hi"]:
            raise ValueError("%s: %d Hz is outside %d-%d Hz"
                             % (name, band["freq"], spec["lo"], spec["hi"]))
        if not 0 < band["carrier_s"] <= 60:
            raise ValueError("%s: carrier_s must be 1-60" % name)


def message(cfg):
    return cfg["message"].format(call=cfg["callsign"], loc=cfg["locator"])


def load(path=CONFIG_FILE):
    """Defaults overlaid with the saved file, if any. Not validated."""
    cfg = defaults()
    try:
        with open(path) as f:
            saved = json.load(f)
    except OSError:
        return cfg
    bands = saved.pop("bands", {})
    cfg.update(saved)
    for name, values in bands.items():
        if name in cfg["bands"]:
            cfg["bands"][name].update(values)
    return cfg


def save(cfg, path=CONFIG_FILE):
    validate(cfg)
    with open(path, "w") as f:
        json.dump(cfg, f)
