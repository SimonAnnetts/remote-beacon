"""Remote beacon entry point.

Core 1 runs the beacon (Si5351, keying, flash writes); core 0 runs Wi-Fi and the
web server. Settings come from config.json.
"""
import _thread
import asyncio
import time

from machine import I2C, Pin

import clock
import config
import web
import wifi
from beacon import Beacon
from si5351 import Si5351

cfg = config.load()
config.validate(cfg)

clk = Si5351(I2C(0, sda=Pin(4), scl=Pin(5), freq=400000),
             correction_ppb=cfg["correction_ppb"])
beacon = Beacon(clk, cfg)
_thread.start_new_thread(beacon.run, ())

net = wifi.start(cfg)
print("network:", net)


async def main():
    asyncio.create_task(wifi.keep_connected(net, lambda: beacon.cfg))
    asyncio.create_task(clock.keep_synced(net, lambda: beacon.cfg))
    await web.serve(beacon, net)


try:
    asyncio.run(main())
finally:
    # Let core 1 switch the outputs off before anything else touches the chip.
    beacon.stop = True
    for _ in range(40):
        if not beacon.running:
            break
        time.sleep_ms(50)
