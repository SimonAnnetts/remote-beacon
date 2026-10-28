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

Planning. The development environment (VS Code + MicroPico) has been verified.
