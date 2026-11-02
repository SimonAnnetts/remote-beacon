# Cleanest carrier frequencies in each band

The Si5351's close-in spurs depend strongly on the carrier frequency (see the three output characterisations). This page
lists, for each band, the frequencies where the **worst close-in spur** (within +/-2 MHz of the carrier on 6m and 2m,
+/-5 MHz on 70cm) was lowest. The figures are in dBc, relative to the wanted carrier, so lower (more negative) is better.

Sources: the spur-map test of each baseline run in `tests-results/`, at 2 mA and 8 mA drive.

* 6m: `6m-chebyshev-lpf-64MHz-38dB` (0.1 MHz steps).
* 2m: the **worst case over four filter set-ups** (band-pass, low-pass, both touching, both 15 cm apart), so the figure holds
  whichever of those is fitted (0.1 MHz steps). The Chebyshev low-pass alone (2026-11-01) is given below it.
* 70cm: `70cm-saw-unknown-10dB`, 02-51-44 baseline (0.25 MHz steps). The pad correction does not affect dBc.

## Read this first

* **The maps are coarse** (0.1 MHz on 6m and 2m, 0.25 MHz on 70cm). The pattern can change faster than that: on 6m,
  50.000 MHz is -60 dBc but 50.100 MHz is -50 dBc. Treat these as pointers, then run a finer map around the frequency you
  choose (see the end).
* **Frequencies between map points have not been measured.** That includes the default beacon frequencies (50.050, 144.450
  and 432.450 MHz) and the 6m WSPR frequency (50.293 MHz dial, tones 1.5 kHz higher).
* **Lower drive is cleaner.** Every band is 5 to 20 dB better at 2 mA than at 8 mA. Frequencies that are good at 8 mA are good
  at 2 mA too.
* **These are close-in spurs only.** Harmonics and the 5 MHz spurs on 2m depend on filters, not on the exact carrier frequency
  (see each characterisation).
* The IARU Region 1 beacon sub-bands are about 50.000-50.100 MHz, 144.400-144.490 MHz and 432.400-432.500 MHz. **Check the
  current band plan and your licence before choosing**; this page only says where the spurs are low.

## 6m (CLK0)

Worst close-in spur against carrier frequency (dBc):

| Carrier (MHz) | 2 mA | 8 mA | |
|---|---|---|---|
| **50.000** | **-60** | **-61** | best by far: an integer ratio of the PLL, so no fractional-N spurs |
| 52.000 | -50 | -45 | best 8 mA figure besides 50.000 |
| 51.900 | -51 | -44 | |
| 51.800 | -49 | -44 | |
| 51.700 | -49 | -42 | |
| 51.100 | -51 | -42 | |
| 51.000 | -52 | -37 | good at 2 mA only |
| 50.900 | -51 | -35 | good at 2 mA only |
| 50.100 | -50 | -40 | |

**Avoid** (-37 dBc or worse at 8 mA): 50.200 to 51.000 MHz. The worst point is 50.700 MHz at 8 mA (-33 dBc) and 50.300 MHz
at 2 mA (-47 dBc).

For beacons: 50.000 MHz (exactly) is the clean choice, and it sits at the bottom of the IARU beacon sub-band. The default
50.050 MHz was not measured; its neighbours are -60 dBc (50.000) and -50 dBc (50.100). 50.293 MHz (WSPR) sits in the
region to avoid (-47 dBc at 2 mA and -35 dBc at 8 mA for the nearby 50.300 MHz point).

## 2m (CLK1)

Worst close-in spur, taking the worst result among four filter set-ups (dBc):

| Carrier (MHz) | 2 mA | 8 mA |
|---|---|---|
| **144.600** | **-63** | -46 |
| **144.300** | **-61** | **-48** |
| **144.500** | -60 | -44 |
| 145.500 | -57 | -44 |
| **144.400** | -56 | **-48** |
| 144.000 | -52 | -45 |
| 144.200 | -51 | |
| 144.100 | -49 | |
| 145.800 / 145.900 | | -43 |

With the best filter arrangement (low-pass, 15 cm coax, band-pass) 144.0 to 144.6 MHz gives -52 to -65 dBc at 2 mA
(144.600 MHz: -65; the lowest is -57 at 144.400 MHz) and -52 to -57 dBc at 8 mA. The band-pass on its own is worse, so these figures need the low-pass in the chain.

With the **Chebyshev low-pass alone** (8 mA / 2 mA): 144.3 to 144.6 MHz gives -53 to -56 dBc at 8 mA (-56 to -63 dBc at 2 mA);
144.0 to 144.2 MHz is the worst part of the lower band (-38.5 to -41 dBc at 8 mA); 144.7 to 145.4 MHz is -41 to -47 dBc at 8 mA
(145.5 MHz is an isolated -55 dBc) and 145.6 MHz is worst at 2 mA (-47 dBc). Same pattern as the other set-ups, apart from 144.0 to 144.2 MHz.

With the **7-pole low-pass on a 12 cm pigtail** (the cleanest set-up so far): at 8 mA every point from 144.0 to 146.0 MHz is
-46 to -53 dBc (best 145.8 to 145.9 MHz at -53; worst 145.3 MHz at -45.7 and 144.1 MHz at -46.5), so the choice of frequency matters
little. At 2 mA 144.0 to 145.5 MHz is -57 to -64 dBc (best 144.2 MHz) and **145.6 to 146.0 MHz is worse (-47 to -52 dBc)**.

**Avoid (earlier set-ups):** 144.700 to 145.400 MHz and 145.600 MHz (-36 to -48 dBc at 8 mA); 145.300 MHz is the worst point.

For beacons: the default 144.450 MHz was not measured, but both neighbours (144.400 and 144.500 MHz) are good, so it is
probably fine. 144.300 to 144.600 MHz is a clean region.

## 70cm (CLK2, 3rd harmonic)

Worst close-in spur against the wanted frequency (dBc). The map has 0.25 MHz steps, so the picture is coarse:

| Wanted (MHz) | 2 mA | 8 mA |
|---|---|---|
| **431.250** | **-57** | **-56** |
| 435.000 | -54 | -52 |
| 431.750 | -55 | -51 |
| 431.500 | -51 | -51 |
| 431.000 | -53 | -50 |
| 433.000 | -52 | -50 |
| 430.750 | -56 | -49 |
| 432.250 | -54 | -47 |
| 430.250 | -53 | -47 |
| 439.500 | -53 | -45 |

Good region: **430.75 to 432.25 MHz**, plus isolated points at 433.000 and 435.000 MHz.

**Avoid:** 436.000 to 438.500 MHz (-35 to -45 dBc; 437.500 MHz is a lone exception at -49); the worst point is 436.750 MHz (-35 dBc at 2 mA, -36 dBc at 8 mA),
and 437.000 MHz is nearly as bad.

For beacons: the default 432.450 MHz was not measured. Its neighbours, 432.250 and 432.500 MHz, are -54 and -53 dBc at 2 mA
but -47 and -45 dBc at 8 mA, so use low drive there.

## Refining the choice

Measure the spur map more finely around a frequency you are considering. On the bench with that band's chain connected:

```
python3 tests/bench/run.py --setup <setup id> --tests spur_map \
    --set spur_map.start=432.4 --set spur_map.stop=432.5 --set spur_map.step=0.005 \
    --note "fine map around the 70cm beacon segment"
```

(`--set test.param=json`; the steps must be small enough to resolve the pattern, and a run with different parameters is
flagged as not like-for-like in the Compare view, which is correct.) A finer map of the beacon sub-band on each band, at the
drive you will use, is the most useful next measurement.
