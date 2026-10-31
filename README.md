# Remote VHF/UHF beacon
A remote VHF/UHF beacon for 6m/2m/70cm using a Raspberry PI PICO-W and a SI5351 clock source

## Summary

MicroPython firmware for a Raspberry Pi Pico W driving an Adafruit Si5351 clock generator
(I2C) to produce amateur-radio beacons on three bands:

| Output | Band | Notes |
|--------|------|-------|
| CLK0 | 6m | Fundamental |
| CLK1 | 2m | Fundamental |
| CLK2 | 70cm | Third harmonic of a ~145 MHz carrier |

A web interface served by the Pico sets the beacon frequencies and modulation: carrier
on/off (including Morse ID), on/off duty cycle, and potentially FSK and WSPR.

The two RP2040 cores are split by role: core 0 handles Wi-Fi, the web server and
configuration; core 1 handles modulation timing, the Si5351 and Morse ID generation.

**Output filtering is required.** The Si5351 outputs square waves, so band-pass/low-pass
filtering must be added before connecting an antenna. Operating a beacon requires an
amateur radio licence and the appropriate permissions for your country.

See [PLAN.md](PLAN.md) for the full design, risks and milestones.

## Status

Working on the bench, without filters or amplifiers yet:

- Si5351 driver with all three outputs, PLL allocation and crystal ppm correction.
- Morse ID beacon that transmits one band at a time, scheduled from the Pico's second core.
- Web interface (Wi-Fi, password protected) for the station and band settings, a
  Transmit now button per band and an emergency stop.

Still to come: duty-cycle and FSK modes, WSPR, GPS time and calibration, and the filter and
amplifier hardware.

## Testing

* `python3 -m unittest discover -s tests/unit -v` runs the firmware's logic tests on the PC (no hardware).
* `tests/bench/` is an RF bench for the Si5351 outputs: it steps an output from the PC, measures it with a TinySA Ultra
  over USB, and stores the result with a description of the filters fitted, in `tests-results/`. A local web UI
  (`python3 tests/bench/serve.py`, port 3333, served from the PC, not the Pico) shows runs, compares them and plots trends.
  See [tests/bench/README.md](tests/bench/README.md).

## Setup

1. Flash MicroPython (v1.29 was used) onto the Pico W.
2. Copy `config.example.json` to `config.json` and fill in your Wi-Fi details and a web
   password of at least 8 characters. `config.json` is not committed.
3. Upload the project to the Pico (the MicroPico extension's **Upload project**). `main.py`
   starts the beacon and web server at power-up, with transmitting disabled until you tick
   **Transmit enabled** in the web interface.
