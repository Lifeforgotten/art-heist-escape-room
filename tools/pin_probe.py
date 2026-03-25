# pin_probe.py
# Safe pin capability probe for ESP32 (MicroPython)
# Run from Thonny or REPL. Keep heavy loads disconnected.

from machine import Pin
import time

probe_pins = [p for p in range(0,40) if p not in range(6,12)]  # skip flash pins 6-11
print("Probing pins (skipping 6-11). Avoid heavy loads. Results follow:\n")
print("PIN | IN? | OUT? | ADC? | TOUCH? | PWM? | NOTE")
print("-"*80)

for p in probe_pins:
    note = ""
    can_in = can_out = has_adc = has_touch = has_pwm = False

    # Test creating as input
    try:
        pin_in = Pin(p, Pin.IN)
        can_in = True
    except Exception as e:
        note += f"IN_err:{e} "

    # Test ADC (constructor only)
    try:
        from machine import ADC
        adc = ADC(Pin(p))
        has_adc = True
    except Exception:
        has_adc = False

    # Test Touch
    try:
        from machine import TouchPad
        tp = TouchPad(Pin(p))
        has_touch = True
    except Exception:
        has_touch = False

    # Test PWM (create then deinit quickly)
    try:
        from machine import PWM
        pwm = PWM(Pin(p))
        try:
            pwm.deinit()
        except Exception:
            pass
        has_pwm = True
    except Exception:
        has_pwm = False

    # Test temporary output capability (set to OUT then revert to IN)
    try:
        pin_out = Pin(p, Pin.OUT)
        # immediately revert to input to avoid leaving driven pin
        pin_out.init(Pin.IN)
        can_out = True
    except Exception:
        can_out = False

    print("{:>3} |  {:1}  |  {:1}  |  {:3}  |   {:3}   |  {:3} | {}".format(
        p,
        "Y" if can_in else "N",
        "Y" if can_out else "N",
        "Y" if has_adc else "N",
        "Y" if has_touch else "N",
        "Y" if has_pwm else "N",
        note
    ))
