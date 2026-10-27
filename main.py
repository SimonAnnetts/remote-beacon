import sys
import time

from machine import Pin

# On the Pico W the onboard LED is wired to the WiFi chip; "LED" resolves it.
led = Pin("LED", Pin.OUT)

print("Hello from the Pico W!")
print(sys.implementation)

for i in range(10):
    led.toggle()
    print("blink", i)
    time.sleep(0.5)

led.off()
print("Done")
