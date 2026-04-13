# MPU6050 Tilt + Solenoid Wiring (Pico H)

## I2C (MPU6050)
| MPU6050 | Pico |
|---------|------|
| VCC     | 3.3V (Pin 36) |
| GND     | GND (Pin 38) |
| SCL     | GP1 (Pin 2) |
| SDA     | GP0 (Pin 1) |
| ADO     | GND (Pin 38) → sets addr to 0x68 |

## Solenoid (via MOSFET)

```
                    ┌─────────────┐
    GP15 ────R─── Gate           Drain ──── Solenoid ──── V+
     (Pin 20)    10kΩ           │              │
                               Source        GND
                    └─────────────┘        (Pin 38)
                         │
                        GND
```

**Parts:**
- **R (Gate resistor):** 10kΩ between GP15 and MOSFET gate
- **MOSFET:** N-channel logic-level (e.g., IRF520, AO3400, 2N7000)
- **Solenoid:** One end to 5V/12V (depends on solenoid), other to MOSFET drain
- **Flyback diode:** 1N4007 across solenoid (anode to drain, cathode to V+) — **REQUIRED** to protect MOSFET

**Wiring MOSFET (TO-220 or similar):**
- Pin 1 (Source) → GND
- Pin 2 (Drain) → Solenoid → Cathode of diode
- Pin 3 (Drain) → Solenoid → Anode of diode

Wait, for TO-220:
- Left (Source) → GND
- Middle (Drain) → Solenoid → Diode
- Right (Drain) → Solenoid → Diode

**Power:** Solder bridge Pico to select 5V (USB) or VSYS (up to ~12V with diode). For simplicity, use USB 5V if your solenoid is 5V.

---

Run the script again and the latch should retract. Test with an LED first if you want to verify before hooking up the solenoid.