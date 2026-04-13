# HX711 Weight Sensor - Cabinet Door Puzzle
# Triggers linear actuator when weight threshold exceeded
# Uses HX711 Channel A (128 gain) - supports 2 load cells in bridge
# To add Channel B support, modify hx711_read() for gain=32

from machine import Pin, I2C
import time

# === CONFIG ===
HX711_SCK = 14  # GP14 - clock pin
HX711_DT = 15   # GP15 - data pin
ACTUATOR_PIN = 16  # GP16 - MOSFET gate for actuator
ACTUATOR_EXTEND_ON = True  # True = HIGH extends, False = HIGH retracts
WEIGHT_THRESHOLD = 500  # Raw reading threshold (tune this)
WEIGHT_OFFSET = 0       # Tare offset
CALIBRATION = 2280      # Divide raw by this to get approximate grams (tune)
TRIGGER_DURATION = 15   # Seconds to run actuator (full extension)

# HX711 functions
def hx711_read():
    """Read 24-bit value from HX711"""
    # Wait for data ready
    while dt.value() == 1:
        pass
    
    # Read 24 bits
    result = 0
    for i in range(24):
        sck.value(1)
        result = (result << 1) | dt.value()
        sck.value(0)
    
    # Pulse for channel/gain (128 for channel A, 128 gain)
    for _ in range(2):  # Actually 2 pulses for 128 gain
        sck.value(1)
        sck.value(0)
    
    # Handle signed value
    if result & 0x800000:
        result |= 0xFF000000
    
    return result

# === CONFIG PINS ===
sck = Pin(HX711_SCK, Pin.OUT)
dt = Pin(HX711_DT, Pin.IN)

actuator = Pin(ACTUATOR_PIN, Pin.OUT)
actuator.value(0)

# State
triggered = False
last_weight = 0

print("HX711 weight sensor active. Place weight to trigger.")
print("Calibration: raw /", CALIBRATION, "= grams (approx)")
print("Current threshold:", WEIGHT_THRESHOLD)

# Tare on startup
print("Taring...")
time.sleep(1)
tare_sum = 0
for i in range(10):
    tare_sum += hx711_read()
    time.sleep(0.1)
WEIGHT_OFFSET = tare_sum // 10
print("Tare offset:", WEIGHT_OFFSET)

while True:
    raw = hx711_read()
    # Apply offset and calibration
    adjusted = raw - WEIGHT_OFFSET
    weight_grams = adjusted / CALIBRATION if CALIBRATION else 0
    
    # Use raw adjusted value for threshold (more direct)
    if abs(adjusted) > WEIGHT_THRESHOLD:
        display_weight = abs(adjusted) // 100  # Scaled for display
    else:
        display_weight = abs(adjusted)
    
    # Debug output
    print(f"Raw:{adjusted:+d} Weight:{weight_grams:.1f}g {'[TRIGGERED]' if triggered else ''}")
    
    # Check trigger
    if not triggered and abs(adjusted) > WEIGHT_THRESHOLD:
        print(">>> TRIGGERED! Extending actuator...")
        if ACTUATOR_EXTEND_ON:
            actuator.value(1)
            time.sleep(TRIGGER_DURATION)
            actuator.value(0)
        else:
            actuator.value(0)
            time.sleep(TRIGGER_DURATION)
            actuator.value(1)
        triggered = True
        print("Actuator extended. Reset to fire again.")
    
    # Reset check (if weight drops below threshold)
    if triggered and abs(adjusted) < (WEIGHT_THRESHOLD // 2):
        triggered = False
        print(">>> RESET (weight removed)")
    
    time.sleep(0.2)