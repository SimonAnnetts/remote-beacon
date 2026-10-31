# 70cm output characterisation (CLK2, 3rd harmonic, with SAW filter)

Measured 2026-10-31 (01:35-01:48), firmware at commit `7859547`.
Raw data: [`data/70cm-saw-2026-10-31.json`](data/70cm-saw-2026-10-31.json).
First-version measurement scripts: [`../tools/bench/`](../tools/bench/) (`campaign_70cm_v0.py`, `tinysa.py`, `pico.py`).

## Summary

| | Result |
|---|---|
| SAW passband (-3 dB) | **420.9 to 444.1 MHz** (23.2 MHz wide, centred on 432.5 MHz) |
| Passband flatness | about 1.6 dB p-p (-29.7 to -28.1 dBm) over 421-443 MHz; the whole 430-440 MHz band is inside it |
| SAW rejection | 42 to 50 dB below 415 MHz; 25 dB at 450 MHz; 36 dB at 455 MHz; 45 to 47 dB above 470 MHz |
| Wanted level leaving the SAW | -24.7 dBm (2 mA) to -19.2 dBm (8 mA) at 435 MHz |
| Strongest out-of-band signals, 5-800 MHz | 145 MHz fundamental at -45 to -52 dBc; 580 MHz (4th harmonic) at about -53 dBc. Everything else is below about -54 dBc (analyser floor limited) |
| Close-in spurs (within 5 MHz) | **depend strongly on the carrier frequency**: -52 to -53 dBc at 435 MHz, -47 to -49 dBc at 432.45 MHz, **-38 dBc at 438 MHz** |
| Through a PGA-103+ (datasheet gain) | about -3 to +2.6 dBm out; far below its +21.5 dBm P1dB |

The close-in spurs are the main concern: the SAW is wide, so it cannot remove them, and their level changes by
15 dB across the band.

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

## 3. Out-of-band emissions (5-800 MHz)

Only two signals other than the wanted one and its close-in family rise more than 12 dB above the floor:

| Signal | 2 mA | 8 mA |
|---|---|---|
| 145.0 MHz (carrier fundamental, inside the 2m band) | -50 dBc | -46 dBc |
| 580.0 MHz (4x carrier) | -53 dBc | -54 dBc |

Everything else from 5 to 800 MHz is below about -90 dBm, i.e. at least 54 dB below the wanted signal. The 2nd harmonic
of the carrier (290 MHz) and the 5th (725 MHz) are not visible. The TinySA's low input stops at 800 MHz, so the 870 MHz
signal (2 x 435 MHz, the VCO frequency) and everything above is **not covered**.

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

| | 145 MHz | 435 MHz | 580 MHz |
|---|---|---|---|
| Gain, dB (interpolated) | 25.3 | 21.8 | 20.3 |

Other datasheet figures at 400 MHz: P1dB +21.5 dBm, OIP3 +39 dBm, noise figure 0.5 dB, input return loss 11.3 dB. Absolute
maximum input +21 dBm CW. Gain is specified at -25 dBm input. Supply 5.0 V (4.8-5.2 V), 97 mA typical, with an input
DC block and an RF-choke bias tee on the output (datasheet Fig. 2a/2b).

Predicted at the amplifier output, assuming the amplifier is linear (it is, by a wide margin: the input is 40 dB below its
maximum):

| Drive | Into the PGA | Out at 435 MHz | 145 MHz spur | 580 MHz spur | Worst close-in spur at 435 MHz |
|---|---|---|---|---|---|
| 2 mA | -24.7 dBm | **-2.9 dBm** | -48 dBc | -55 dBc | -53 dBc |
| 8 mA | -19.2 dBm | **+2.6 dBm** | -44 dBc | -56 dBc | -52 dBc |

* The fundamental gets **worse** by 3.5 dB relative to the wanted signal because the amplifier has more gain at 145 MHz;
  the 4th harmonic gets 1.5 dB better. The close-in spurs are unchanged.
* The output is only about 0.5 to 1.8 mW. To reach, say, +20 dBm you would need about 17 dB more gain and a harmonic filter
  after it. The amplifier's own harmonic output is not specified in the datasheet and should be measured.
* The PGA-103+ is a wideband amplifier: it will amplify the 145 MHz leak, the 580 MHz harmonic and the close-in spurs along
  with the wanted signal. Any extra filtering is best placed *before* it for the 145 MHz leak and *after* it for harmonics.

## 6. What this suggests

1. **Choose the 70cm frequency with the close-in spurs in mind.** A "spur map" (strongest spur against carrier frequency over
   430-440 MHz in small steps) would show which frequencies are clean. This is a software-only test.
2. **The SAW does not help with spurs near the carrier**, nor much with the 145 MHz leak (about 50 dB). A tighter
   band-pass or a high-pass in front of the SAW would help the 145 MHz leak.
3. **The 580 MHz 4th harmonic** (-53 dBc) wants a low-pass filter (cutoff about 470-500 MHz) after the amplifier.
4. Decide what spurious limit applies to the beacon before judging these numbers; they are in dBc relative to the
   wanted signal, not absolute.

## Limitations

* One SAW filter of unknown type, one board, one run, room temperature.
* TinySA readings are not calibrated; absolute levels are +/-2 dB or worse. The pad is assumed to be exactly 10 dB.
* The TinySA's low input stops at 800 MHz.
* The SAW's insertion loss and the unfiltered baseline were not measured in this run.
* The amplifier figures are calculated from the datasheet, not measured.
