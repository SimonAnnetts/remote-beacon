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
| `web.py` | HTTP server, API, HTML UI |
| `wspr.py` | WSPR message encoding (later) |

## Modulation modes

1. **Carrier** – unmodulated, continuous.
2. **OOK / Morse** – carrier on/off keyed with the station ID or a configurable message.
3. **Duty cycle** – on/off with a variable duty cycle and period (simple identifiable beacon).
4. **FSK** – shift the output frequency between two (or more) tones, e.g. a CW-style
   FSK ID or slow data.
5. **WSPR** (stretch) – 4-FSK, 162 symbols at ~1.4648 baud, time-synchronised to even
   2-minute boundaries (needs NTP time over Wi-Fi). Encoding must be implemented on-device.

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

## Milestones

1. ~~Verify dev environment (blink + hello world)~~ ✔
2. ~~Si5351 driver: probe over I2C, set a single frequency, check with a spectrum analyser~~ ✔
3. Three outputs: 6m, 2m, and 70cm via the 3rd harmonic; confirm PLL allocation and filtering. ✔ outputs and 3rd harmonic confirmed on a TinySA Ultra; filtering still to be built.
4. Morse ID and on/off modulation on core 1.
5. Wi-Fi + minimal web server on core 0 with config persistence.
6. Full web UI with per-band configuration and authentication.
7. Duty-cycle and FSK modes.
8. WSPR (NTP time sync, encoding, symbol timing).
9. GPS: UART/NMEA time, 1PPS capture, ppm calibration, safety limits, documentation.

## Open questions

- Exact frequencies/segments to use for each band (and licence conditions).
- SAW filter part number and passband (see risks).
- How the GPS frequency-error measurement is done (PWM counter or PIO).
