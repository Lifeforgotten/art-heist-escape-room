# MPU6050 Tilt Sensor - Picture Frame Puzzle
# Triggers GPIO when tilted past threshold

from machine import Pin, I2C, PWM
import time

# === CONFIG ===
I2C_ID = 0           # I2C0 (SCL=GP1, SDA=GP0)
MPU_ADDR = 0x68      # ADO=GND
SOLENOID_PIN = 15    # GP15 - change as needed
TILT_THRESHOLD = 1.5 # G-force threshold (tweak based on testing)
HYSTERESIS = 0.3     # Deadzone to prevent chatter
TRIGGER_DURATION = 1 # How long to hold solenoid (seconds)

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

# Setup solenoid output
solenoid = Pin(SOLENOID_PIN, Pin.OUT)
solenoid.value(0)

# State
triggered = False

def read_accel():
    """Read accelerometer, return (x, y, z) in G"""
    data = i2c.readfrom_mem(MPU_ADDR, ACCEL_XOUT0, 6)
    # Convert to signed 16-bit, then to G (assuming 2G range)
    x = (data[0] << 8) | data[1]
    y = (data[2] << 8) | data[3]
    z = (data[4] << 8) | data[5]
    
    # Sign extend and convert to G (2G range = 16384 LSB/g)
    if x >= 32768: x -= 65536
    if y >= 32768: y -= 65536
    if z >= 32768: z -= 65536
    
    return (x / 16384, y / 16384, z / 16384)

print("MPU6050 tilt sensor active. Tilt the frame...")

while True:
    x, y, z = read_accel()
    
    # Calculate tilt magnitude (horizontal G-force)
    tilt = (x**2 + y**2)**0.5
    
    # Debug output (optional)
    print(f"X:{x:.2f} Y:{y:.2f} Z:{z:.2f} Tilt:{tilt:.2f}")
    
    if not triggered and tilt > TILT_THRESHOLD:
        print(">>> TRIGGERED!")
        solenoid.value(1)
        time.sleep(TRIGGER_DURATION)
        solenoid.value(0)
        triggered = True
        print("Solenoid fired. Reset by resetting script.")
    
    # Reset trigger if needed (or just let them reload)
    
    time.sleep(0.1)