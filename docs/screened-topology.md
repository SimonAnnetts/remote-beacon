# Screened board with a pad on each output (2026-11-03 and 04)

The Si5351 board is now screened and each output (CLK0 6m, CLK1 2m, CLK2 70cm) has a fully screened pad of about 8 dB fitted
directly on it. This page records the loss of those pads, and the full bench suite for each band without a filter and then
with the filter that band normally uses. The earlier set-ups (unscreened board, no source pad, or a carbon T pad) are in the
three band documents; section 8 of each links back here.

## Summary

* **The three screened pads lose 7 to 9.5 dB** over the ranges that matter (table below), flat to within about 1 dB. Nominal
  "8 dB" is right to within 1 dB.
* **70cm: the pad is what the earlier T-pad test predicted.** With the SAW fitted, the drive curve is smooth (6.5, 3.5, 2.5 dB
  steps; the old baseline wobbled), the 725 MHz harmonic is 8 dB better in dBc (-44.3 against -36.3), and the SAW response is
  unchanged (-3 dB at 421.0 to 444.5 MHz). The reflection explanation is supported again, not measured directly.
* **6m: one clear gain.** The 49 MHz spur at 8 mA is -48.7 dBc (the old runs: -36.5 and -35.2). The close-in spurs are inside
  the pass band and the filter cannot change them, so they are about the same as before.
* **2m: no measurable gain over the best earlier set-up** (the 7-pole on a 12 cm pigtail). The two are within 1 to 4 dB for the
  close-in spurs at 2, 4 and 8 mA. The filter and the pad contributions were not separated.
* **The unfiltered outputs are what the filters have to deal with.** On 6m and 2m the 3rd harmonic is only -8 to -11 dBc and the
  5th -11 to -14 dBc. On 70cm the 145 MHz carrier is stronger than the wanted 435 MHz signal (+7.7 dBc at 8 mA) and the 5th
  harmonic (725 MHz) is -2.3 dBc.
* **The 8 mA spur at 440.0 MHz on 70cm (-30.7 to -32.0 dBc) is a property of the source, not of the SAW**, since the unfiltered
  output has it too.
* Unfiltered 6m and 2m could only be run at 2 and 4 mA (the 8 mA signal would be above the analyser's limit). The filtered 6m
  and 2m runs were at the limit at 8 mA and carry a warning.

## Pad measurements

Each pad was measured by the sweep method used before: CLK output stepped across the range at 2 mA, level read on the TinySA, once
with the pad fitted and once with it removed, through the same 30 cm cable and the BNC attenuator marked "10 dB" in front of
the analyser. The loss is the difference. The raw sweeps are in
[`data/screened-pads-and-6m-lpf-2026-11-03.json`](data/screened-pads-and-6m-lpf-2026-11-03.json); they were made by an ad-hoc
script, not by the bench runner, and are not in `tests-results/`. For 70cm the wanted frequency (425 to 445 MHz) is the 3rd
harmonic of a carrier of 142 to 148 MHz.

| Output | Range | Loss | At the working frequency |
|---|---|---|---|
| CLK0 (6m) | 20 to 180 MHz | 8.5 to 9.5 dB | 8.7 dB at 50 MHz; 8.5 to 8.7 dB at 70.0 to 70.5 MHz |
| CLK1 (2m) | 20 to 180 MHz | 7.0 to 8.5 dB | 7.5 dB at 144 to 146 MHz (7.7 at 150 MHz); 8.0 dB at 70 MHz |
| CLK2 (70cm) | 425 to 445 MHz | 8.9 to 9.5 dB | 8.9 dB at 435 MHz |

* The CLK0 value at 156 MHz (7.6 dB) is a single point against 8.5 to 9.5 dB around it, and is probably a glitch or a spur.
* **The reference levels differ between outputs**: with no pad, 2 mA read -23.0 dBm on CLK0 and -25.9 dBm on CLK1 at 20 MHz
  (the same cable and attenuator), so CLK1 delivers about 3 dB less. That is why each pad has its own reference, taken on its own
  output.
* The "10 dB" attenuator in front of the analyser is the same one as before: 25.8 dB at 435 MHz, about 27 dB at VHF (flat over
  20 to 180 MHz). It was not re-measured in these chains. The 6m and 2m setup files use 27.0 dB for it.
* The 30 cm cable is in both the with-pad and without-pad sweeps, so each figure is the pad alone.

## Runs

All runs are in `tests-results/`, with a matching setup in `tests/bench/setups/`. In the filtered setups the screened pad is
**before** the filter, so it is not in `pad_db`: the levels leaving the filter include its loss, like the T-pad runs on 70cm.

| Band | Run | `pad_db` | Notes |
|---|---|---|---|
| 70cm | `70cm/2026-11-03T18-47-53__70cm-screened-pad-nofilter-10dB` | 34.7 | CLK2, pad, 30 cm, attenuator. Warning: analyser saw -24.0 dBm (the 145 MHz carrier at 8 mA, not the wanted signal) |
| 70cm | `70cm/2026-11-03T19-18-21__70cm-screened-pad-saw-unknown-10dB` | 25.8 | pad, SAW directly after it, 30 cm, attenuator. No warnings |
| 6m | `6m/2026-11-03T21-00-44__6m-screened-pad-nofilter-10dB` | 35.7 | 2 and 4 mA only. Not like-for-like with the full runs |
| 6m | `6m/2026-11-03T22-21-58__6m-screened-pad-chebyshev-lpf-64MHz-10dB` | 27.0 | filter directly after the pad. Run with `--force` (8 mA read -24.3 dBm, 0.7 dB over); warning: analyser saw up to -22.6 dBm |
| 2m | `2m/2026-11-04T17-47-34__2m-screened-pad-nofilter-10dB` | 34.5 | 2 and 4 mA only. Not like-for-like with the full runs |
| 2m | `2m/2026-11-04T18-03-49__2m-screened-pad-lpf-7pole-10dB` | 27.0 | filter directly after the pad. Warning: analyser saw up to -23.5 dBm |

One 6m no-filter run (19-51-06) was discarded: a connection was loose at the start and the reference level drifted by 31 dB. It was
deleted and rerun (the 21-00-44 run above).

## 70cm

Compared with the unscreened baseline (`70cm-saw-unknown-10dB`, no source pad). Absolute levels are not comparable (the pad
adds about 9 dB of loss), so use the dBc figures.

| | Screened pad + SAW | Baseline | Unfiltered, screened pad |
|---|---|---|---|
| 435 MHz at the analyser, 2 / 4 / 6 / 8 mA | -45.7 / -39.2 / -35.7 / -33.2 dBm | -34.4 / -32.2 / -32.7 / -28.9 | -44.2 / -37.7 / -34.2 / -32.0 |
| Drive curve | smooth, rising | dips at 6 mA | smooth, rising |
| SAW -3 dB points | 421.0 to 444.5 MHz | 420.9 to 444.1 | not applicable |
| Rejection, low / high side | 44.3 / 23.1 dB | 41.3 / 24.8 | not applicable |
| 725 MHz, 8 mA | **-44.3 dBc** | -36.3 | -2.3 |
| 145 MHz, 8 mA | -52.5 dBc | -47.3 | +7.7 |
| 580 MHz, 8 mA | -55.2 dBc | -53.7 | -12.2 |
| 290 MHz, 8 mA | not reported | not reported | -10.6 |
| Close-in spur at 435 MHz, 4 / 6 / 8 mA | -53.6 / -54.0 / -51.5 dBc | -52.8 / -52.8 / -52.9 | -53.4 / -53.8 / -52.7 |
| Close-in spur at 432.45 MHz, 2 / 8 mA | -49.7 / -46.3 dBc | -49.7 / -46.1 | -49.4 / -46.8 |
| Close-in spur at 438 MHz, 2 / 8 mA | -38.5 / -36.1 dBc | -38.5 / -38.1 | -37.8 / -34.6 |
| Spur map worst, 2 mA | -36.2 dBc at 438.25 MHz | -34.8 at 436.75 | -35.3 at 438.25 |
| Spur map worst, 8 mA | -32.0 dBc at 440.0 MHz | -35.8 at 437.0 | -30.7 at 440.0 |
| Spur map median, 2 / 8 mA | -49.3 / -43.8 dBc | -48.9 / -45.4 | -48.9 / -45.0 |
| Spur map best, 8 mA | -54.4 dBc at 431.25 MHz | -56.1 at 431.25 | -56.3 at 431.25 |

* **The drive curve is smooth.** Steps of 6.5, 3.5 and 2.5 dB with the SAW; the baseline's wobble (a dip at 4 and 6 mA) was the
  reflection effect seen in the pigtail tests. A pad at the source removes it, as predicted.
* **The SAW removes the harmonics well**: the unfiltered 725 MHz harmonic is -2.3 dBc, with the SAW -44.3 dBc, about 42 dB of
  rejection, and 580 MHz goes from -12.2 to -55.2 dBc. The 145 MHz fundamental goes from +7.7 dBc (stronger than the wanted
  signal) to -52.5 dBc.
* **Close-in spurs come from the source.** The filtered and unfiltered runs are within 1 to 2 dB everywhere, and the
  worst point on the 8 mA map is 440.0 MHz in both (-32.0 and -30.7 dBc). This settles a point left open after the T-pad run: that
  440.0 MHz spur is not the SAW.
* **The worst point moved from 437.0 MHz (baseline) to 440.0 MHz.** The pad changes the spur pattern at the top of the map (437 to
  440 MHz); the best region (430 to 435 MHz) is unchanged. The baseline's 437.0 MHz figure (-35.8 dBc) was not repeated with the pad.
* The 2 mA data is range-limited, as in the T-pad run: no close-in spur is reported at 435 MHz at 2 mA (the baseline had -53.5 dBc).
* The baseline comparison is across two different topologies (screened board and pad against unscreened), so a difference of a
  few dB in the close-in spurs cannot be assigned to the pad or the board.

## 6m

Compared with the old baseline (`6m-chebyshev-lpf-64MHz-38dB`) and the 12 cm pigtail run. Unfiltered figures are at 2 and 4 mA only.

| | Screened pad + filter | Old baseline | Old pigtail | Unfiltered |
|---|---|---|---|---|
| 51 MHz level, 2 / 4 / 6 / 8 mA | -33.9 / -28.9 / -25.9 / -24.1 dBm | -36.9 / -30.9 / -27.9 / -25.9 | -37.3 / -30.8 / -28.3 / -25.8 | -32.8 / -27.3 (2, 4 mA) |
| Close-in spur at 51.0 MHz, 2 / 4 / 6 / 8 mA | -50.3 / -44.0 / -40.8 / -39.3 dBc | -52.2 / -47.6 / -41.4 / -37.2 | -50.2 / -44.5 / -39.5 / -36.0 | -49.2 / -42.5 (2, 4 mA) |
| Spur map worst, 2 / 8 mA | -44.5 (50.6 MHz) / -35.7 (51.3) | -46.7 (50.3) / -32.7 (50.7) | -43.5 (50.7) / -31.5 (50.7) | -45.0 (50.6) / -39.3 at 4 mA (51.3) |
| Spur map median, 2 / 8 mA | -47.5 / -38.7 dBc | -48.8 / -40.3 | -49.0 / -43.0 | -47.0 / -42.8 at 4 mA |
| 49 MHz spur, 2 / 8 mA | -51.5 / **-48.7 dBc** | -52.2 / -36.5 | -49.0 / -35.2 | not listed |
| 48 / 54 MHz spurs, 8 mA | -49.5 / -50.7 dBc | -51.7 / -52.7 | -47.8 / -48.2 | |
| 3rd harmonic (153 MHz) | not reported | not reported | not reported | -10.6 dBc (2 mA), -9.8 (4 mA) |
| 5th harmonic (255 MHz) | not reported | -60.7 dBc at 8 mA | not reported | -14.0 dBc (2 mA), -13.3 (4 mA) |

* **The close-in spurs are the same with and without the filter** (-50.3 against -49.2 dBc at 2 mA, -44.0 against -42.5 at 4 mA),
  as expected: they are inside the pass band and come from the synthesis. The pad changes little here.
* **The 49 MHz spur at 8 mA is 12 dB better** (-48.7 against -36.5 and -35.2 dBc). It is 2 MHz below the carrier; it is
  probably what the pad's reflection isolation helps, but the mechanism is not measured.
* **The 8 mA spur-map median is 1.6 dB worse than the baseline and 4.3 dB worse than the pigtail run**, from a run that read up to
  -22.6 dBm at the analyser, so analyser distortion cannot be ruled out. Nothing can be read into the 8 mA close-in differences.
* **The unfiltered harmonics** are -10 dBc (3rd) and -14 dBc (5th) at 2 mA, falling slowly through 7th to 15th (-17 to -22 dBc).
  The filter removes them: with the filter the 3rd and 5th are not among the reported entries (the weakest reported entry is
  -64.3 dBc), but the list is limited in length, so this is not a measured limit.
* The filter's loss in the passband (51 MHz) was not derived from this pair of runs, since the pad_db values differ. The previous
  measurement was 1.9 dB at 51 MHz on a pigtail (0.4 to 2.5 dB ripple), and it is the figure to use.

## 2m

Compared with the best earlier set-up, the 7-pole on a 12 cm pigtail (`2m-lpf-7pole-12cm-pigtail-37dB`). Unfiltered figures are at
2 and 4 mA only.

| | Screened pad + 7-pole | Old 7-pole, pigtail | Unfiltered |
|---|---|---|---|
| 145 MHz level, 2 / 4 / 6 / 8 mA | -35.7 / -30.2 / -27.2 / -25.2 dBm | -38.1 / -32.6 / -29.1 / -27.6 | -35.1 / -29.6 (2, 4 mA) |
| Close-in spur at 145.0 MHz, 2 / 4 / 6 / 8 mA | -63.3 / -60.9 / -47.9 / -53.5 dBc | -63.0 / -58.7 / -56.8 / -50.1 | -63.8 / -54.3 (2, 4 mA) |
| Spur map median, 2 / 8 mA | -62.2 / -52.7 dBc | -61.0 / -49.0 | -61.1 / -52.8 at 4 mA |
| Spur map worst, 2 / 8 mA | -46.2 (145.6 MHz) / -46.7 (145.3) | -47.0 (145.6) / -45.7 (145.3) | -46.9 (145.6) / -46.7 at 4 mA (145.6) |
| 5 MHz spurs 140 / 150 MHz, 8 mA | -42.1 / -47.4 dBc | -45.2 / -50.6 | not reported |
| 435 MHz (3rd) | -62.7 dBc at 8 mA | not reported | -9.2 dBc (2 mA), -8.2 (4 mA) |
| 725 MHz (5th) | not reported | -61.5 dBc at 8 mA | -12.5 dBc (2 mA), -11.5 (4 mA) |
| 290 MHz (2nd) | not reported | -58.3 dBc at 8 mA | -22.4 dBc (2 mA), -19.3 (4 mA) |
| 580 MHz (4th) | not reported | not reported | -25.4 dBc (2 mA), -21.9 (4 mA) |
| -3 dB point | 148.2 MHz | 149.0 MHz | not applicable |

* **No measurable gain over the best earlier set-up.** The close-in spurs agree to within 1 to 4 dB at 2, 4 and 8 mA; the 2 mA
  median of -62 dBc and the worst point at 145.6 MHz (the clean-frequencies pattern) are the same.
* **One drive is much worse: 6 mA at 145.0 MHz is -47.9 dBc** (-56.8 in the old run). It is a single spur at one drive, and has not
  been investigated. A repeat of that point would show whether it is real.
* The 5 MHz spurs at 140 and 150 MHz are about 3 dB worse at 8 mA. They come from the synthesiser, so a pad would not be
  expected to help, and 3 dB is not significant.
* **At 4 mA the filtered close-in spur is 6.6 dB better than unfiltered** (-60.9 against -54.3 dBc), with a different offset (0.11
  against -0.31 MHz). Not explained; at 2 mA the two are equal.
* **Harmonics:** the 435 MHz harmonic is -62.7 dBc with the filter, against -8 to -9 dBc without it, so at least 50 dB of rejection.
  The 725 and 290 MHz harmonics are not in the filtered 8 mA list (the old run had them at -61.5 and -58.3 dBc), so they are at
  or below about that level. That is a statement about the list, not an improvement.
* The -3 dB point is 0.8 MHz lower (148.2 against 149.0 MHz); the pad and layout may change the filter's termination.
* This run does not separate the pad's effect from the filter's: that needs the same 7-pole run without the source pad.

## The 6m filter at 70 MHz (4m idea)

An exploratory measurement made before the pads were re-measured: how the 9-pole Chebyshev low-pass behaves from 30 to 100 MHz,
with the question of using CLK0 on the 4m band (70.0 to 70.5 MHz). It was made on the old topology (unscreened board, CLK0 -
12 cm - filter - 15 cm - pad pair of about 38 dB, inferred from the -35.25 dBm reference level - TinySA). Loss is the filter
sweep minus a reference sweep with the filter removed (flat at -35.25 dBm, ±0.5 dB, 30 to 100 MHz); 2 mA, an ad-hoc script. Raw data
in the file above.

| Frequency (MHz) | Loss (dB) |
|---|---|
| 30 to 40 | 1.5 to 2.5 |
| 42 to 48 | 0.4 to 0.9 |
| 50 to 51 | 1.9 |
| 52 to 56 | 1.9 to 2.4 |
| 58 to 66 | -0.2 to 0.9 |
| 68 | 7.2 |
| 70.0 | 14.9 |
| 70.25 | 15.9 |
| 70.5 | 16.6 |
| 72 | 21.4 |
| 76 / 80 / 90 | 32 / 41 / 58 |
| 94 and above | at least 66 (noise floor) |

* The passband ripple is 0.4 to 2.5 dB up to 66 MHz, and the -3 dB point is near 67 MHz.
* **The filter loses 15 to 17 dB across 70.0 to 70.5 MHz**, so it cannot be used for 4m as it is. A filter for both bands would need an
  edge around 75 to 80 MHz, which would give less rejection of 6m's 2nd harmonic (about 100 MHz); the existing filter has at least
  67 dB there. A separate 4m filter and an RF switch is the other route.
* The 4m idea is not in the firmware or the setups; the PLL arrangement was discussed (70.000 MHz is an integer ratio from a 700 MHz PLL,
  which would conflict with the 2m use of PLLA) but not tested.

## Limitations

* **Mixed topologies.** The comparisons with earlier runs cross from the unscreened board to the screened one, and from no source
  pad to a screened pad. A difference of a few dB in the close-in spurs cannot be assigned to either.
* **Unfiltered 6m and 2m were run at 2 and 4 mA only**, and the filtered 6m and 2m runs read up to -22.6 and -23.5 dBm at the
  analyser (limit -25), so the 8 mA close-in figures in those runs are less certain than the rest.
* The 6m and 2m "10 dB" attenuator value (27.0 dB) is the earlier VHF measurement, not repeated in these chains; the absolute
  levels depend on it. The dBc figures do not.
* The pad sweeps are one measurement each, at 2 mA, with an ad-hoc script. The agreement between the three pads suggests they are
  all the same part, but that is an inference.
* Section "The 6m filter at 70 MHz" was measured on the old topology and the filter's loss may differ slightly in the screened one.
* The TinySA is not a calibrated instrument: relative numbers (dB, dBc) are more reliable than absolute dBm.
* No amplifier or antenna was connected.
