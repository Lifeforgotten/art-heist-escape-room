# Converted 3-Stage Servo-Rotary Encoder Puzzle for ESP32 (WROOM on Acebot breakout)
# MicroPython for ESP32
# NOTE: Review and adjust PIN_* constants below to match your Acebot breakout wiring.

from machine import Pin, PWM
import time

# ==========================================================================
# CONFIGURATION - adjust for your hardware
# ============================================================================

# Phase 1 sequence unchanged
PHASE1_SEQUENCE = [
    ("right", 3),
    ("button", 0),
    ("left", 2),
    ("button", 0),
    ("left", 3),
    ("button", 0),
]

STATUETTE_FACE_EACH_OTHER = 0
FIGURINE_FACE_EACH_OTHER = 180
STATUETTE_FACE_PAINTING = 45
FIGURINE_FACE_OBELISK = 135
ANGLE_TOLERANCE = 10

BUST_HOLD_TIME_MS = 2000
BUST_NORMAL_MAX = 90
BUST_FULL_RANGE = 180

SERVO_FREQ = 50  # 50Hz for standard servos
# ESP32 MicroPython PWM duty range is typically 0-1023 (10-bit). We'll map pulse width to that.
# For 20ms period: 0.5ms -> 0.025 fraction -> ~26 ; 2.5ms -> 0.125 fraction -> ~128
SERVO_MIN_DUTY = 26
SERVO_MAX_DUTY = 128
SERVO_HOME_POSITION = 90

DEBOUNCE_MS = 50
BUTTON_HOLD_MS = 2000

# ==========================================================================
# PIN ASSIGNMENTS (default suggestions)
# Edit these to match your ACEBOT breakout wiring before flashing
# ==========================================================================

# Servos (PWM pins)
PIN_STATUETTE_SERVO = 18
PIN_FIGURINE_SERVO = 19
PIN_BUST_SERVO = 21

# Outputs (relay/solenoid/maglock)
PIN_PANEL_LOCK = 22
PIN_STATUS_LED = 23
PIN_FINAL_MAGLOCK = 5

# Rotary Encoders (choose pins that support interrupts and pull-ups)
PIN_STATUETTE_CLK = 32
PIN_STATUETTE_DT = 33
PIN_STATUETTE_SW = 25

PIN_FIGURINE_CLK = 26
PIN_FIGURINE_DT = 27
PIN_FIGURINE_SW = 14

PIN_BUST_CLK = 16
PIN_BUST_DT = 17
PIN_BUST_SW = 4

# ==========================================================================
# HELPERS / CLASSES
# ==========================================================================

class RotaryEncoder:
    def __init__(self, clk_pin, dt_pin, sw_pin, name="encoder"):
        self.name = name
        self.clk = Pin(clk_pin, Pin.IN, Pin.PULL_UP)
        self.dt = Pin(dt_pin, Pin.IN, Pin.PULL_UP)
        self.sw = Pin(sw_pin, Pin.IN, Pin.PULL_UP)

        self.position = 0
        self.last_clk = self.clk.value()
        self.button_pressed = False
        self.button_held = False
        self.hold_start = 0

        self.clk.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._on_clk)
        self.sw.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._on_sw)

    def _on_clk(self, pin):
        clk_val = self.clk.value()
        dt_val = self.dt.value()
        if clk_val != self.last_clk:
            if dt_val != clk_val:
                self.position += 1
            else:
                self.position -= 1
            self.last_clk = clk_val

    def _on_sw(self, pin):
        if not self.sw.value():
            self.button_pressed = True
            self.hold_start = time.ticks_ms()
        else:
            # released
            self.button_pressed = False
            self.button_held = False

    def update(self):
        if self.button_pressed and not self.button_held:
            if time.ticks_diff(time.ticks_ms(), self.hold_start) >= BUTTON_HOLD_MS:
                self.button_held = True
                return "held"
        return None

    def get_clicks(self):
        clicks = self.position
        self.position = 0
        return clicks

    def was_pressed(self):
        # Return True if a short press (press+release) occurred
        if not self.sw.value() and not self.button_held:
            # still pressed
            return False
        # if previously marked pressed and now released
        if self.button_pressed is False and self.button_held is False:
            # nothing outstanding
            return False
        # If we detect a release (button_pressed false and not held), treat as press
        if not self.button_pressed and not self.button_held:
            return False
        # Simpler: check edges by sampling; user code calls this frequently after IRQs
        # We'll approximate: if hold flag isn't set and sw reads high (released) after earlier press
        if self.button_pressed and not self.button_held and self.sw.value():
            self.button_pressed = False
            return True
        return False

    def reset(self):
        self.position = 0
        self.button_pressed = False
        self.button_held = False


class Servo:
    def __init__(self, pin, name="servo"):
        self.name = name
        self.pwm = PWM(Pin(pin), freq=SERVO_FREQ)
        self.current_angle = SERVO_HOME_POSITION
        self.set_angle(SERVO_HOME_POSITION)

    def angle_to_duty(self, angle):
        angle = max(0, min(180, angle))
        duty = SERVO_MIN_DUTY + (angle / 180.0) * (SERVO_MAX_DUTY - SERVO_MIN_DUTY)
        return int(duty)

    def set_angle(self, angle):
        self.current_angle = max(0, min(180, angle))
        d = self.angle_to_duty(self.current_angle)
        try:
            self.pwm.duty(d)
        except Exception:
            # Some firmwares provide duty instead of duty(), so try attribute
            self.pwm.duty(d)

    def move_by(self, delta):
        new_angle = self.current_angle + delta
        self.set_angle(new_angle)

    def get_angle(self):
        return self.current_angle

    def is_at_target(self, target, tolerance=ANGLE_TOLERANCE):
        return abs(self.current_angle - target) <= tolerance


# ==========================================================================
# HARDWARE SETUP
# ==========================================================================

statuette_servo = Servo(PIN_STATUETTE_SERVO, "statuette")
figurine_servo = Servo(PIN_FIGURINE_SERVO, "figurine")
bust_servo = Servo(PIN_BUST_SERVO, "bust")

statuette_encoder = RotaryEncoder(PIN_STATUETTE_CLK, PIN_STATUETTE_DT, PIN_STATUETTE_SW, "statuette")
figurine_encoder = RotaryEncoder(PIN_FIGURINE_CLK, PIN_FIGURINE_DT, PIN_FIGURINE_SW, "figurine")
bust_encoder = RotaryEncoder(PIN_BUST_CLK, PIN_BUST_DT, PIN_BUST_SW, "bust")

panel_lock = Pin(PIN_PANEL_LOCK, Pin.OUT)
status_led = Pin(PIN_STATUS_LED, Pin.OUT)
final_maglock = Pin(PIN_FINAL_MAGLOCK, Pin.OUT)

# Initialize outputs
panel_lock.value(1)
final_maglock.value(1)
status_led.value(0)

# Helper to toggle LED (Pin.toggle() not guaranteed on ESP32 MicroPython)
def led_toggle():
    status_led.value(not status_led.value())

# ==========================================================================
# STATE
# ==========================================================================

PHASE_IDLE = 0
PHASE_1 = 1
PHASE_2 = 2
PHASE_3 = 3
PHASE_COMPLETE = 4

current_phase = PHASE_IDLE
phase1_step = 0
phase2_step = 0
bust_extended = False

# ==========================================================================
# HELPERS / PHASE HANDLERS
# ==========================================================================

def home_all_servos():
    statuette_servo.set_angle(SERVO_HOME_POSITION)
    figurine_servo.set_angle(SERVO_HOME_POSITION)
    bust_servo.set_angle(SERVO_HOME_POSITION)

    statuette_encoder.reset()
    figurine_encoder.reset()
    bust_encoder.reset()

    time.sleep(0.5)


def unlock_panel():
    panel_lock.value(0)
    status_led.value(1)
    print("Panel unlocked!")


def unlock_final():
    final_maglock.value(0)
    status_led.value(1)
    print("Final maglock released! Puzzle complete!")


def reset_puzzle():
    global current_phase, phase1_step, phase2_step, bust_extended
    current_phase = PHASE_1
    phase1_step = 0
    phase2_step = 0
    bust_extended = False

    panel_lock.value(1)
    final_maglock.value(1)
    status_led.value(0)

    home_all_servos()
    print("Puzzle reset. Phase 1 active.")


def handle_phase1():
    global current_phase, phase1_step
    clicks = statuette_encoder.get_clicks()

    if clicks != 0:
        print("Statuette clicks:", clicks)

    if statuette_encoder.was_pressed():
        expected_dir, expected_clicks = PHASE1_SEQUENCE[phase1_step]
        if expected_dir == "button":
            print(f"Phase 1 step {phase1_step} complete: button pressed")
            phase1_step += 1
        else:
            print("Button pressed out of sequence")

    if clicks != 0 and phase1_step < len(PHASE1_SEQUENCE):
        expected_dir, expected_clicks = PHASE1_SEQUENCE[phase1_step]
        if expected_dir == "right" and clicks == expected_clicks:
            print(f"Phase 1 step {phase1_step} complete: {clicks} right")
            phase1_step += 1
        elif expected_dir == "left" and clicks == -expected_clicks:
            print(f"Phase 1 step {phase1_step} complete: {abs(clicks)} left")
            phase1_step += 1
        else:
            print(f"Wrong input: expected {expected_dir} {expected_clicks}, got {clicks}")

    if phase1_step >= len(PHASE1_SEQUENCE):
        unlock_panel()
        current_phase = PHASE_2
        print("Phase 1 complete! Phase 2 active.")


def handle_phase2():
    global current_phase, phase2_step
    stat_clicks = statuette_encoder.get_clicks()
    fig_clicks = figurine_encoder.get_clicks()

    CLICK_TO_DEGREES = 5

    if stat_clicks != 0:
        statuette_servo.move_by(stat_clicks * CLICK_TO_DEGREES)
        print("Statuette angle:", statuette_servo.get_angle())

    if fig_clicks != 0:
        figurine_servo.move_by(fig_clicks * CLICK_TO_DEGREES)
        print("Figurine angle:", figurine_servo.get_angle())

    if phase2_step == 0:
        if statuette_encoder.was_pressed() and figurine_encoder.was_pressed():
            stat_ok = statuette_servo.is_at_target(STATUETTE_FACE_EACH_OTHER)
            fig_ok = figurine_servo.is_at_target(FIGURINE_FACE_EACH_OTHER)
            if stat_ok and fig_ok:
                print("They faced each other! Now face your favorites...")
                phase2_step = 1
            else:
                print("Not quite facing each other yet...")
    elif phase2_step == 1:
        if statuette_encoder.was_pressed() and figurine_encoder.was_pressed():
            stat_ok = statuette_servo.is_at_target(STATUETTE_FACE_PAINTING)
            fig_ok = figurine_servo.is_at_target(FIGURINE_FACE_OBELISK)
            if stat_ok and fig_ok:
                print("Phase 2 complete! Phase 3 active.")
                current_phase = PHASE_3
                for _ in range(3):
                    led_toggle()
                    time.sleep(0.2)
            else:
                print("Not facing the right favorites...")


def handle_phase3():
    global current_phase, bust_extended
    bust_clicks = bust_encoder.get_clicks()
    CLICK_TO_DEGREES = 5

    if bust_clicks != 0:
        current = bust_servo.get_angle()
        new_angle = current + (bust_clicks * CLICK_TO_DEGREES)
        max_angle = BUST_FULL_RANGE if bust_extended else BUST_NORMAL_MAX
        new_angle = max(0, min(max_angle, new_angle))
        bust_servo.set_angle(new_angle)
        print(f"Bust angle: {bust_servo.get_angle()} (extended: {bust_extended})")

    hold_result = bust_encoder.update()
    if hold_result == "held" and not bust_extended:
        if bust_servo.get_angle() >= BUST_NORMAL_MAX - 10:
            bust_extended = True
            print("Bust extended! Full 180° range unlocked.")
            for _ in range(5):
                led_toggle()
                time.sleep(0.1)

    if bust_extended and bust_servo.get_angle() >= BUST_FULL_RANGE - 10:
        if bust_encoder.was_pressed():
            unlock_final()
            current_phase = PHASE_COMPLETE

# ==========================================================================
# MAIN
# ==========================================================================

def main():
    print('=' * 50)
    print('3-Stage Servo Puzzle (ESP32) Starting...')
    print('=' * 50)

    home_all_servos()
    reset_puzzle()

    while True:
        try:
            if current_phase == PHASE_1:
                handle_phase1()
            elif current_phase == PHASE_2:
                handle_phase2()
            elif current_phase == PHASE_3:
                handle_phase3()
            elif current_phase == PHASE_COMPLETE:
                pass

            time.sleep(0.01)
        except KeyboardInterrupt:
            print('\nShutting down...')
            home_all_servos()
            panel_lock.value(1)
            final_maglock.value(1)
            break

if __name__ == '__main__':
    main()
