# 70cm output characterisation (CLK2, 3rd harmonic, with SAW filter)

> **Correction (later the same day).** The first version of this document said that, apart from the 145 MHz carrier and
> the 580 MHz 4th harmonic, nothing out of band was visible above the floor. **That was wrong.** The first campaign's
> peak finder never looked at the first and last point of each scan window, and the 5th harmonic of the carrier, at
> **725.0 MHz**, falls exactly on a window's first point. The bench framework joins its windows into one trace and found
> it: it is at -33 to -37 dBc, the **strongest out-of-band emission through the SAW**. It is a real signal (see section 3).
> The affected figures below have been corrected.

Measured 2026-10-31 (01:35-01:48), firmware at commit `7859547`.
Raw data: [`data/70cm-saw-2026-10-31.json`](data/70cm-saw-2026-10-31.json).
This was a one-off, hand-run campaign (script: [`../tests/bench/campaign_70cm_v0.py`](../tests/bench/campaign_70cm_v0.py)).
The measurements are now repeatable with the bench framework in [`../tests/bench/`](../tests/bench/README.md), and this
run's data has been imported into `tests-results/` so it can be compared with later runs in the bench web UI.

## Summary

| | Result |
|---|---|
| SAW passband (-3 dB) | **420.9 to 444.1 MHz** (23.2 MHz wide, centred on 432.5 MHz) |
| Passband flatness | about 1.6 dB p-p (-29.7 to -28.1 dBm) over 421-443 MHz; the whole 430-440 MHz band is inside it |
| SAW rejection | 42 to 50 dB below 415 MHz; 25 dB at 450 MHz; 36 dB at 455 MHz; 45 to 47 dB above 470 MHz |
| Wanted level leaving the SAW | -24.7 dBm (2 mA) to -19.2 dBm (8 mA) at 435 MHz |
| Strongest out-of-band signals, 5-800 MHz | **725 MHz (5th harmonic of the carrier) at -33 dBc (2 mA) / -36 dBc (8 mA)**; 145 MHz carrier at -47 to -52 dBc; 580 MHz (4th harmonic) at -53 to -54 dBc. Everything else is below the analyser's floor (about -54 dBc or lower) |
| Close-in spurs (within 5 MHz) | **depend strongly on the carrier frequency**: across 430-440 MHz the strongest spur ranges from **-57 dBc (best, 431.25 MHz) to -35 dBc (worst, 436.75 MHz)**; see the spur map below |
| Through a PGA-103+ (datasheet gain) | about -3 to +2.6 dBm out; far below its +21.5 dBm P1dB |

The close-in spurs are the main concern: the SAW is wide, so it cannot remove them, and their level changes by
over 20 dB across the band. The spur map (section 2) shows where they are and why.

## Setup

```
Pico W --I2C-- Si5351 (Adafruit, 25 MHz crystal, +151.3 ppm correction applied)
                 CLK2 --> SAW filter (part number unknown) --> 10 dB attenuator --> TinySA Ultra, low input
```

* CLK2 is on PLLB, MultiSynth divide 6. The carrier is 1/3 of the wanted frequency (about 145 MHz for 435 MHz); the
  wanted signal is its 3rd harmonic. Only CLK2 was enabled.
* TinySA Ultra `tinySA4_v1.4-200` (HW V0.4.6), controlled over USB. Attenuation fixed at 0 dB, LNA off.
* All levels below are **at the TinySA input, after the 10 dB attenuator**. Add 10 dB for the level leaving the
  SAW (assumes the attenuator is exactly 10 dB and ignores cable loss; about +/-1 dB).
* Drive: 8 mA for the SAW sweeps; 2, 4, 6 and 8 mA where stated.

## Method

1. **SAW response.** The carrier was stepped so that the wanted 3rd harmonic moved across 340-500 MHz (0.25 MHz steps over
   425-445 MHz, 1 MHz steps elsewhere). At each step the level was read at 1x, 2x, 3x and 4x the carrier (2 scans of a
   +/-150 kHz window, 41 points, RBW 10 kHz, averaged; the peak was taken).
2. **Close-in spectrum.** +/-5 MHz around the wanted signal, RBW 30 kHz, 401 points (25 kHz steps, so the step is smaller
   than the RBW), 6 sweeps averaged. Peaks within 150 kHz of the carrier are ignored: they are the analyser's own filter
   skirt (their level changes with RBW; checked at 30, 10 and 3 kHz).
3. **Wide spectrum.** 5-800 MHz in 18 windows of 450 points, RBW 100 kHz (100 kHz steps), 2 sweeps averaged. Floor about
   -102 dBm; peaks more than 12 dB above the floor were listed. With RBW equal to the step a narrow peak can read up to
   about 3 dB low.
4. **Level against drive** at 435 MHz.

Repeatability of the same sweep on the same setup was about 0.5 dB. The TinySA is not a calibrated instrument: use the
**relative** numbers (dB, dBc) with more confidence than the absolute dBm.

## 1. SAW filter

![SAW response, 340-500 MHz](img/70cm-saw-wide.svg)

![SAW passband detail](img/70cm-saw-passband.svg)

Passband reference (median over 421-443 MHz): -28.7 dBm at the TinySA. Edges, by interpolation:

| Level below passband | Lower edge, MHz | Upper edge, MHz | Width, MHz |
|---|---|---|---|
| 3 dB | 420.9 | 444.1 | 23.2 |
| 10 dB | 420.5 | 445.8 | 25.2 |
| 20 dB | 420.0 | 448.3 | 28.3 |
| 30 dB | 419.3 | 451.5 | 32.2 |
| 40 dB | 415.2 | 459.5 | 44.3 |

The lower edge is very steep (20 dB between 420 and 421 MHz) and was sampled at 1 MHz steps only, so the lower-edge figures
are good to about +/-0.5 MHz. The upper edge is much gentler.

Rejection (dB below the passband):

| Frequency, MHz | 340 | 360 | 380 | 400 | 410 | 415 | 420 | 445 | 447 | 450 | 455 | 460 | 470 | 480 | 500 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Rejection, dB | 50 | 50 | 49 | 47 | 45 | 42 | 20 | 7 | 16 | 25 | 36 | 41 | 46 | 47 | 46 |

* There is a narrow bump at about **416 MHz** (only 31 dB of rejection) and a smaller one near 468 MHz: typical SAW
  out-of-band responses.
* Insertion loss is **not known**. A comparison with an earlier unfiltered reading suggests it is small, but that reading
  used a stepped sweep and is not reliable. Measuring 435 MHz with the SAW bypassed, same setup, would settle it.
* This measures the SAW together with the source (the Si5351's 3rd-harmonic amplitude, assumed smooth with frequency).

Other orders of the carrier through the SAW, 8 mA:

![Other orders through the SAW](img/70cm-saw-other-orders.svg)

* 1x carrier (113-167 MHz): about -78 dBm (-82 to -75), i.e. about -49 dBc against the wanted signal.
* 2x carrier: at or below the analyser floor (about -95 dBm).
* 4x carrier at 435 MHz: -84.4 dBm, i.e. about -56 dBc.

## 2. Close-in spurs

![Spurs against frequency](img/70cm-spurs-vs-frequency.svg)

Strongest spurs within +/-5 MHz (offset from the wanted signal in MHz, level in dBc):

| Wanted, MHz | Drive | Carrier at TinySA | Strongest spurs |
|---|---|---|---|
| 435.00 | 2 mA | -34.1 dBm | +/-0.65: -53; +/-1.50: -57; +/-0.33: -57 |
| 435.00 | 4 mA | -31.7 dBm | +/-0.65: -53; +/-1.48: -55 |
| 435.00 | 6 mA | -32.2 dBm | +/-0.65: -53; +/-1.4 to 1.6: -57 |
| 435.00 | 8 mA | -29.8 dBm | +/-0.65: -52; 0.33: -57 |
| 432.45 | 2 mA | -34.1 dBm | -1.15: -49; -1.32: -52; 1.52: -54 |
| 432.45 | 8 mA | -29.9 dBm | +/-1.50: -47; -1.32: -48; -1.15: -49 |
| 438.00 | 2 mA | -31.6 dBm | **+/-0.88: -38**; 4.03: -58 |
| 438.00 | 8 mA | -28.9 dBm | **+/-0.88: -38**; 4.03: -50; 0.62: -55 |

* The spur pattern and level **change a great deal with the carrier frequency**, and barely with drive. At 438 MHz the
  spurs at +/-0.88 MHz are 14 dB worse than at 435 MHz. This is the SAW being irrelevant: all of these are well inside its
  passband.
* The cause is almost certainly the PLL's fractional divider (VCO = 6 x carrier = 2 x the wanted frequency; the multiplier
  is 34.79 at 435 MHz, 34.59 at 432.45 MHz and 35.03 at 438 MHz). A simple model (spurs where a multiple of the
  fractional part lands near a whole number) predicts the +/-0.88 MHz spur at 438 MHz (twice the 0.43 MHz distance from
  the integer-ratio frequency 437.57 MHz) and the +/-0.65 MHz spur at 435 MHz, but does not account for all the spurs
  seen at 432.45 MHz. Treat it as a guide, not an explanation.
* PLLA against PLLB made only a 3-4 dB difference at 435 MHz in an earlier test. See PLAN.md.
* The beacon's default 70cm frequency (432.45 MHz) has spurs of about -47 to -49 dBc.

### Spur map

The bench framework (`tests/bench`, run `2026-10-31T02-28-15__70cm-saw-unknown-10dB`) measured the whole +/-5 MHz spectrum at
every 0.25 MHz from 430 to 440 MHz, at 2 mA and 8 mA (3 sweeps averaged, RBW 30 kHz, 25 kHz steps). The strongest spur at
each frequency:

![Spur map](img/70cm-spur-map.svg)

| | 2 mA | 8 mA |
|---|---|---|
| Worst across the band | -34.7 dBc at 436.75 MHz | -36.0 dBc at 436.75 MHz |
| Median | -49.4 dBc | -45.8 dBc |
| Best | -56.9 dBc at 431.25 MHz | -55.3 dBc at 431.25 MHz |
| Frequencies with the strongest spur at or below -50 dBc | 19 of 41 | 6 of 41 |

* **Two regions are bad.** From about 436 to 438.5 MHz the strongest spur is -35 to -43 dBc, and there is a smaller peak near
  434.25 MHz (-41 to -44 dBc). The cleanest region is 430.75 to 432 MHz and around 435.0 MHz.
* **Lower drive is cleaner** (relative to the wanted signal) over most of the band: typically 4 to 9 dB better at 2 mA than at
  8 mA between 430 and 433 MHz and above 439 MHz. In the worst region (436 to 438.5 MHz) the two are within about 1 dB, and
  8 mA is very slightly better at 436.75 MHz. In absolute terms the spurs are lower at 2 mA by more than the 5 dB difference in
  the wanted level (for example at 432.5 MHz: -88 dBm at 2 mA against -76 dBm at 8 mA, at the analyser).
* **The beacon's default 432.45 MHz** is at -53 dBc (2 mA) but -46 to -47 dBc (8 mA).

**Why: fractional-N spurs.** The carrier at 145 MHz comes from a PLL running at 6 x the carrier (870 MHz). Its multiplier is
the crystal's 25.004 MHz multiplied by 34.8, a fractional number, and a fractional divider generates spurs. The pattern is
predictable: with the VCO at exactly 35 x the crystal (an integer ratio) there should be no fractional-N spurs, and that
happens at a wanted frequency of 437.566 MHz. Near that frequency the strongest spur is at **exactly twice the distance from it**:

| Wanted, MHz | Distance from 437.566 | Predicted spur offset (2 x distance) | Measured strongest spur |
|---|---|---|---|
| 436.75 | 0.82 | 1.63 | +/-1.625 MHz at -36 dBc |
| 437.00 | 0.57 | 1.13 | +/-1.125 MHz at -36 dBc |
| 437.25 | 0.32 | 0.63 | +/-0.625 MHz at -38 dBc |
| 437.75 | 0.18 | 0.37 | +/-0.375 MHz at -40 dBc |
| 438.00 | 0.43 | 0.87 | +/-0.875 MHz at -38 dBc |
| 438.25 | 0.68 | 1.37 | +/-1.375 MHz at -36 dBc |
| 438.50 | 0.93 | 1.87 | +/-1.875 MHz at -39 dBc |

At 437.50 MHz, 0.07 MHz from the integer ratio, the strong spurs disappear (-49 dBc), as the model says they should. A weaker
spur at +/-4.2 MHz (-50 dBc) is present at every frequency and moves slowly with the carrier; it is probably a different
mechanism. The raised spurs near 436 and 434.25 MHz are probably the same effect at other simple fractions of the multiplier (the fraction is
about 7/8 near 436 MHz), but that has not been checked.

**What can be done about it:**
1. Choose the beacon frequency with the map: 431.25 MHz (-55 to -57 dBc) is the cleanest; 435.0 MHz is good (-52 dBc).
   Anywhere between 436 and 438.5 MHz is poor.
2. Prefer a lower drive, and recover the power in the amplifier.
3. The default 432.45 MHz segment frequency is acceptable at 2 mA and is the first thing to re-check at 8 mA.
4. A frequency near an integer PLL ratio (437.50 MHz here) is a good choice where it is allowed: the nearby strong spurs vanish.
   The same idea applies to every band: the cleanest frequencies are those whose VCO is close to a whole multiple of the crystal.
5. The ppm correction moves the integer-ratio frequency (the crystal is 151 ppm fast), so the clean frequency must be
   recomputed if the crystal's calibration changes.

## 3. Out-of-band emissions (5-800 MHz)

Three signals, other than the wanted one and its close-in family, rise more than 12 dB above the floor:

| Signal | 2 mA | 8 mA |
|---|---|---|
| **725.0 MHz (5x carrier)** | **-33 dBc** (-67.4 dBm at the analyser) | **-36 dBc** (-66.4 dBm) |
| 145.0 MHz (carrier fundamental, inside the 2m band) | -51 dBc | -47 dBc |
| 580.0 MHz (4x carrier) | -53 dBc | -54 dBc |

Everything else from 5 to 800 MHz is below about -90 dBm, i.e. at least 54 dB below the wanted signal. The 2nd harmonic of the
carrier (290 MHz) is not visible. The TinySA's low input stops at 800 MHz, so the 870 MHz signal (2 x 435 MHz, the VCO
frequency) and everything above is **not covered**.

**The 725 MHz signal is real, not an analyser artefact.** With the Si5351 output off there is nothing at 725 MHz (only noise at
-95 to -108 dBm). The TinySA corrects its readings back to its input, so a real signal reads the same whatever attenuation
the analyser itself adds, while a spur the analyser creates from the strong wanted signal falls as that attenuation is
raised. At 8 mA with 0, 10 and 20 dB of analyser attenuation the readings were:

| Analyser attenuation | 145 MHz | 435 MHz (wanted) | 580 MHz | 725 MHz |
|---|---|---|---|---|
| 0 dB | -77.5 | -29.2 | -83.9 | **-66.0** |
| 10 dB | -77.0 | -29.2 | -85.9 | **-66.0** |
| 20 dB | -77.5 | -29.7 | -83.9 | **-66.0** |

Every signal, 725 MHz included, stays where it is. (The wide-spectrum test now repeats this check automatically for the
strongest out-of-band signals it finds, and marks each one "real signal" or "made by the analyser".)

**Why it is so strong:** the carrier is a square wave, whose 5th harmonic is only 4.4 dB below the 3rd (the wanted signal),
and this SAW does little to stop it. The response test (procedure v2, run `2026-10-31T02-51-44`) reads the 5th order as the
wanted frequency is stepped, which traces what the SAW does to the carrier's 5th harmonic from 567 to 790 MHz (wanted
frequencies 340-474 MHz). At 8 mA, as read at the analyser:

| Wanted frequency, MHz | 5x carrier, MHz | 5th harmonic, dBm | Relative to the wanted signal |
|---|---|---|---|
| 425 | 708 | -67.4 | -39 dBc |
| 430 | 717 | -67.7 | -39 dBc |
| 435 | 725 | -66.2 | -37 dBc |
| 440 | 733 | -66.8 | -38 dBc |
| 445 | 742 | -69.8 | -35 dBc (the wanted signal is already falling) |

* Across the whole 70cm band the 5th harmonic is **-37 to -40 dBc** (worst at 436.25 MHz).
* It is **flat at about -67 dBm (-65 to -70)** wherever it falls between 567 and 790 MHz. The SAW does not discriminate in this
  range, so there is no "bad frequency" to avoid: it is a general weakness of the filter at these frequencies.
* Taking the 5th harmonic as 4.4 dB below the 3rd at the source (ideal square wave), the SAW attenuates it by only about 34 dB,
  against 46-50 dB for the 340-500 MHz range of section 1. That is an estimate; the source's harmonic ratio was not measured.

## 4. Level against drive (435 MHz)

| Drive | Wanted at TinySA | Wanted leaving the SAW | 145 MHz fundamental at TinySA | 145 MHz relative to wanted |
|---|---|---|---|---|
| 2 mA | -34.7 dBm | -24.7 dBm | -86.5 dBm | -52 dBc |
| 4 mA | -32.2 dBm | -22.2 dBm | -81.0 dBm | -49 dBc |
| 6 mA | -32.7 dBm | -22.7 dBm | -78.5 dBm | -46 dBc |
| 8 mA | -29.2 dBm | -19.2 dBm | -77.0 dBm | -48 dBc |

The wanted 3rd harmonic is **not monotonic** with drive (6 mA is lower than 4 mA), unlike the fundamental on 6m. Between
repeats at the same setting the carrier moved by about 0.5 dB (8 mA: -29.2, -29.8, -29.9 dBm).

## 5. Baseline for a PGA-103+ stage

PGA-103+ datasheet (Mini-Circuits, Rev C, 5 V supply), gain interpolated between the tabulated points:

| | 145 MHz | 435 MHz | 580 MHz | 725 MHz |
|---|---|---|---|---|
| Gain, dB (interpolated) | 25.3 | 21.8 | 20.3 | 18.9 |

Other datasheet figures at 400 MHz: P1dB +21.5 dBm, OIP3 +39 dBm, noise figure 0.5 dB, input return loss 11.3 dB. Absolute
maximum input +21 dBm CW. Gain is specified at -25 dBm input. Supply 5.0 V (4.8-5.2 V), 97 mA typical, with an input
DC block and an RF-choke bias tee on the output (datasheet Fig. 2a/2b).

Predicted at the amplifier output, assuming the amplifier is linear (it is, by a wide margin: the input is 40 dB below its
maximum):

| Drive | Into the PGA | Out at 435 MHz | 145 MHz spur | 580 MHz spur | **725 MHz spur** | Worst close-in spur at 435 MHz |
|---|---|---|---|---|---|---|
| 2 mA | -24.7 dBm | **-2.9 dBm** | -48 dBc | -55 dBc | **-36 dBc** | -53 dBc |
| 8 mA | -19.2 dBm | **+2.6 dBm** | -44 dBc | -56 dBc | **-39 dBc** | -52 dBc |

* The fundamental gets **worse** by 3.5 dB relative to the wanted signal because the amplifier has more gain at 145 MHz;
  the 4th and 5th harmonics get 1.5 and 2.9 dB better. The close-in spurs are unchanged.
* At 8 mA the 725 MHz signal would be about -37 dBm at the amplifier output, 40 dB below the wanted signal: that is the
  strongest unwanted signal outside the band, and it needs filtering.
* The output is only about 0.5 to 1.8 mW. To reach, say, +20 dBm you would need about 17 dB more gain and a harmonic filter
  after it. The amplifier's own harmonic output is not specified in the datasheet and should be measured.
* The PGA-103+ is a wideband amplifier: it will amplify the 145 MHz leak, the 580 MHz harmonic and the close-in spurs along
  with the wanted signal. Any extra filtering is best placed *before* it for the 145 MHz leak and *after* it for harmonics.

## 6. What this suggests

1. **Choose the 70cm frequency with the close-in spurs in mind.** A "spur map" (strongest spur against carrier frequency over
   430-440 MHz in small steps) would show which frequencies are clean. This is a software-only test.
2. **The SAW does not help with spurs near the carrier**, nor much with the 145 MHz leak (about 50 dB), and it is weak near
   725 MHz. A high-pass in front of the SAW would help the 145 MHz leak.
3. **A low-pass filter is now the most important addition.** The 725 MHz 5th harmonic (-33 to -37 dBc) and the 580 MHz 4th
   harmonic (-53 dBc) both need to go: a low-pass with a cutoff of about 470 MHz, with enough rejection at 580 and 725 MHz,
   placed after the SAW (and after the amplifier too, to catch the amplifier's own harmonics).
4. Decide what spurious limit applies to the beacon before judging these numbers; they are in dBc relative to the
   wanted signal, not absolute.

## Limitations

* One SAW filter of unknown type, one board, room temperature. The measurements are repeatable: two full bench runs 23 minutes
  apart agree to within 0.8 dB on all 18 headline figures (the SAW bandwidth to 0.03 MHz, the spur map frequency by frequency to a
  mean of 0.5 dB, with a worst single point of 2.9 dB), so a change of a couple of dB between runs is a real change. The first
  campaign's out-of-band list had the window-edge blind spot described at the top.
* The baseline for this setup is run `2026-10-31T02-51-44__70cm-saw-unknown-10dB` (all five tests, procedure versions in the
  file); the earlier run `02-28-15` used wide-spectrum v1 and response v1 (no 5th order, no out-of-band checks).
* TinySA readings are not calibrated; absolute levels are +/-2 dB or worse. The pad is assumed to be exactly 10 dB.
* The TinySA's low input stops at 800 MHz.
* The SAW's insertion loss and the unfiltered baseline were not measured in this run.
* The amplifier figures are calculated from the datasheet, not measured.
