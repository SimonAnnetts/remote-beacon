"""Remote beacon entry point: run the beacon scheduler from config.json."""
from machine import I2C, Pin

import config
from beacon import Beacon
from si5351 import Si5351

cfg = config.load()
config.validate(cfg)

i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
clk = Si5351(i2c, correction_ppb=cfg["correction_ppb"])

beacon = Beacon(clk, cfg)
try:
    beacon.run()
finally:
    clk.disable_all()
