"""70cm output characterisation: Si5351 CLK2 (carrier near 145 MHz, 3rd harmonic wanted) -> SAW -> 10 dB pad -> TinySA.
Writes campaign_results.json incrementally. All levels are as read by the TinySA, i.e. AFTER the 10 dB pad."""
import json, math, sys, time, traceback
import tinysa
from pico import Pico, SETUP

OUT = "campaign_results.json"
results = {"notes": "levels in dBm at the TinySA input (after a 10 dB pad); SAW fitted on CLK2", "saw": [], "close_in": [], "wide": [], "drive": []}

def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)

def save():
    json.dump(results, open(OUT, "w"))

def window(s, f, half=150e3, pts=41, n=2):
    """Average n scans around f; return (peak dBm, median floor dBm)."""
    acc = None
    for _ in range(n):
        d = tinysa.scan(s, int(f - half), int(f + half), pts)
        pw = [10 ** (p[1] / 10) for p in d]
        acc = pw if acc is None else [x + y for x, y in zip(acc, pw)]
    db = [10 * math.log10(x / n) for x in acc]
    return max(db), sorted(db)[len(db) // 2]

def measure_harmonics(s, p, fo, drive, orders=(1, 2, 3, 4)):
    carrier = int(round(fo / 3))
    act = int(p.run("print(out(%d, %d))" % (carrier, drive)))
    time.sleep(0.05)
    row = {"fo_target": fo, "carrier": act, "drive": drive, "lev": {}, "floor": {}}
    for k in orders:
        fk = k * act
        if fk > 790e6:
            continue
        peak, floor = window(s, fk)
        row["lev"][k] = round(peak, 2)
        row["floor"][k] = round(floor, 2)
    return row

def sweep_points(s, start, stop, points, n):
    acc = None
    for _ in range(n):
        d = tinysa.scan(s, int(start), int(stop), points)
        pw = [10 ** (q[1] / 10) for q in d]
        acc = pw if acc is None else [x + y for x, y in zip(acc, pw)]
    freqs = [q[0] for q in d]
    return freqs, [10 * math.log10(x / n) for x in acc]

def peaks(freqs, dbm, floor_margin=10, guard=(None, 0)):
    floor = sorted(dbm)[len(dbm) // 2]
    out = []
    for i in range(1, len(dbm) - 1):
        if dbm[i] >= dbm[i - 1] and dbm[i] >= dbm[i + 1] and dbm[i] > floor + floor_margin:
            out.append((freqs[i], dbm[i]))
    return out, floor

def main():
    s = tinysa.open_port()
    p = Pico()
    p.run(SETUP)
    try:
        tinysa.command(s, "attenuate 0"); tinysa.command(s, "lna off")

        log("== 1. SAW passband: 3rd harmonic stepped 425-445 MHz, 0.25 MHz steps, 8 mA")
        tinysa.command(s, "rbw 10")
        t0 = time.time()
        for i in range(81):
            fo = 425e6 + i * 0.25e6
            results["saw"].append(measure_harmonics(s, p, fo, 8))
            if i % 10 == 0:
                log("   %.2f MHz  3f=%.1f dBm  (%.0fs)" % (fo / 1e6, results["saw"][-1]["lev"].get(3, float("nan")), time.time() - t0))
        save()

        log("== 2. SAW wide: 340-424 and 446-500 MHz, 1 MHz steps, 8 mA")
        for fo in list(range(340, 425)) + list(range(446, 501)):
            results["saw"].append(measure_harmonics(s, p, fo * 1e6, 8))
            if fo % 10 == 0:
                log("   %d MHz  3f=%.1f dBm" % (fo, results["saw"][-1]["lev"].get(3, float("nan"))))
        save()

        log("== 3. close-in spectrum +/-5 MHz, RBW 30 kHz, 6 sweeps averaged")
        tinysa.command(s, "rbw 30")
        for fo, drive in ((435.0, 2), (435.0, 4), (435.0, 6), (435.0, 8), (432.45, 2), (432.45, 8), (438.0, 2), (438.0, 8)):
            act = int(p.run("print(out(%d, %d))" % (round(fo * 1e6 / 3), drive)))
            time.sleep(0.5)
            freqs, d = sweep_points(s, 3 * act - 5e6, 3 * act + 5e6, 401, 6)
            ci = max(range(len(d)), key=lambda i: d[i])
            pk, floor = peaks(freqs, d, 8)
            spurs = sorted([(lev - d[ci], (f - freqs[ci]) / 1e6, lev) for f, lev in pk if abs(f - freqs[ci]) > 150e3], reverse=True)[:12]
            results["close_in"].append({"fo": fo, "drive": drive, "carrier_dbm": round(d[ci], 2), "carrier_hz": freqs[ci], "floor": round(floor, 1),
                                        "spurs": [(round(o, 3), round(l, 1), round(c, 1)) for c, o, l in spurs]})
            log("   %.2f MHz %d mA: carrier %.1f dBm, %d spurs, strongest %s" % (fo, drive, d[ci], len(spurs), spurs[:3]))
        save()

        log("== 4. wide spectrum 5-800 MHz, RBW 100 kHz, windows of 450 points, 2 sweeps averaged")
        tinysa.command(s, "rbw 100")
        step = 100e3 * 449
        for fo, drive in ((435.0, 2), (435.0, 8)):
            act = int(p.run("print(out(%d, %d))" % (round(fo * 1e6 / 3), drive)))
            time.sleep(0.5)
            rec = {"fo": fo, "drive": drive, "carrier": act, "peaks": [], "floors": []}
            start = 5e6
            while start < 800e6:
                stop = min(start + step, 800e6)
                pts = int((stop - start) / 100e3) + 1
                freqs, d = sweep_points(s, start, stop, min(pts, 450), 2)
                pk, floor = peaks(freqs, d, 12)
                rec["peaks"] += [(round(f / 1e6, 3), round(l, 1)) for f, l in pk]
                rec["floors"].append((round(start / 1e6), round(floor, 1)))
                start = stop + 100e3
            results["wide"].append(rec)
            log("   %d mA: %d peaks; strongest: %s" % (drive, len(rec["peaks"]), sorted(rec["peaks"], key=lambda q: -q[1])[:6]))
            save()

        log("== 5. level versus drive at 435 MHz")
        tinysa.command(s, "rbw 10")
        for drive in (2, 4, 6, 8):
            row = measure_harmonics(s, p, 435e6, drive, orders=(1, 3))
            results["drive"].append(row)
            log("   %d mA: 145 MHz %.1f dBm, 435 MHz %.1f dBm" % (drive, row["lev"][1], row["lev"][3]))
        save()
        log("campaign complete")
    except Exception:
        log("FAILED:\n" + traceback.format_exc())
        save()
    finally:
        try:
            p.run("off()")
        except Exception as e:
            log("could not switch the output off:", e)
        tinysa.command(s, "rbw 100"); tinysa.command(s, "sweep 420000000 460000000 450")
        s.close(); p.close()
        log("output off, TinySA restored")

main()
