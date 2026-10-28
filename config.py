"""Beacon configuration: band definitions, defaults, validation, persistence."""
import json
import os

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

MODES = ("morse", "carrier", "duty", "fsk")

# Settings that may be changed through the web API.
TOP_KEYS = ("callsign", "locator", "message", "wpm", "gap_s", "interval_s",
            "correction_ppb", "tx_enabled", "wifi_ssid", "wifi_password",
            "web_password", "ntp_host")
BAND_KEYS = ("enabled", "mode", "freq", "carrier_s", "period_ms", "duty_pct",
             "shift_hz")
SECRET_KEYS = ("wifi_password", "web_password")


def _band(freq):
    return {"enabled": False, "mode": "morse", "freq": freq, "carrier_s": 5,
            "period_ms": 1000, "duty_pct": 50, "shift_hz": 200}


def defaults():
    return {
        "callsign": "GW3ACE",
        "locator": "IO82gh",
        # Template for the Morse ID.
        "message": "VVV DE {call} {loc}",
        "wpm": 12,
        # Master transmit switch. Off until deliberately enabled.
        "tx_enabled": False,
        # Measured crystal error in ppb; 151300 is this development board.
        "correction_ppb": 151300,
        # Seconds between transmissions of consecutive bands, and between cycles.
        "gap_s": 2,
        "interval_s": 30,
        "wifi_ssid": "",
        "wifi_password": "",
        "ntp_host": "pool.ntp.org",
        # Required for the web interface and used as the setup access point's
        # WPA2 key, so at least 8 characters.
        "web_password": "",
        # Per band: carrier_s is the length of carrier and duty-cycle
        # transmissions; duty mode uses period_ms/duty_pct; fsk mode sends the
        # Morse message with key-up shifted shift_hz above the band frequency.
        "bands": {
            "6m": _band(50050000),
            "2m": _band(144450000),
            "70cm": _band(432450000),
        },
    }


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def message(cfg):
    return cfg["message"].format(call=cfg["callsign"], loc=cfg["locator"])


def validate(cfg):
    """Raise ValueError if cfg is invalid. A callsign is only required once
    transmitting is enabled, so a half-finished setup can still be saved."""
    call = cfg["callsign"]
    if not isinstance(call, str) or len(call) > 12 or not all(
            c.isalpha() or c.isdigit() or c == "/" for c in call):
        raise ValueError("callsign: letters, digits and / only")
    loc = cfg["locator"]
    if not isinstance(loc, str) or len(loc) > 8 or not all(
            c.isalpha() or c.isdigit() for c in loc):
        raise ValueError("locator: letters and digits only")
    if not isinstance(cfg["tx_enabled"], bool):
        raise ValueError("tx_enabled must be true or false")
    if cfg["tx_enabled"] and not call:
        raise ValueError("a callsign is required to enable transmitting")
    try:
        text = message(cfg)
    except (KeyError, IndexError, ValueError, AttributeError):
        raise ValueError("message: only {call} and {loc} may be used")
    if len(text) > 80:
        raise ValueError("message is too long (80 characters maximum)")
    for key, lo, hi in (("wpm", 5, 30), ("gap_s", 0, 3600), ("interval_s", 0, 86400),
                        ("correction_ppb", -1000000, 1000000)):
        if not _is_int(cfg[key]) or not lo <= cfg[key] <= hi:
            raise ValueError("%s must be a whole number %d to %d" % (key, lo, hi))
    ssid, wpass, apass = cfg["wifi_ssid"], cfg["wifi_password"], cfg["web_password"]
    if not all(isinstance(v, str) for v in (ssid, wpass, apass)):
        raise ValueError("wifi and web settings must be text")
    ntp = cfg["ntp_host"]
    if not isinstance(ntp, str) or not 1 <= len(ntp) <= 64 or " " in ntp:
        raise ValueError("ntp_host must be a host name or address")
    if len(ssid) > 32:
        raise ValueError("wifi_ssid is too long")
    if wpass and not 8 <= len(wpass) <= 63:
        raise ValueError("wifi_password must be 8-63 characters")
    if apass and not 8 <= len(apass) <= 63:
        raise ValueError("web_password must be 8-63 characters")
    for name, spec in BANDS.items():
        band = cfg["bands"][name]
        if not isinstance(band["enabled"], bool):
            raise ValueError("%s: enabled must be true or false" % name)
        if band["mode"] not in MODES:
            raise ValueError("%s: mode must be one of %s" % (name, MODES))
        if not _is_int(band["freq"]) or not spec["lo"] <= band["freq"] <= spec["hi"]:
            raise ValueError("%s: frequency must be %d-%d Hz"
                             % (name, spec["lo"], spec["hi"]))
        for key, lo, hi in (("carrier_s", 1, 60), ("period_ms", 50, 60000),
                            ("duty_pct", 1, 99), ("shift_hz", 10, 5000)):
            if not _is_int(band[key]) or not lo <= band[key] <= hi:
                raise ValueError("%s: %s must be %d-%d" % (name, key, lo, hi))
        if band["mode"] == "fsk" and band["freq"] + band["shift_hz"] > spec["hi"]:
            raise ValueError("%s: frequency plus shift is above the band" % name)


def copy(cfg):
    return json.loads(json.dumps(cfg))


def merge(cfg, update):
    """Return a validated copy of cfg with the web-settable keys of update
    applied. Unknown keys are rejected."""
    new = copy(cfg)
    for key, value in update.items():
        if key == "bands":
            for name, band_update in value.items():
                if name not in new["bands"]:
                    raise ValueError("unknown band " + name)
                for bkey, bvalue in band_update.items():
                    if bkey not in BAND_KEYS:
                        raise ValueError("unknown band setting " + bkey)
                    new["bands"][name][bkey] = bvalue
        elif key in TOP_KEYS:
            new[key] = value
        else:
            raise ValueError("unknown setting " + key)
    validate(new)
    return new


def public(cfg):
    """cfg without secrets, for sending to the web interface."""
    out = copy(cfg)
    for key in SECRET_KEYS:
        out[key + "_set"] = bool(out.pop(key))
    return out


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
    """Validate and write cfg, replacing the old file only once complete."""
    validate(cfg)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f)
    os.rename(tmp, path)
