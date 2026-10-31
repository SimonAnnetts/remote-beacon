# 6m output characterisation (CLK0, fundamental, with a 64 MHz low-pass filter)

Measured 2026-10-31 (16:47-17:00) with the bench framework, firmware at commit `833b76c` (working tree not clean: the
only differences were test files).
Raw data: [`../tests-results/6m/2026-10-31T16-47-16__6m-chebyshev-lpf-64MHz-38dB.json`](../tests-results/6m/2026-10-31T16-47-16__6m-chebyshev-lpf-64MHz-38dB.json).
Setup: [`../tests/bench/setups/6m-chebyshev-lpf-64MHz-38dB.json`](../tests/bench/setups/6m-chebyshev-lpf-64MHz-38dB.json).
View it, and compare it with later runs, in the bench web UI (`python3 tests/bench/serve.py`, port 3333).
This is the 6m baseline: later runs with a different filter, amplifier or PLL set-up should be compared with it.

## Summary

| | Result |
|---|---|
| Filter -3 dB point | **66.2 MHz** (-10 dB at 68.8, -20 at 72.4, -30 at 76.6, -40 at 81.6 MHz) |
| Passband | flat to about 1.3 dB peak-to-peak from 10 to 64 MHz; the whole 50-52 MHz band is inside it |
| Wanted level leaving the filter | about **+1 dBm (2 mA) to +12 dBm (8 mA)** (see "Pad" below; about +/-2 dB) |
| Close-in spurs, best | **-60 dBc at exactly 50.000 MHz**, at either drive |
| Close-in spurs, worst (50.1-52 MHz) | **-47 dBc (2 mA)**, **-33 dBc (8 mA)** |
| Typical close-in spur | 2 mA: -48 to -52 dBc; 8 mA: -35 to -45 dBc |
| Strongest out-of-band emission | the same fractional-N spur family, 2 MHz either side of a 51 MHz carrier: **-52 dBc (2 mA), -36.5 dBc (8 mA)** |
| Harmonics | 2nd, 3rd and 4th not seen (below about -64 dBc at 8 mA); 5th (255 MHz) -61 dBc and 9th (459 MHz) -63 dBc at 8 mA |

The close-in spurs are the main concern, as on 70cm: the filter is a low-pass and cannot remove anything near the carrier.
A higher drive makes them worse in dBc, not better.

## Setup

```
Pico W --I2C-- Si5351 (Adafruit, 25 MHz crystal, +151.3 ppm correction applied)
                 CLK0 --> 9-pole Chebyshev low-pass (64 MHz, home built)
                      --> T pad (27-33-27 ohm) --> BNC attenuator (marked "10 dB")
                      --> TinySA Ultra, low input
```

* CLK0 is on PLL A. The wanted signal is the fundamental; only CLK0 was enabled.
* TinySA Ultra `tinySA4_v1.4-200` (HW V0.4.6), controlled over USB. Attenuation 0 dB, LNA off.
* SMA cables, with SMA-to-BNC and BNC-to-SMA adapters to take the attenuator.

### Pad

**The attenuator marked "10 dB" actually loses 27 dB**, and the 27-33-27 ohm T pad, designed for about 10.5 dB, loses
15 dB. Neither value can be trusted from the part or its design: every pad in the chain was measured. The method was a
sweep of CLK0 at 2 mA from 20 to 180 MHz, first through a straight cable and the adapters, then with each pad added
(analyser attenuation 10 or 30 dB, so the straight-through reading was in its linear range):

| Between the Si5351 and the analyser | Loss, 20 to 180 MHz |
|---|---|
| Straight cable and adapters (reference, +2.4 to +3.6 dBm at 2 mA) | 0 |
| "10 dB" attenuator | 26.5 to 27.0 dB, flat |
| T pad | 14.9 to 15.4 dB, flat |
| Both together | 36.9 to 38.4 dB (**37.9 dB at 51 MHz**) |

The combined loss is less than the sum (42 dB) because the parts do not match perfectly. The setup file uses the combined
37.9 dB.

All levels in the results are as read by the analyser, after the pad. Adding the pad back gives the level leaving the
filter: **+1.0 dBm at 2 mA and +12.0 dBm at 8 mA**. Direct measurement of the unfiltered source gave +3.0 dBm at 2 mA, so
the filter loses roughly 2 to 4 dB in its passband, and the quoted levels carry an uncertainty of about 2 dB.

The first 6m attempts, with a single "10 dB" part and then a "20 dB" part (really 27 and 29.5 dB), were refused by the
runner's overload check, because the readings were far above what the labels predicted. See "Limitations".

## Method

The five standard tests, unchanged from the 70cm baseline (the procedure is in
[`../tests/bench/README.md`](../tests/bench/README.md)); versions: drive_levels 1, spur_map 1, spectrum_close 1,
spectrum_wide 2, response 2.

1. **Filter response.** Carrier stepped across 10-100 MHz (0.25 MHz steps over 45-56 MHz, 1 MHz elsewhere) at 8 mA, and
   113-140 MHz to see the harmonic region; the level was read at each carrier order.
2. **Spur map.** 21 carriers from 50.0 to 52.0 MHz in 0.1 MHz steps, +/-2 MHz window, 401 points, 3 sweeps, at 2 and 8 mA.
3. **Close-in spectrum** and **wide spectrum** (5-800 MHz, RBW 100 kHz) at 2 and 8 mA, with the analyser's own
   attenuation raised 10 dB to check whether a peak is real (a real signal does not change).
4. **Level against drive** at 51 MHz.

Reference point at the start and the end: identical (drift 0.0 dB). The analyser saw up to -24.8 dBm during the 8 mA
tests, 0.2 dB over the runner's -25 dBm limit; the runner recorded a warning. A separate check (below) shows the 8 mA
spurs are not caused by this.

## 1. Filter

The response measured at the analyser (8 mA):

| Carrier | Level | |
|---|---|---|
| 10-64 MHz | -24.8 to -25.9 dBm | passband |
| 66 MHz | -27.9 dBm | -2 dB |
| 68 MHz | -33.1 dBm | -7 dB |
| 70 MHz | -38.9 dBm | -13 dB |
| 75 MHz | -51.9 dBm | -26 dB |
| 80 MHz | -62.4 dBm | -37 dB |
| 90 MHz | -79.2 dBm | -53 dB |
| 95-97 MHz | -89.4 to -94.9 dBm | -63 to -69 dB |

The cutoff is a little above the nominal 64 MHz. The skirt is steep enough that harmonics at 2x (102 MHz) and above are
removed to below the analyser's detection limit.

## 2. Close-in spurs

### Where they come from

They are fractional-N spurs of the PLL, the same mechanism as on 70cm. With a 25 MHz crystal, **50.000 MHz is an integer
ratio**, so the PLL has no fractional part there and no spurs. At any other frequency the spurs appear at multiples of
the distance from 50.000 MHz:

| Carrier | Spur offsets seen |
|---|---|
| 50.5 MHz | +/-0.5, +/-1.0, +/-1.5 MHz |
| 51.0 MHz | +/-1.0, +/-2.0 MHz (and higher multiples: see section 3) |
| 52.0 MHz | +/-2.0 MHz |

### Spur map

Worst close-in spur against carrier frequency (dBc):

| Carrier (MHz) | 2 mA | 8 mA |
|---|---|---|
| **50.0** | **-60** | **-61** |
| 50.1 | -50 | -40 |
| 50.2 | -49 | -37 |
| 50.3 | -47 | -35 |
| 50.4 | -49 | -37 |
| 50.5 | -48 | -35 |
| 50.6 | -47 | -33 |
| 50.7 | -48 | -33 |
| 50.8 | -49 | -33 |
| 50.9 | -51 | -35 |
| 51.0 | -52 | -37 |
| 51.1 | -51 | -42 |
| 51.2 | -50 | -41 |
| 51.3 | -48 | -40 |
| 51.4 | -48 | -40 |
| 51.5 | -48 | -41 |
| 51.6 | -48 | -41 |
| 51.7 | -49 | -42 |
| 51.8 | -49 | -44 |
| 51.9 | -51 | -44 |
| 52.0 | -50 | -45 |

The worst point overall is -46.7 dBc at 50.3 MHz (2 mA) and -32.7 dBc at 50.7 MHz (8 mA). The map steps are 0.1 MHz, so the default beacon frequency (50.050 MHz) and the WSPR frequency (50.293 MHz plus tones) are
not measured exactly; 50.3 MHz is near the bad end of the table.

### A higher drive makes the spurs worse

From 2 mA to 8 mA the carrier rises 11 dB, but the strongest spurs rise much more. At 51.0 MHz the 49.0 MHz spur went
from -89.0 dBm to -62.3 dBm (26.7 dB). I do not know the mechanism. It is not the analyser: with 0, 10 and 20 dB of
analyser attenuation the +/-2 MHz spurs at 51.0 MHz and 8 mA read -36.3 to -37.2 dBc (lower) and -37.3 to -38.0 dBc
(upper), unchanged within about 1 dB, so they are real signals.

## 3. Out-of-band emissions (5-800 MHz)

The peak finder lists peaks more than 12 dB above the floor (about -101.5 dBm), so the detection limit is about
**-53 dBc at 2 mA and -64 dBc at 8 mA**. Nothing else is listed below those levels.

At 8 mA, with the real/analyser-made check (10 dB extra analyser attenuation):

| Frequency | Level | Relative | Notes |
|---|---|---|---|
| 49.0 MHz | -62.3 dBm | -36.5 dBc | real; the -2 MHz spur |
| 48.0 MHz | -77.5 dBm | -51.7 dBc | real; -3 MHz |
| 54.0 MHz | -78.5 dBm | -52.7 dBc | real; +3 MHz |
| 35.0 MHz | -82.0 dBm | -56.2 dBc | real; -16 MHz |
| 46.0 MHz | -83.5 dBm | -57.7 dBc | real; -5 MHz |
| 56.0 MHz | -83.8 dBm | -58.0 dBc | real; +5 MHz |
| 255.0 MHz | -86.5 dBm | -60.7 dBc | 5th harmonic of the carrier |
| 67.0 MHz | -87.6 dBm | -61.8 dBc | +16 MHz |
| 459.0 MHz | -88.6 dBm | -62.8 dBc | 9th harmonic |

The fractional-N spurs are at whole-MHz offsets from the carrier (the carrier is 1 MHz from 50.0 MHz), as far as
+/-16 MHz. At 2 mA only the 49.0 MHz spur (-52.2 dBc) is above the detection limit.

## 4. Level against drive (51 MHz)

At the analyser (after the 37.9 dB pad); add 37.9 dB for the level leaving the filter:

| Drive | At the analyser | Leaving the filter (approx.) |
|---|---|---|
| 2 mA | -36.9 dBm | +1.0 dBm |
| 4 mA | -30.9 dBm | +7.0 dBm |
| 6 mA | -27.9 dBm | +10.0 dBm |
| 8 mA | -25.9 dBm | +12.0 dBm |

The steps are +6.0, +3.0 and +2.0 dB for 2 to 4, 4 to 6 and 6 to 8 mA.

## 5. Baseline for a PGA-103+ stage

From the datasheet (not measured here): gain about 25 to 26.5 dB at 50 MHz, output P1dB +21.5 dBm (at 400 MHz; 6m
should be similar or better), maximum input +21 dBm.

* At **8 mA (+12 dBm)** the PGA-103+ would be driven far into compression (the output would be limited by P1dB, not by
  gain); the spurs in the table above would pass through, and compression turns them into more intermodulation.
* At **2 mA (+1 dBm)** the output would be about +26 dBm if linear, still above P1dB.
* For a linear stage a drive of about -5 dBm (or less) is needed, so an attenuator of **6 dB or more at 2 mA** (and 17 dB
  or more at 8 mA) belongs between the filter and the amplifier. The attenuator also improves the filter's termination.

## 6. What this suggests

1. **Choose the carrier frequency by its spurs.** 50.000 MHz is clean; the rest of the band has spurs at -33 to -52 dBc.
   If the beacon frequency is free to choose, pick it close to 50.000 MHz.
2. **Use low drive and let the amplifier supply the power.** Going from 8 mA to 2 mA improves the worst close-in spur
   by about 14 dB (from -33 to -47 dBc), at 11 dB less carrier.
3. **A low-pass filter will not clean this up.** The spurs are inside the band. Reducing them needs a different PLL
   choice (an integer ratio, or a different crystal frequency) or a narrow band-pass filter.
4. **Check the 50.05 MHz and 50.293 MHz frequencies directly** before relying on them: they are not in the map.

## Limitations

* The pad was measured at 2 mA and at 20-180 MHz; at 8 mA with the filter in front it may differ slightly (the combined
  pad had 1 to 2 dB of mismatch). The levels leaving the filter are good to about 2 dB.
* The runner's overload check only guards against too much signal. It cannot tell if the attenuation is what the
  setup file says, so a mislabelled pad shows up only when a reading contradicts the label. For a new setup, it is worth
  measuring each pad with the same sweep first.
* The 8 mA headroom was marginal (-25.9 dBm against -25). The check on the +/-2 MHz spurs, done separately, shows the
  8 mA close-in spurs are not caused by it, but a repeat with an extra 6 dB of pad would remove the doubt. It would cost
  about 6 dB of detection range at 2 mA.
* Only one filter and one pad set have been measured. No amplifier or antenna was connected.
* The TinySA is not a calibrated instrument: the relative numbers (dB, dBc) are more reliable than the absolute dBm.
* The same attenuator marked "10 dB" was used for the 70cm baseline. Its loss at 435 MHz was measured afterwards as
  25.8 dB, and the 70cm document has been corrected (its absolute levels were 15.8 dB too low).
