"""Registry of bench measurements."""
from . import drive_levels, response, spectrum_close, spectrum_wide, spur_map

MEASUREMENTS = {m.NAME: m for m in (response, spur_map, spectrum_close, spectrum_wide, drive_levels)}
DEFAULT_ORDER = ["drive_levels", "spur_map", "spectrum_close", "spectrum_wide", "response"]
