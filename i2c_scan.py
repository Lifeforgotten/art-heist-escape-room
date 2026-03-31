# I2C Scanner - Find devices on different pins
# Wire your LCD to any set of pins, run this, and it will report what it finds

from machine import Pin, I2C
import time

# Try scanning on different pin combinations
test_configs = [
    {"sda": 21, "scl": 22, "name": "H13 (SDA) / H14 (SCL)"},
    {"sda": 21, "scl": 23, "name": "SDA21/SCL23"},
    {"sda": 22, "scl": 23, "name": "SDA22/SCL23"},
    {"sda": 4, "scl": 5, "name": "GPIO4/5 (common I2C alt)"},  # Also try common alt pins
]

def scan_i2c(sda_pin, scl_pin, name):
    print(f"\n=== Scanning {name} (SDA={sda_pin}, SCL={scl_pin}) ===")
    try:
        i2c = I2C(0, sda=Pin(sda_pin), scl=Pin(scl_pin), freq=400000)
        devices = i2c.scan()
        if devices:
            print(f"  Found device(s): {[hex(d) for d in devices]}")
            for d in devices:
                # Common LCD addresses
                if d == 0x27:
                    print(f"    -> 0x27: Likely LCD (PCF8574)")
                elif d == 0x3F:
                    print(f"    -> 0x3F: Likely LCD (PCF8574A)")
                elif d == 0x3C:
                    print(f"    -> 0x3C: Likely OLED (SSD1306)")
                else:
                    print(f"    -> Unknown device at {hex(d)}")
        else:
            print("  No devices found")
    except Exception as e:
        print(f"  Error: {e}")

# Run scans
for cfg in test_configs:
    scan_i2c(cfg["sda"], cfg["scl"], cfg["name"])
    time.sleep_ms(500)

print("\n=== Done ===")
print("If no devices found, check wiring. Common LCD address: 0x27 or 0x3F")