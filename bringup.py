"""Hardware bring-up: probe the Si5351 and step through the three outputs.

Wiring: Si5351 SDA -> GP4, SCL -> GP5, VIN -> 3V3(OUT), GND -> GND.
Outputs are unfiltered square waves: no antenna, use a short wire into an SDR.
"""
import time

from machine import I2C, Pin

from si5351 import Si5351

STAGE_SECONDS = 60

# Measured against a TinySA Ultra (checked on its 30 MHz cal output): the
# crystal runs 151.3 ppm fast. Temperature drift remains; GPS will refine this.
CORRECTION_PPB = 151300

# (channel, PLL, carrier Hz, what to look for on the SDR)
STAGES = (
    (0, Si5351.PLLA, 50200000, "6m carrier at 50.2 MHz"),
    (1, Si5351.PLLA, 144500000, "2m carrier at 144.5 MHz (CLK0 must stay at 50.2)"),
    (2, Si5351.PLLB, 145000000, "70cm: 145.0 MHz carrier, 3rd harmonic at 435.0 MHz"),
)

led = Pin("LED", Pin.OUT)
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
print("I2C devices:", [hex(a) for a in i2c.scan()])

clk = Si5351(i2c, correction_ppb=CORRECTION_PPB)
print("Si5351 found, status:", clk.status())

for ch, pll, hz, note in STAGES:
    actual = clk.set_frequency(ch, hz, pll=pll)
    time.sleep_ms(50)
    print("CLK%d -> %d Hz | locked: %s | %s" % (ch, actual, clk.locked(), note))
    for _ in range(STAGE_SECONDS * 2):
        led.toggle()
        time.sleep_ms(500)

clk.disable_all()
led.off()
print("Done, all outputs off")
