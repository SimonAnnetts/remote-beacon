# Bench measurements

Repeatable RF measurements of one Si5351 output at a time, controlled from this PC: the Pico steps the
output over USB, a TinySA Ultra measures it over USB, and the results are stored with a full description
of what was fitted between the two.

```
Pico W --I2C-- Si5351 CLKn --> [your filters / amplifier / attenuator] --> TinySA low input
   ^ USB (/dev/ttyACM0)                                                       ^ USB (/dev/ttyACM1)
   +---------------------------------- this PC ------------------------------+
```

## Running a measurement

```
python3 tests/bench/run.py --list                                   # tests and setups
python3 tests/bench/run.py --setup 70cm-saw-unknown-10dB --dry-run  # what would run, and how long
python3 tests/bench/run.py --setup 70cm-saw-unknown-10dB            # everything (about 25 minutes)
python3 tests/bench/run.py --setup 70cm-saw-unknown-10dB --tests spur_map,drive_levels
python3 tests/bench/run.py --setup 70cm-saw-unknown-10dB --set spur_map.step=0.5 --note "re-seated the SAW"
```

Before you start:
* Connect the output under test, through whatever filters are in the setup, to the TinySA **low input**, with the
  attenuator the setup names. Keep the signal at the analyser below about -25 dBm (the TinySA's front end
  distorts above that), and the attenuation of the analyser fixed.
* **The beacon is stopped while a run is in progress** and the Pico is rebooted at the end, so its web interface comes
  back. Only the output named in the setup is ever enabled, one frequency at a time. If a run fails, the output is
  still switched off and the TinySA's own settings are restored.

| Test | What it measures |
|---|---|
| `drive_levels` | Level of the wanted signal and its other orders at 2, 4, 6 and 8 mA |
| `spur_map` | The whole close-in spectrum (and the strongest spur) at every carrier frequency across the band, per drive |
| `spectrum_close` | Close-in spectra at chosen frequencies and drives |
| `spectrum_wide` | 5 MHz to 790 MHz at a resolution that cannot miss a narrow signal: harmonics and other out-of-band emissions |
| `response` | The chain's response: the wanted frequency is stepped over a wide range and the level read at each order of the carrier (for 70cm this traces the SAW filter) |

Each measurement has defaults for each output (`6m`, `2m`, `70cm`). Override a parameter with
`--set <test>.<param>=<json value>`; `--dry-run` shows the parameters.

## Consistency: getting comparable results

The aim is to change **one thing** (a filter, an amplifier, a PLL setting in the firmware) and see what that did. For that:

* **Same procedure.** Each measurement has a `VERSION` and fixed defaults per output. Both are stored in every result, and the
  **Compare** page opens with a "like-for-like?" check that lists any difference in procedure version or parameter. If it says
  no, differences in the figures may come from the method. Change a default only for a reason, and bump the `VERSION` when you do.
* **Always run everything** (`--tests all`, the default) for a baseline and for each change, so a comparison covers every figure.
* **Same setup naming.** The setup `id` is `<output>-<what is fitted>-<pad>`, for example `70cm-saw-unknown-10dB`. When you change
  a filter, copy the file, change the `chain` and the `id`, and leave everything else alone. Keep the cabling and the analyser's
  attenuation the same.
* **Record what changed in the firmware.** Each run stores the git commit (and whether the working tree was dirty) and the crystal
  correction, so a PLL or driver change (for instance for WSPR on 2m or 70cm) shows up in the conditions of the run.
* **Check the reference.** Each run measures a reference level at the start and the end; a drift of more than 1 dB is reported.
* The **spur map** is the best before-and-after test for anything that changes the PLL: it shows, frequency by frequency, whether a
  spur moved or got stronger.

## The three outputs

The same tests run on `6m` (CLK0), `2m` (CLK1) and `70cm` (CLK2). The channel, PLL and harmonic number come from the firmware's
own `config.BANDS`, so the rig always commands what the beacon would. A few things differ:

| | 6m (CLK0) | 2m (CLK1) | 70cm (CLK2) |
|---|---|---|---|
| Wanted signal | the carrier itself | the carrier itself | 3rd harmonic of a ~145 MHz carrier |
| How the Si5351 makes it | fractional divider on a fixed 800 MHz VCO | PLL moved (VCO = 6 x carrier), integer divider | PLL moved, as 2m |
| Typical level at the analyser | **strong**: about -24 dBm at 2 mA, -16 dBm at 8 mA (with a 10 dB pad) | same | weak: about -34 / -29 dBm |
| Close-in window | +/-2 MHz | +/-2 MHz | +/-5 MHz |
| Spur mechanism seen | different: no whole-PLL fractional pattern to expect | like 70cm but offsets are 1/3 as far from the carrier | PLL fractional-N, see docs/70cm-output-characterisation.md |

* **Analyser overload.** On 6m and 2m the wanted signal is the strong fundamental. Before measuring, the runner reads the level at
  the highest drive the plan uses and **refuses to continue above -25 dBm** (the TinySA's front end then makes its own spurs).
  Add attenuation and say so in the setup, restrict the drives (`--set spur_map.drives=[2]`), or accept it with `--force`.
* **Response sweeps** step over 100-112.5 MHz, where the Si5351 cannot produce a frequency (below 100 MHz it divides an 800 MHz VCO, from
  113 MHz it moves the PLL). A test checks every plan against the real driver on the PC.
* A **low-pass** filter (the 6m one) has no lower -3 dB edge, so the response reports `lowpass_cutoff_mhz` instead of a bandwidth.
* The close-in tests ignore anything within 100 kHz of the carrier: the analyser's own filter skirt is indistinguishable from a spur there.
* **6m and 2m have not yet been run on the real hardware**, only in simulation with the real driver (`tests/unit/test_bench.py`).
  Move the TinySA to the output (with its filter and attenuator) and use the matching setup; there is one for 6m, and `2m` needs one describing
  what is fitted.

## Describing what you changed: setups

A *setup* is a small JSON file in `setups/` that describes the chain between the Si5351 output and the analyser. It is
copied into every result, so a result always says what was fitted. To test a different filter, copy an existing file,
change the `id`, the `chain` and the notes, and run with `--setup <new id>`:

```json
{
  "id": "70cm-lpf-500MHz-after-saw",
  "output": "70cm",
  "description": "SAW followed by a 500 MHz low-pass",
  "chain": [
    {"kind": "filter", "name": "SAW filter", "part": "unknown"},
    {"kind": "filter", "name": "5-pole low-pass, 500 MHz", "notes": "home built"},
    {"kind": "attenuator", "db": 10}
  ],
  "analyser": {"type": "tinysa", "port": "/dev/ttyACM1", "attenuation_db": 0, "lna": false}
}
```

`kind` is one of `filter`, `amplifier`, `attenuator`, `cable`, `other`. Attenuators and cables **after the last filter or
amplifier** add up to the "pad" that is added back when the UI shows the level leaving the chain.

## Looking at the results

```
python3 tests/bench/serve.py          # http://127.0.0.1:3333
```

A local, read-only web UI (standard library only, served from this PC, never from the Pico). **Runs** lists everything in
`tests-results/`; a run page shows the test conditions and a chart for each test (including the spur-map heat map);
**Compare** overlays two runs and shows the change in every headline figure; **Trends** plots a figure over time, one
line per setup. It reads the files on every request, so you can watch a run fill in while it is going.

## Results

`tests-results/<output>/<date-time>__<setup id>.json`: one file per run, holding the setup, the environment (git
commit, MicroPython and TinySA versions, crystal correction), the parameters and the **raw data** of each test, and a
`status` (`complete`, `incomplete` or `failed`). Derived figures (bandwidths, worst spurs, rejection...) are **not**
stored: `benchlib/metrics.py` computes them when a result is viewed, so improving the analysis improves old runs too.
The result is saved after every test, so a failed run keeps what it measured.

`legacy_import.py` converted the first hand-run campaign (`docs/data/70cm-saw-2026-10-31.json`) into this format.

## Things that matter for repeatable numbers

* The TinySA sweeps in **steps**. Keep the step no wider than the RBW (the tests choose this for you), or a narrow signal
  can fall between points and read low.
* Its low input overloads above about -25 dBm. The runner reads the level at the highest drive first and refuses to go on above
  that. Raising the analyser's own attenuation does not move the reading of a **real** signal (the TinySA corrects back to its
  input), but a spur the analyser makes itself falls: `spectrum_wide` uses this to mark each strong out-of-band signal "real
  signal" or "made by the analyser". An external attenuator does change what the analyser sees, and is part of the setup.
* The firmware prints a value that rounds up to 10 as `-:.000000e+01` (really -100.0). `benchlib/tinysa.py` understands this;
  without it, points silently go missing.
* The serial link occasionally returns a short reply; the driver retries and warns.
* Levels are as read at the analyser. They are not calibrated. Use differences (dB, dBc) between runs on the same setup more
  than absolute dBm. Each run measures a reference level at the start and the end and records the drift.
* The low input stops at 800 MHz, so harmonics above that (for 70cm, the 2nd harmonic of the wanted signal) are not seen.

## Adding a measurement

Add a module to `benchlib/measure/` with `NAME`, `TITLE`, `defaults(rig)`, `estimate_s(params)` and `run(rig, params, log)`
returning JSON-able data (columns of numbers, not objects per point), register it in `benchlib/measure/__init__.py`, add a
metrics function in `benchlib/metrics.py`, a renderer in `webui/app.js`, and a test against the simulated instruments in
`tests/unit/test_bench.py`.

## Layout

```
run.py              command-line runner          serve.py   web UI server (port 3333)
setups/             chain descriptions           webui/     the UI (plain JS, no dependencies)
benchlib/           tinysa.py, pico.py, rig.py, spectrum.py, metrics.py, results.py, setups.py, fakes.py
benchlib/measure/   one module per test           svgplot.py SVG charts for written reports
legacy_import.py    one-off converter            campaign_70cm_v0.py   the original ad-hoc script, kept for reference
```
