Art Heist Escape Room - Wiring and Pinout

This README lists the wiring for the single ESP32 board that runs four scripts:
- main.py (Room Brain)
- auction_house_intranet_async.py (Intranet web server)
- laser_curtain_two_stage.py (Laser + Stepper + Servos + Sensors)
- esp32_touch_leds.py (Touch sensors -> NeoPixel effects)

IMPORTANT: DRY_RUN is enabled by default in scripts. Leave it True while wiring and testing.

Legend:
- Pin: physical GPIO number on ESP32
- Func: logical function
- Dir: direction (IN/OUT/PWM/ADC/TOUCH)
- Wire: suggested wire color

WIRING TABLE (one board hosts all 4 scripts)

| Pin | Func                                   | Dir        | Notes / Suggested Wire |
|-----|----------------------------------------|------------|------------------------|
| 2   | Status LED (intranet)                  | OUT        | Green                 |
| 5   | TRIGGER_MAGLOCK_1 (maglock/relay)      | OUT        | Red   (moved from 4)  |
| 19  | TRIGGER_MAGLOCK_2 (maglock)            | OUT        | Red                   |
| 23  | STATUS_LED (room brain)                | OUT        | Green                 |
| 21  | RESET_BUTTON (shared)                  | IN (PULL_UP)| Blue (active-low)     |
| 25  | AUDIO_DAC / optional output            | OUT        | White                 |
| 16  | SERVO_A (laser mirror A)               | PWM OUT    | Orange                |
| 17  | SERVO_B (laser mirror B)               | PWM OUT    | Orange                |
| 18  | ENABLE_STEPPER (active low)            | OUT        | Yellow                |
| 26  | STEP_DIR (stepper direction)           | OUT        | Brown                 |
| 22  | STEP_STEP (stepper step)               | OUT        | Brown                 |
| 12  | HOME_SWITCH (stepper home)             | IN (PULL_UP)| Grey                  |
| 35  | LIMIT_MAX (stepper max limit)          | IN (input-only)| Grey               |
| 32  | JOYSTICK_X (ADC for mirror A)          | ADC        | Grey (ADC)            |
| 33  | POT_MIRROR (ADC for mirror B)          | ADC        | Grey (ADC)            |
| 34  | LDR_PIN (ADC for laser target)         | ADC        | Grey (ADC, input-only)|
| 27  | TOUCH_PAD (laser curtain touch)        | TOUCH      | Purple                |
| 4   | TOUCH T0 (touch module)                | TOUCH      | Purple                |
| 14  | TOUCH T?
 (touch module)                      | TOUCH      | Purple                |
| 13  | TOUCH T?
 (touch module)                      | TOUCH      | Purple                |
| 15  | NeoPixel STRIP data line               | OUT (1-wire)| White (data)         |
| 13  | NeoPixel GRID data line                | OUT (1-wire)| White (data)         |
| 35  | LIMIT_MAX (input-only)                 | IN         | Grey                  |

NOTES & SAFETY
- NeoPixels (WS2812): use a separate 5V power supply for long strips/grids. Connect grounds together. Add a 470Ω resistor in series with the data line and a 1000µF electrolytic capacitor across 5V-GND at the strip.
- Stepper, servos, and maglocks need separate power supplies sized for their loads. DO NOT power them from the ESP32 VIN or 3.3V pin.
- Stepper driver enable is active-low in code (ENABLE_STEPPER.value(0) to enable). Confirm your driver wiring.
- All limit switches are set with internal PULL_UP. Use mechanical switches wired to ground.
- Touch pins: verify board-specific touch-capable pins. Some pins affect boot mode; avoid using strapping pins pulled low at boot.

DRY_RUN flags
- main.py: DRY_RUN = True (don't drive maglocks)
- laser_curtain_two_stage.py: DRY_RUN = True and ALLOW_SERVOS_IN_DRY_RUN = True (set to True if you want servos to move for visual feedback during dry run)
- esp32_touch_leds.py: DRY_RUN = True (NeoPixel outputs disabled until you set False)
- auction_house_intranet_async.py: no DRY_RUN flag (be cautious; it drives trigger relay)

BOOT & DEBUG
- Serial console: 115200 baud. Use screen/picocom/minicom.
- To prevent main.py from auto-running during edits: remove or rename main.py temporarily or use WebREPL/ampy.

If you'd like, I can also generate a printable table without pipes (plain text) or export as wiring.pdf. Confirm which format you prefer.
