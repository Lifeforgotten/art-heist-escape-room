# MPU6050 Tilt Sensor - Picture Frame Puzzle
# Triggers GPIO when tilted past threshold
# Reset via button or auto-reset timer

from machine import Pin, I2C, PWM
import time

# === CONFIG ===
I2C_ID = 0           # I2C0 (SCL=GP1, SDA=GP0)
MPU_ADDR = 0x68      # ADO=GND
SOLENOID_PIN = 15    # GP15 - change as needed
RESET_PIN = 14       # GP14 - connect button to GND
LED_PIN = 16         # GP16 - status LED (optional)
TILT_THRESHOLD = 1.5 # G-force threshold (tweak based on testing)
TRIGGER_DURATION = 1 # How long to hold solenoid (seconds)
AUTO_RESET_SEC = 0   # 0 = disabled, otherwise auto-reset after X seconds

# MPU6050 Registers
PWR_MGMT_1 = 0x6B
ACCEL_XOUT0 = 0x3B

# Setup I2C
i2c = I2C(I2C_ID, scl=Pin(1), sda=Pin(0), freq=400000)

# Verify sensor
devices = i2c.scan()
if MPU_ADDR not in devices:
    raise RuntimeError(f"MPU6050 not found at 0x{MPU_ADDR:02X}. Found: {[hex(d) for d in devices]}")

# Wake up MPU6050
i2c.writeto_mem(MPU_ADDR, PWR_MGMT_1, bytes([0]))

# Setup outputs
solenoid = Pin(SOLENOID_PIN, Pin.OUT)
solenoid.value(0)

led = Pin(LED_PIN, Pin.OUT) if LED_PIN else None
if led:
    led.value(0)

# Reset button (internal pull-up)
reset_btn = Pin(RESET_PIN, Pin.IN, Pin.PULL_UP)

# State
triggered = False
trigger_time = 0

def read_accel():
    """Read accelerometer, return (x, y, z) in G"""
    data = i2c.readfrom_mem(MPU_ADDR, ACCEL_XOUT0, 6)
    x = (data[0] << 8) | data[1]
    y = (data[2] << 8) | data[3]
    z = (data[4] << 8) | data[5]
    
    if x >= 32768: x -= 65536
    if y >= 32768: y -= 65536
    if z >= 32768: z -= 65536
    
    return (x / 16384, y / 16384, z / 16384)

def reset_puzzle():
    global triggered, trigger_time
    triggered = False
    trigger_time = 0
    if led:
        led.value(0)
    print(">>> PUZZLE RESET")

print("MPU6050 tilt sensor active. Tilt the frame to trigger.")
print(f"Reset: press button on GP{RESET_PIN} or auto-reset in {AUTO_RESET_SEC}s")

while True:
    x, y, z = read_accel()
    tilt = (x**2 + y**2)**0.5
    
    # Check reset button (pressed = low)
    if reset_btn.value() == 0:
        time.sleep_ms(50)  # debounce
        if reset_btn.value() == 0:
            reset_puzzle()
            while reset_btn.value() == 0:  # wait for release
                time.sleep_ms(50)
    
    # Auto-reset timer
    if triggered and AUTO_RESET_SEC > 0:
        if time.ticks_diff(time.ticks_ms(), trigger_time) > (AUTO_RESET_SEC * 1000):
            reset_puzzle()
    
    # Debug output
    print(f"X:{x:.2f} Y:{y:.2f} Z:{z:.2f} Tilt:{tilt:.2f} {'[TRIGGERED]' if triggered else ''}")
    
    if not triggered and tilt > TILT_THRESHOLD:
        print(">>> TRIGGERED!")
        solenoid.value(1)
        if led:
            led.value(1)
        time.sleep(TRIGGER_DURATION)
        solenoid.value(0)
        triggered = True
        trigger_time = time.ticks_ms()
        print("Solenoid fired. Reset to fire again.")
    
    time.sleep(0.1)