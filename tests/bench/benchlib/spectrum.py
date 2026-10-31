"""Spectrum arithmetic shared by the measurements and the metrics."""
import math


def power_average(traces):
    """Average several dBm traces (equal length) in the power domain."""
    n = len(traces)
    return [10 * math.log10(sum(10 ** (t[i] / 10) for t in traces) / n) for i in range(len(traces[0]))]


def median(values):
    s = sorted(values)
    return s[len(s) // 2]


def find_peaks(freqs, dbm, margin_db=12.0):
    """Local maxima more than margin_db above the median floor: ([(freq, dbm)], floor)."""
    floor = median(dbm)
    peaks = [(freqs[i], dbm[i]) for i in range(1, len(dbm) - 1)
             if dbm[i] >= dbm[i - 1] and dbm[i] >= dbm[i + 1] and dbm[i] > floor + margin_db]
    return peaks, floor


def extract_spurs(freqs, dbm, guard_hz, margin_db=8.0, top=8):
    """Carrier and spurs of a window centred on a carrier.

    Returns (carrier_dbm, carrier_hz, floor_dbm, [(offset_hz, dbc), ...]) with
    the strongest spurs first. Peaks within guard_hz of the carrier are ignored:
    they are the analyser's own filter skirt.
    """
    ci = max(range(len(dbm)), key=lambda i: dbm[i])
    peaks, floor = find_peaks(freqs, dbm, margin_db)
    spurs = [(f - freqs[ci], lev - dbm[ci]) for f, lev in peaks if abs(f - freqs[ci]) > guard_hz]
    spurs.sort(key=lambda s: -s[1])
    return dbm[ci], freqs[ci], floor, spurs[:top]


def rbw_for_step(step_hz, choices=(1, 3, 10, 30, 100, 300)):
    """Smallest RBW (kHz) that is not narrower than the sweep step, so no peak falls between points."""
    for c in choices:
        if c * 1000 >= step_hz:
            return c
    return choices[-1]
