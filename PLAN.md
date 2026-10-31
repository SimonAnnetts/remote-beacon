# Remote Beacon – Plan

## Goal

A remote amateur-radio beacon for 6m, 2m and 70cm, built on a Raspberry Pi Pico W
(MicroPython) driving an Adafruit Si5351 clock generator over I2C. Frequencies and
modulation are configured through a web interface served by the Pico.

## Hardware

| Item | Notes |
|------|-------|
| Raspberry Pi Pico W | RP2040, Wi-Fi, dual core |
| Adafruit Si5351 breakout | 25 MHz crystal, 3 outputs (CLK0–CLK2), 2 PLLs, I2C |
| Band-pass filters | 6m and 2m: 3rd/4th-order band-pass. 70cm: SAW filter (built by the project owner) |
| Amplifiers | One Mini-Circuits PGA-103+ per output, after the filter (built by the project owner) |
| GPS module | ATGM336H (AT6558) with UART NMEA, 1PPS, ceramic antenna and u.FL port; see "GPS" below |

### Pins

| Function | Pins | Notes |
|----------|------|-------|
| Si5351 I2C | I2C0: SDA GP4, SCL GP5 | Hardware I2C peripheral, no bit-banging |
| GPS UART | UART1: TX GP8, RX GP9 | Hardware UART |
| GPS 1PPS | GP10 | Interrupt/capture input |

The Wi-Fi chip uses its own internal pins, so none of these conflict with it.

### Output allocation

| Output | Band | Frequency | Notes |
|--------|------|-----------|-------|
| CLK0 | 6m | 50.0–52.0 MHz | Direct fundamental |
| CLK1 | 2m | 144.0–146.0 MHz | Direct fundamental |
| CLK2 | 70cm | 430–440 MHz | **Third harmonic** of the CLK2 carrier (3 × f) |

The tuning range should cover the whole UK allocation of each band (the firmware range
limits are the band edges above; beacons would normally sit in the beacon segments).

For the 70cm output the CLK2 fundamental is the target divided by 3. Covering 430–440 MHz
needs a CLK2 range of 143.333–146.667 MHz, still inside the Si5351's 200 MHz limit. Note the
low end of that range is below 2m and the top end is above it, so the SAW filter must
reject the fundamental wherever it lands.

## Design considerations / risks

- **PLL sharing.** The Si5351 has two PLLs for three outputs, so two outputs share a PLL and
  retuning a PLL moves every output on it. See "PLL allocation" below for how this is handled.
- **Output ceiling.** The Si5351 is specified to 200 MHz (reportedly usable to ~225 MHz).
  ~145 MHz is within spec; MultiSynth divide ratios above 150 MHz would need integer dividers
  (not an issue at these frequencies).
- **Harmonic output on CLK2.** CLK2 is a square wave, rich in odd harmonics, which is what
  makes the 3rd-harmonic approach work. But the ~145 MHz fundamental is also present and is
  *in the 2m band*, so the 70cm SAW filter must strongly reject it (and the 5th/other
  harmonics). Filtering is a hard requirement before connecting an antenna.
- **SAW filter bandwidth.** Many off-the-shelf 433 MHz SAW filters pass only ~1 MHz or less,
  far narrower than the 10 MHz UK allocation. Pick a part whose passband covers the
  frequencies you intend to use, or accept a restricted 70cm range in firmware (configurable
  limits). SAW filters can also have spurious out-of-band responses; check the datasheet.
- **Amplifier range.** Check the PGA-103+ datasheet for gain and input limits at 50 MHz, the
  lowest frequency used, and make sure the filtered Si5351 output stays within its input
  rating. Amplifier harmonics are not removed by the filters that precede it, so a low-pass
  filter after the amp may still be needed depending on the measured result.
- **Crosstalk between outputs.** Measured on the bench with CLK0/1/2 all running (2 mA drive,
  10 dB pad): CLK1's third harmonic (3 x 144.5 = 433.5 MHz) appears on the CLK2 SMA at about
  -70 dBm, ~36 dB below the wanted 435 MHz signal (-33.9 dBm). It disappears when CLK1 is
  disabled. The third harmonic of any 2m frequency (432–438 MHz) lies inside the 70cm band, so
  neither the 2m filter nor the SAW filter can remove it. Mitigation: never transmit two bands
  at the same time (the scheduler time-multiplexes bands); improve layout/shielding if more
  isolation is needed. The reverse also happens: CLK2's 145.0 MHz carrier appears on the CLK1
  output at -58 dBm, ~30 dB below CLK1's 144.5 MHz (-27.5 dBm) and only 0.5 MHz away, in the 2m
  band itself, so no filter can remove it. Firmware must therefore enable only one output at a
  time. Optional hardware: switch each PGA-103+ supply from a spare GPIO so only the active
  band's amplifier is powered.
  Confirmed on the bench: with only CLK1 enabled, the 145 MHz leak disappears and the spurs
  around the carrier (seen at 144.1/144.3/144.6/144.8 MHz, -59 to -64 dBm with all three
  outputs running) fall to -70 dBm or lower (>=42 dB below the -27.5 dBm carrier, 10 dB pad).
- **PLL allocation.** A MultiSynth can only divide fractionally when the divider is 8 or
  more, so with a 600–900 MHz VCO anything above 112.5 MHz must use an integer divider (6 for
  112.5–150 MHz) and be tuned by moving its PLL. 2m (CLK1) and the 70cm carrier (CLK2) therefore
  each own a PLL (CLK1 on PLLA, CLK2 on PLLB) and cannot share. 6m (CLK0, below 112.5 MHz) is
  tuned with its fractional divider on PLLA and the driver recalculates it whenever CLK1
  retunes PLLA. PLL resolution gives ~4 Hz steps on 2m and ~12 Hz on 70cm.
- **Frequency accuracy.** A 25 MHz crystal at tens of ppm gives errors of kHz at VHF/UHF
  (tens of kHz when tripled to 70cm). Provide a calibration offset (ppm) setting in the config
  and consider GPS/1PPS or a TCXO/external reference later. Measured on the bench: the
  Adafruit board's crystal runs 151.3 ppm fast (checked against a TinySA Ultra whose 30 MHz
  cal output read correctly); this is applied as `CORRECTION_PPB` in `main.py` and the
  outputs were then on frequency. Expect further drift with temperature.
- **MicroPython timing.** Fine for Morse, on/off keying and slow FSK. WSPR symbol timing
  (~0.68 s) is fine, but tone accuracy depends on fractional-divider resolution, not software
  timing. Flash writes (saving config) stall the other core, so avoid saving mid-transmission.
- **Regulatory.** Operation requires an amateur licence and, where applicable, beacon
  approval (in the UK, a Notice of Variation) and use of the beacon segments of each band
  plan. The beacon must transmit its callsign/ID. Frequency/power limits should be enforced
  in firmware, not only by convention.

## Software architecture

Using the RP2040's two cores (MicroPython `_thread` runs the second thread on core 1):

**Core 0 – network and configuration**
- Wi-Fi connection (station mode, with an access-point fallback for first-time setup)
- Web server and REST/JSON API
- Configuration load/save (JSON file in flash)

**Core 1 – RF and timing**
- Modulation timing
- Si5351 driver
- Morse ID generation

Cores communicate through a small shared state object (the current config snapshot plus a
"config changed" flag) guarded by a lock, so the RF loop never blocks on network activity.

### Planned modules

| File | Purpose |
|------|---------|
| `main.py` | Start Wi-Fi/web on core 0, RF loop on core 1 |
| `si5351.py` | Si5351 I2C driver: PLL/MultiSynth maths, output enable, drive strength, ppm calibration |
| `beacon.py` | Per-band beacon scheduler and modulation (core 1) |
| `morse.py` | Text → Morse timing |
| `config.py` | Defaults, validation (band limits), persistence |
| `web.py` | HTTP server and JSON API (Basic auth) |
| `index.html` | Web UI: status, per-band settings and Transmit now buttons, network settings |
| `wifi.py` | Join the configured network, else a setup access point |
| `bringup.py` | Hardware bring-up test of the three Si5351 outputs |
| `wspr.py` | WSPR message encoding (later) |
| `clock.py` | NTP time sync and UTC status |

## Modulation modes

Implemented (mode names as in the web UI):

1. **Carrier** – unmodulated, for a set length.
2. **Morse ID (on/off)** – carrier gated by the output enable.
3. **Duty cycle** – on/off at a set period and percentage, for a set length.
4. **Morse ID (FSK)** – carrier always on; key-down at the band frequency, key-up a set
   shift (10 Hz to 5 kHz) above. A retune takes 1.5–3.8 ms.
5. **AM carrier (two levels)** and **Morse ID (AM tone)** – crude amplitude modulation by
   switching the output drive between two of 2/4/6/8 mA at 20–500 Hz. The drive write takes
   ~0.34 ms, so each half cycle must be at least 600 µs. Measured at 50 MHz (10 dB pad):
   -22 / -17 / -14 / -12 dBm for 2 / 4 / 6 / 8 mA, so 2 mA with 8 mA gives ~52% depth and the
   steps shrink at higher drive. Verified on 6m with 2/8 mA at 400 Hz: sidebands ~10 dB
   below the carrier, as predicted for ~52% depth. Depth on 2m and 70cm still to be measured.
6. **FM carrier (square-wave tone)** and **Morse ID (FM tone)** – the frequency alternates
   between the band frequency plus and minus a deviation (±100 Hz to 10 kHz) at 20–500 Hz. Each
   step is a single precomputed 8-byte I2C write (~0.39 ms on all three bands). The Morse ID
   version keys the tone and leaves the carrier on during key-up. Verified on 6m with ±3 kHz
   at 400 Hz: two clean lobes at the right spacing, ~30 dB below them in between. On 70cm the
   deviation is tripled by the harmonic, so the board sets the carrier deviation to a third.

7. **WSPR (6m only)** – type 1 message (callsign, 4-character locator, power) as 162 symbols
   of 4-FSK at 1.4648 baud, sent at second 1 of every N-th even UTC minute (`wspr_every`).
   The frequency setting is the dial (USB) frequency; the tones sit 1500 Hz above it. The
   encoder (`wspr.py`) is verified by the real `wsprd` decoder: messages decode correctly,
   including at about -14 dB SNR with added noise. The tones need millihertz tuning, which
   only the fractional-MultiSynth output (6m) can do (`Si5351.tuning_mhz`). Requires NTP
   time; `ntptime` sets the clock to whole seconds, so the start may be up to ~1 s off, which
   decoders tolerate.

   Not yet done: **WSPR on 2m and 70cm.** Those outputs are tuned by the PLL in ~4 Hz (2m) and
   ~12 Hz (70cm) steps, coarser than the 1.46 Hz tone spacing. A possible workaround is
   dithering between the two nearest steps at a few hundred Hz so the average lands on the
   right tone; to be tested with a real decoder.
   Crystal temperature drift (tens of ppm, i.e. ~1 kHz at 50 MHz) can push the signal out of
   the decoder's 200 Hz window, so the ppm correction should be re-checked when warm; GPS will
   fix this properly.

Each band is configured independently (enabled, frequency, mode, message, schedule).

## Web interface

- Status page: Wi-Fi state, time, per-band state (frequency, mode, on-air).
- Config page: per-band frequency (validated against band limits), enable/disable, mode,
  Morse text / duty cycle parameters, ppm calibration, Wi-Fi credentials.
- Master transmit enable / emergency stop.
- Simple authentication (shared password), since this controls an RF transmitter.

## GPS

Purpose: UTC time for WSPR (via NMEA over UART, with 1PPS for sub-microsecond edges) and a
frequency reference for calibrating the Si5351's crystal error.

- Chosen hardware: ATGM336H module (Zhongkewei AT6558, GPS + BeiDou, NMEA at 9600 baud by
  default, configured with CASIC commands rather than u-blox UBX). It has a ceramic patch
  antenna and a u.FL port for an external active antenna (add a u.FL to SMA pigtail if
  needed). It was chosen over a NEO-7M for cost, delivery time and the antenna connector;
  the NEO-7M would be the fallback if the PPS output is poor.
- Run from 3.3 V. Keep the module and antenna away from the Si5351 and amplifiers.
- PPS is only output once there is a fix; check the pin exists on the delivered board and
  check the pulse with a scope or counter.
- Calibration approach: count edges of a divided-down Si5351 output between 1PPS pulses over
  tens of seconds and store the result as a ppm offset. That corrects the Si5351 setting
  rather than locking the crystal. Measurement details (PWM counter or PIO) are to be worked
  out in the milestone.
- Software time keeping can fall back to NTP over Wi-Fi if no GPS is fitted.

## Bench results (Si5351 only, no filters or amplifiers)

TinySA Ultra, 10 dB attenuator + DC block in line (add 10 dB for levels at the chip), all
outputs at the default 2 mA drive, crystal correction 151.3 ppm applied. One output enabled at
a time unless stated.

| Output | Signal | Level | Notes |
|--------|--------|-------|-------|
| CLK0 | 50.2000 MHz | -23.9 dBm | Spurs <= -73 dBm (>= 49 dB down) |
| CLK0 | 100.4 / 150.6 / 251 MHz | -45 / -34 / -35 dBm | 2nd / 3rd / 5th harmonics, ~21 / 10 / 11 dB below the carrier |
| CLK1 | 144.5 MHz | -27.5 dBm | Spurs <= -70 dBm (all three outputs on: worse, see crosstalk) |
| CLK2 | 145.0 MHz fundamental | -28 dBm | Must be rejected by the SAW filter |
| CLK2 | 435.0 MHz (3rd harmonic) | -34.8 dBm | Only ~7 dB below the fundamental |
| CLK2 | 434.6 / 435.3 MHz | -68 dBm | ~33 dB below wanted; other spurs <= -88 dBm |

6m with a 9-pole Chebyshev low-pass filter (64 MHz cutoff) fitted: no harmonics visible above
-70 dBm from the carrier to 510 MHz (before the filter: 2nd/3rd/5th at -45/-34/-35 dBm), so the
3rd harmonic is now at least 36 dB lower. Carrier through the filter (10 dB pad): -27 dBm at 2 mA
and -15.7 dBm at 8 mA, i.e. ~5 dB and ~3.7 dB filter loss against -22/-12 dBm unfiltered; the
difference may be the source impedance changing with drive. 2 mA versus 8 mA is now 11.3 dB
apart (~57% AM depth). The analyser's noise floor appeared to rise from -90 to -70 dBm while
transmitting; the cause was the TinySA's auto attenuator stepping from 0 to 13 dB when a signal
appeared. With it fixed, the floor stays near -90 dBm.

Remaining spurs on 6m after the filter (carrier 51 MHz, fixed attenuation): at 2 mA (carrier
-27.6 dBm) spurs at ~36.4 MHz (-82 dBm), ~66.5 MHz (-82) and 458.8 MHz (-86), all about -54 to
-58 dBc; at 8 mA the strongest were 102 MHz (-71 dBm, the 2nd harmonic), 36.4 MHz (-73) and
458.8 MHz (-77, the 9th harmonic). The 36.4 and 66.5 MHz spurs are not harmonics of 51 MHz. They
could be Si5351 VCO products (with only 6m running the VCO is at 800 MHz, and 800/22 and 800/12
are 36.4 and 66.7 MHz), but that may be coincidence.
These readings are NOT yet trustworthy. With the 10 dB pad removed (carrier -5 dBm) the 102 MHz
spur rose 45 dB for a 9 dB rise in the carrier, so the TinySA front end overloads above roughly
-25 dBm, and its stepped sweep gives inconsistent levels when the span changes. To repeat on the
analogue analyser with its input kept low: check each spur with a 10 dB attenuator step (a real
spur moves 10 dB, an analyser-made one 20 dB or more), and move the carrier by 0.5 MHz to see how
each spur shifts (2nd harmonic by 1 MHz, 9th by 4.5 MHz, a fixed clock not at all).

(SUPERSEDED, kept for history: the wide-span spur readings in this paragraph, such as -32 dBc at +/-2 MHz, were artefacts of the
stepped sweep, and the out-of-band list missed the 725 MHz 5th harmonic. See docs/70cm-output-characterisation.md.)
70cm with the SAW filter fitted (carrier 145 MHz, so 435 MHz wanted; 10 dB pad; stepped TinySA, so
frequencies are only good to a few hundred kHz): at 2 mA the wanted signal is -34.7 dBm, the
145 MHz fundamental is -84 dBm (-49 dBc) and a spur at 580 MHz (4th harmonic) is -80 dBm (-45 dBc).
At 8 mA the wanted signal is -30 dBm, the fundamental -76 dBm (-46 dBc) and 579 MHz -83 dBm
(-53 dBc), with spurs at 433 and 437 MHz of -62 dBm (-32 dBc). So the SAW rejects the fundamental
by about 55 dB, but (a) the fundamental is still in the 2m band at about -46 to -49 dBc, (b) the
4th harmonic at 580 MHz needs a low-pass filter around 450-500 MHz, and (c) the +/-2 MHz spurs
are inside the SAW passband and must be fixed at the source. Ideas: put 70cm on PLLA instead of
PLLB to see whether the spurs follow the PLL, shift the carrier to see if they keep a fixed
offset, and try the only integer-ratio frequency (437.566 MHz) to see if they are fractional-N
products. The 435.2 MHz carrier reading is probably stepped-sweep error; confirm with a narrow span.

A full characterisation of the 70cm output with the SAW filter, including the SAW's response, spurs against
carrier frequency, out-of-band emissions and a PGA-103+ baseline, is in docs/70cm-output-characterisation.md.

Controlled re-measurement of 70cm over USB (tinysa.py helper in the scratchpad: fixed 30 kHz RBW,
25 kHz steps, 8 sweeps averaged, 8 mA, SAW fitted, 10 dB pad; repeatable to about 0.5 dB):
carrier 435.000 MHz at -29.7 dBm. The +/-0.1 MHz "spurs" are the analyser's own RBW skirt (their dBc
falls from -48 to -71 as RBW goes 30 -> 3 kHz), so nothing real is seen within +/-0.2 MHz down to
-71 dBc. Real spurs at about +/-0.65 MHz and +/-1.3 to 2 MHz are -53 to -58 dBc. PLLA versus PLLB:
PLLA is only 3-4 dB better at +/-0.65 MHz and the same elsewhere, so there is no reason to move 70cm
to PLLA. The earlier wide-span readings of -32 dBc spurs at +/-2 MHz and the 434.6/435.3 MHz spurs
were measurement artefacts of the stepped sweep; the wide-span 6m spur readings (36.4/66.5/458.8
MHz) should be re-checked the same way. The paragraph below is therefore superseded.

The 434.6/435.3 MHz spurs fall inside the SAW passband (133 kHz below and 100 kHz above the
145 MHz fundamental before tripling) and are probably PLLB fractional-N spurs (VCO/xtal =
34.8). Possible mitigation: choose the fractional denominator to move them.

## Test infrastructure

* **Unit tests** (`tests/unit/`): the firmware's logic runs on the PC against a simulated chip and clock, and the WSPR
  encoder is checked with the real `wsprd` decoder when it is installed.
* **Bench measurements** (`tests/bench/`): repeatable RF measurements of one output at a time, controlled over USB (Pico and
  TinySA Ultra). Each run stores its raw data and a description of the chain of filters between the Si5351 and the analyser in
  `tests-results/<output>/`. Tests: drive levels, **spur map** (spurs against carrier frequency), close-in spectra, wide
  spectrum (out-of-band emissions) and chain response (traces filters such as the 70cm SAW).
* **Results UI**: `python3 tests/bench/serve.py` on port 3333 (standard library, localhost, read-only). It lists runs, draws
  each test, overlays two runs and shows the change in every headline figure, and plots figures over time per setup, so a
  new filter can be compared with the old one. Nothing from the tests goes on the Pico or into its web interface.
* MicroPico's **Upload project** would copy these folders to the Pico, so `tests`, `tests-results` and `docs` are in
  `micropico.pyIgnore` in `.vscode/settings.json`.

## Milestones

1. ~~Verify dev environment (blink + hello world)~~ ✔
2. ~~Si5351 driver: probe over I2C, set a single frequency, check with a spectrum analyser~~ ✔
3. Three outputs: 6m, 2m, and 70cm via the 3rd harmonic; confirm PLL allocation and filtering. ✔ outputs and 3rd harmonic confirmed on a TinySA Ultra; filtering still to be built.
4. ~~Morse ID and on/off modulation on core 1~~ ✔ (one band at a time; key-click shaping to revisit with filters and amplifiers fitted)
5. ~~Wi-Fi + minimal web server on core 0 with config persistence~~ ✔
6. ~~Full web UI with per-band configuration and authentication~~ ✔ (Basic auth over plain HTTP: trusted LAN only)
7. ~~Duty-cycle and FSK modes~~ ✔, plus AM and FM modes and NTP time (`clock.py`) ✔
8. WSPR: ✔ on 6m (NTP time sync, encoding, symbol timing); 2m and 70cm to do.
9. GPS: UART/NMEA time, 1PPS capture, ppm calibration, safety limits, documentation.

## Open questions

- Exact frequencies/segments to use for each band (and licence conditions).
- SAW filter part number and passband (see risks).
- How the GPS frequency-error measurement is done (PWM counter or PIO).
