from machine import Pin, TouchPad
import neopixel
import time
import uasyncio as asyncio

# 4 Touch sensors (using safe pins)
DRY_RUN = True  # Set False to enable outputs
TOUCH_PINS = [4, 27, 14]  # 3 touch pins: T0, T1, T2 (T3 removed for now until puzzle logic defined)
touch_sensors = [TouchPad(Pin(p)) for p in TOUCH_PINS]

# Setup outputs
STRIP_PIN = 18  # WS2812 LED strip (stepper not connected, GPIO18 free)
GRID_PIN = 13   # WS2812 grid (moved from 22)

if not DRY_RUN:
    strip = neopixel.NeoPixel(Pin(STRIP_PIN), 30)  # 30 LED strip
    grid = neopixel.NeoPixel(Pin(GRID_PIN), 64)   # 8x8 grid = 64 LEDs
else:
    strip = None
    grid = None
    print("DRY_RUN: esp32_touch_leds outputs disabled")

# Thresholds (calibrate these - touch usually reads lower when touched)
THRESHOLDS = [150, 150, 150, 150]  # Adjust based on your wiring/ambient
DEBOUNCE_MS = 300  # debounce per sensor

async def _clear_strip_after(delay_ms):
    await asyncio.sleep_ms(delay_ms)
    try:
        if not DRY_RUN and strip:
            strip.fill((0, 0, 0))
            strip.write()
    except Exception as e:
        print('Error clearing strip:', e)

async def _clear_grid_after(delay_ms):
    await asyncio.sleep_ms(delay_ms)
    try:
        if not DRY_RUN and grid:
            grid.fill((0, 0, 0))
            grid.write()
    except Exception as e:
        print('Error clearing grid:', e)

async def trigger_strip(color=(255, 50, 0), duration_ms=300):
    if DRY_RUN:
        print(f"DRY_RUN: would set strip to {color} for {duration_ms}ms")
        return
    try:
        strip.fill(color)
        strip.write()
        asyncio.create_task(_clear_strip_after(duration_ms))
    except Exception as e:
        print('Error triggering strip:', e)

async def trigger_grid(color=(0, 50, 255), duration_ms=300):
    if DRY_RUN:
        print(f"DRY_RUN: would set grid to {color} for {duration_ms}ms")
        return
    try:
        grid.fill(color)
        grid.write()
        asyncio.create_task(_clear_grid_after(duration_ms))
    except Exception as e:
        print('Error triggering grid:', e)

async def trigger_both():
    await trigger_strip((255, 255, 0), duration_ms=300)
    await trigger_grid((255, 0, 255), duration_ms=300)

async def touch_loop():
    print("Calibrating - touch values:")
    for i, t in enumerate(touch_sensors):
        try:
            print(f"  T{i} (GPIO{TOUCH_PINS[i]}): {t.read()}")
        except Exception as e:
            print(f"  T{i} read error: {e}")

    await asyncio.sleep(2)

    last_trigger = [0] * len(touch_sensors)

    while True:
        for i, t in enumerate(touch_sensors):
            try:
                val = t.read()
            except Exception as e:
                print(f"Touch read error on {TOUCH_PINS[i]}: {e}")
                continue

            touched = val < THRESHOLDS[i]
            now = time.ticks_ms()
            if touched and time.ticks_diff(now, last_trigger[i]) > DEBOUNCE_MS:
                print(f"Touch {i} detected (val: {val})")
                last_trigger[i] = now

                # Schedule appropriate effect
                if i == 0:
                    asyncio.create_task(trigger_strip((255, 0, 0)))
                elif i == 1:
                    asyncio.create_task(trigger_grid((0, 255, 0)))
                elif i == 2:
                    asyncio.create_task(trigger_strip((0, 0, 255)))
                    asyncio.create_task(trigger_grid((255, 255, 0)))
                # T3 removed until puzzle logic defined

        await asyncio.sleep_ms(50)  # cooperative yield

if __name__ == '__main__':
    try:
        asyncio.run(touch_loop())
    except (KeyboardInterrupt, Exception) as e:
        print('Touch loop exiting:', e)
