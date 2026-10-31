"""Metrics computed from stored raw data (never stored themselves, so analysis can improve retroactively)."""
from benchlib import spectrum

EDGE_DROPS = (3, 10, 20, 30, 40)


def _cross(fs, ls, start, step, level):
    """Interpolated frequency where levels first fall below `level` walking from index start in direction step."""
    i = start
    while 0 <= i + step < len(ls):
        a, b = ls[i], ls[i + step]
        if b < level <= a:
            return fs[i] + (level - a) * (fs[i + step] - fs[i]) / (b - a)
        i += step
    return None


def response(params, d):
    k = str(params["wanted_order"])
    pts = sorted((f, l) for f, l in zip(d["fo_mhz"], d["orders"][k]["dbm"]) if l is not None)
    if len(pts) < 5:
        return {}
    fs, ls = [p[0] for p in pts], [p[1] for p in pts]
    peak = max(ls)
    ref = spectrum.median([l for l in ls if l >= peak - 3])
    imax = ls.index(peak)
    m = {"passband_dbm": round(ref, 2), "peak_dbm": round(peak, 2)}
    lo = hi = None
    for drop in EDGE_DROPS:
        a = _cross(fs, ls, imax, -1, ref - drop)
        b = _cross(fs, ls, imax, +1, ref - drop)
        m["edge_lo_%d" % drop] = None if a is None else round(a, 3)
        m["edge_hi_%d" % drop] = None if b is None else round(b, 3)
        if drop == 3:
            lo, hi = a, b
    m["bw3_mhz"] = round(hi - lo, 3) if lo is not None and hi is not None else None
    m["centre_mhz"] = round((hi + lo) / 2, 3) if lo is not None and hi is not None else None
    if lo is not None and hi is not None:
        inner = [l for f, l in pts if lo + 0.1 * (hi - lo) <= f <= hi - 0.1 * (hi - lo)]
        m["ripple_db"] = round(max(inner) - min(inner), 2) if inner else None
    if lo is None and hi is not None:       # a low-pass: no lower edge, so report the cutoff and the ripple below it
        m["lowpass_cutoff_mhz"] = round(hi, 3)
        flat = [l for f, l in pts if f <= 0.9 * hi]
        m["ripple_db"] = round(max(flat) - min(flat), 2) if flat else None
    margin = 5.0
    below = [l for f, l in pts if lo is not None and f <= lo - margin]
    above = [l for f, l in pts if hi is not None and f >= hi + margin]
    m["reject_low_db"] = round(ref - max(below), 1) if below else None
    m["reject_high_db"] = round(ref - max(above), 1) if above else None
    others = {}
    wanted = dict(zip(d["fo_mhz"], d["orders"][k]["dbm"]))
    for ko, series in d["orders"].items():
        if ko == k:
            continue
        pairs = [(f, l - wanted[f]) for f, l in zip(d["fo_mhz"], series["dbm"]) if l is not None and wanted.get(f) is not None]
        inband = [dbc for f, dbc in pairs if lo is None or hi is None or lo <= f <= hi]
        vals = [l for l in series["dbm"] if l is not None]
        if vals:
            others[ko] = {"median_dbm": round(spectrum.median(vals), 1), "max_dbm": round(max(vals), 1),
                          "worst_dbc_in_passband": round(max(inband), 1) if inband else None}
    m["other_orders"] = others
    return m


def _worst(spurs, floor_dbc):
    return spurs[0][1] if spurs else floor_dbc


def spur_map(params, d):
    out = {}
    for s in d["series"]:
        worst = []
        for sp, c, fl in zip(s["spurs"], s["carrier_dbm"], s["floor_dbm"]):
            worst.append(_worst(sp, fl + 8.0 - c))      # if nothing is above the floor, bound by the detection limit
        fo = s["fo_mhz"]
        order = sorted(range(len(worst)), key=lambda i: worst[i])
        out[str(s["drive"])] = {
            "worst_dbc": round(max(worst), 1), "worst_fo_mhz": fo[worst.index(max(worst))],
            "best_dbc": round(min(worst), 1), "best_fo_mhz": fo[order[0]],
            "median_dbc": round(spectrum.median(worst), 1),
            "n_points": len(fo), "n_better_than_50": sum(1 for w in worst if w <= -50),
            "worst_by_fo": [round(w, 1) for w in worst]}
    return out


def spectrum_close(params, d):
    rows = []
    for c in d["configs"]:
        rows.append({"fo_mhz": c["fo_mhz"], "drive": c["drive"], "carrier_dbm": c["carrier_dbm"],
                     "worst_dbc": c["spurs"][0][1] if c["spurs"] else None,
                     "worst_offset_mhz": c["spurs"][0][0] if c["spurs"] else None})
    return {"rows": rows}


def spectrum_wide(params, d):
    out = []
    for c in d["configs"]:
        if "peaks" in c:                 # imported data that kept only the peak list, not the whole trace
            peaks, floor = [tuple(p) for p in c["peaks"]], c.get("floor_dbm", -100.0)
        else:
            peaks, floor = spectrum.find_peaks(c["freq_mhz"], c["dbm"], 12.0)
        wanted_mhz = c["wanted_hz"] / 1e6
        carrier_mhz = c["carrier_hz"] / 1e6
        near = [p for p in peaks if abs(p[0] - wanted_mhz) <= 3.0]
        ref = max(near, key=lambda p: p[1])[1] if near else max(p[1] for p in peaks) if peaks else None
        exclude = max(2.0, 0.03 * wanted_mhz)
        checks = c.get("verify", [])
        oob = []
        for f, lev in peaks:
            if abs(f - wanted_mhz) <= exclude or ref is None:
                continue
            chk = next((v for v in checks if abs(v["freq_mhz"] - f) <= 0.2), None)
            if chk is None:
                real = None
            else:
                drop = chk["base_dbm"] - chk["att_dbm"]
                real = True if drop <= 2.0 else (False if drop >= 4.0 else None)
            order = round(f / carrier_mhz)
            # a harmonic if it is within 0.35 MHz of a whole multiple of the carrier (the wide scan has 0.1 MHz steps)
            oob.append({"freq_mhz": f, "dbm": lev, "dbc": round(lev - ref, 1),
                        "order": order if order >= 1 and abs(f - order * carrier_mhz) <= 0.35 else None, "real": real})
        oob.sort(key=lambda x: -x["dbc"])
        out.append({"fo_mhz": c["fo_mhz"], "drive": c["drive"], "wanted_dbm": ref, "floor_dbm": round(floor, 1),
                    "exclude_mhz": round(exclude, 2), "out_of_band": oob[:20],
                    "worst_oob_dbc": oob[0]["dbc"] if oob else None, "worst_oob_mhz": oob[0]["freq_mhz"] if oob else None})
    return {"configs": out}


def drive_levels(params, d):
    rows = d["rows"]
    k = str(max(int(x) for x in rows[0]["lev"])) if rows and rows[0]["lev"] else None
    wanted = [r["lev"].get(k) for r in rows]
    mono = all(b >= a for a, b in zip(wanted, wanted[1:])) if None not in wanted else None
    return {"wanted_order": k, "wanted_dbm_by_drive": {str(r["drive"]): r["lev"].get(k) for r in rows}, "monotonic": mono}


COMPUTE = {"response": response, "spur_map": spur_map, "spectrum_close": spectrum_close, "spectrum_wide": spectrum_wide,
           "drive_levels": drive_levels}


def compute(run):
    out = {}
    for name, t in run.get("tests", {}).items():
        fn = COMPUTE.get(name)
        if fn and t.get("data"):
            try:
                out[name] = fn(t.get("params", {}), t["data"])
            except (KeyError, ValueError, IndexError, TypeError) as e:
                out[name] = {"error": str(e)}
    return out


def summary(run, metrics=None):
    """A flat {name: number} of headline figures, for tables and trend charts."""
    m = metrics if metrics is not None else compute(run)
    s = {}
    r = m.get("response") or {}
    for key in ("bw3_mhz", "centre_mhz", "lowpass_cutoff_mhz", "passband_dbm", "ripple_db", "reject_low_db", "reject_high_db"):
        if r.get(key) is not None:
            s["response." + key] = r[key]
    for drive, v in (m.get("spur_map") or {}).items():
        if isinstance(v, dict):
            s["spur_map.%smA.worst_dbc" % drive] = v["worst_dbc"]
            s["spur_map.%smA.median_dbc" % drive] = v["median_dbc"]
            s["spur_map.%smA.best_dbc" % drive] = v["best_dbc"]
    for c in (m.get("spectrum_wide") or {}).get("configs", []):
        if c.get("worst_oob_dbc") is not None:
            s["wide.%smA.worst_oob_dbc" % c["drive"]] = c["worst_oob_dbc"]
    for drive, lev in ((m.get("drive_levels") or {}).get("wanted_dbm_by_drive") or {}).items():
        if lev is not None:
            s["drive.%smA.wanted_dbm" % drive] = lev
    return s
