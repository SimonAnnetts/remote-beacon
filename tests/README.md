# Tests

| Folder | What it is |
|---|---|
| `unit/` | Tests of the tooling with simulated instruments. No hardware needed: `python3 -m unittest discover -s tests/unit -v` |
| `bench/` | RF bench measurements of the Si5351 outputs, and the web UI that shows their results. Needs the Pico and a TinySA. See [bench/README.md](bench/README.md) |

Stored measurement results live in [`../tests-results/`](../tests-results/), one JSON file per run.

Nothing in `tests/`, `tests-results/` or `docs/` is meant for the Pico. They are excluded from MicroPico's
**Upload project** by `micropico.pyIgnore` in `.vscode/settings.json`.
