from machine import Pin, ADC, PWM, TouchPad, WDT
import time
import room_reset

# Pin assignments
DRY_RUN = True  # Set False after you verify inputs over serial

JOYSTICK_X = ADC(Pin(32))      # X-axis for mirror A (ADC)
POT_MIRROR = ADC(Pin(33))      # Rotary dial for mirror B (ADC)
LDR_PIN = ADC(Pin(34))         # Photoresistor at laser target (input-only)
TOUCH_PAD = TouchPad(Pin(27))  # Capacitive touch (T7)

SERVO_A_PIN = 16
SERVO_B_PIN = 17
STEP_DIR_PIN = 26
STEP_STEP_PIN = 22
HOME_SWITCH_PIN = 12
LIMIT_MAX_PIN = 35
ENABLE_STEPPER_PIN = 18
RESET_BUTTON_PIN = 21

# Pin objects (respect DRY_RUN)
STEP_DIR = Pin(STEP_DIR_PIN, Pin.OUT)
STEP_STEP = Pin(STEP_STEP_PIN, Pin.OUT)
HOME_SWITCH = Pin(HOME_SWITCH_PIN, Pin.IN, Pin.PULL_UP)
LIMIT_MAX = Pin(LIMIT_MAX_PIN, Pin.IN, Pin.PULL_UP)
ENABLE_STEPPER = Pin(ENABLE_STEPPER_PIN, Pin.OUT)
RESET_BUTTON = Pin(RESET_BUTTON_PIN, Pin.IN, Pin.PULL_UP)

# Servos (only initialize PWM if not DRY_RUN)
if not DRY_RUN:
    servo_a = PWM(Pin(SERVO_A_PIN))
    servo_b = PWM(Pin(SERVO_B_PIN))
    servo_a.freq(50)
    servo_b.freq(50)
else:
    servo_a = None
    servo_b = None
    print("DRY_RUN: laser_curtain_two_stage outputs disabled")

# Enable stepper (active low) (respect DRY_RUN)
if not DRY_RUN:
    ENABLE_STEPPER.value(0)
else:
    print("DRY_RUN: stepper enable/drive suppressed")

# Setup
servo_a = PWM(Pin(SERVO_A_PIN))
servo_b = PWM(Pin(SERVO_B_PIN))
servo_a.freq(50)
servo_b.freq(50)

# Enable stepper (active low)
ENABLE_STEPPER.value(0)

# Watchdog timer (10 second timeout)
wdt = WDT(timeout=10000)

# Calibration
LDR_THRESHOLD = 30000
TOUCH_THRESHOLD = 200
STEP_DELAY = 0.001
STEPS_STAGE_1 = 1000   # Half open
STEPS_STAGE_2 = 1000   # Remainder to fully open
MAX_STEPS = 2500       # Safety limit - never exceed

# Servo idle timeout (disable PWM after 30s to save power/prevent jitter)
SERVO_IDLE_MS = 30000
last_servo_move = time.ticks_ms()

# State machine
curtain_stage = 0  # 0=closed, 1=half, 2=fully open
curtain_steps = 0  # Track absolute step count
laser_triggered = False
touch_triggered = False
servos_active = True

def angle_to_duty(angle):
    pulse = 500 + (angle * 2000 // 180)
    return int(pulse * 65535 // 20000)

def set_servo_a(angle):
    global last_servo_move, servos_active
    servo_a.duty_u16(angle_to_duty(max(0, min(180, angle))))
    last_servo_move = time.ticks_ms()
    servos_active = True

def set_servo_b(angle):
    global last_servo_move, servos_active
    servo_b.duty_u16(angle_to_duty(max(0, min(180, angle))))
    last_servo_move = time.ticks_ms()
    servos_active = True

def disable_servos():
    global servos_active
    servo_a.duty_u16(0)
    servo_b.duty_u16(0)
    servos_active = False

def step_motor(direction, steps):
    global curtain_steps
    STEP_DIR.value(direction)
    for _ in range(steps):
        # Safety checks before each step
        if direction == 0 and HOME_SWITCH.value() == 0:
            print("Home limit hit!")
            curtain_steps = 0
            break
        if direction == 1 and LIMIT_MAX.value() == 0:
            print("Max limit hit!")
            break
        if curtain_steps >= MAX_STEPS and direction == 1:
            print("Software limit reached!")
            break
        
        STEP_STEP.value(1)
        time.sleep(STEP_DELAY)
        STEP_STEP.value(0)
        time.sleep(STEP_DELAY)
        
        curtain_steps += 1 if direction else -1
        wdt.feed()  # Keep watchdog happy during stepping

def home_curtain():
    global curtain_stage, curtain_steps
    print("Homing curtain...")
    ENABLE_STEPPER.value(0)  # Enable driver
    
    # Fast home until switch
    while HOME_SWITCH.value() == 1:
        step_motor(0, 5)
        if LIMIT_MAX.value() == 0:  # Safety - if we hit max instead, reverse
            print("Wrong direction! Reversing...")
            time.sleep(0.5)
            step_motor(1, 100)
    
    curtain_stage = 0
    curtain_steps = 0
    ENABLE_STEPPER.value(1)  # Disable to save power/prevent heat
    print("Curtain closed and homed")

def advance_curtain():
    global curtain_stage
    ENABLE_STEPPER.value(0)  # Enable before moving
    
    if curtain_stage == 0:
        print("Stage 1: Opening to 50%")
        step_motor(1, STEPS_STAGE_1)
        curtain_stage = 1
        print("Curtain at 50% - partial reveal")
    elif curtain_stage == 1:
        print("Stage 2: Fully opening")
        step_motor(1, STEPS_STAGE_2)
        curtain_stage = 2
        print("Curtain fully open - back wall revealed!")
    else:
        print("Curtain already fully open")
    
    ENABLE_STEPPER.value(1)  # Disable after move

def reset_puzzle():
    """Full reset - home curtain, disable servos, reset state"""
    global curtain_stage, laser_triggered, touch_triggered
    print("\n*** RESET TRIGGERED ***")
    home_curtain()
    disable_servos()
    curtain_stage = 0
    laser_triggered = False
    touch_triggered = False
    print("Puzzle reset complete\n")

# Async wrapper for the room-wide reset coordinator
import uasyncio as asyncio
import room_reset

async def async_reset_puzzle():
    reset_puzzle()
    # Yield control back to the event loop – ensures the coordinator can continue
    await asyncio.sleep(0)

# Register with the central coordinator – this lets the global reset command call us
room_reset.coordinator.register('laser_curtain', async_reset_puzzle)


def check_reset():
    """Check physical reset button"""
    return RESET_BUTTON.value() == 0  # Active low

def read_joystick():
    val = JOYSTICK_X.read_u16()
    return int(val * 180 // 65535)

def read_pot():
    val = POT_MIRROR.read_u16()
    return int(val * 180 // 65535)

def check_laser_hit():
    return LDR_PIN.read_u16() > LDR_THRESHOLD

def check_touch():
    return TOUCH_PAD.read() < TOUCH_THRESHOLD

# Main loop
print("Laser Curtain - Two Stage Puzzle")
print("Safety features: Limits, servo idle, watchdog, reset button")
home_curtain()

last_a = -1
last_b = -1

print("\nStarting main loop...")

try:
    while True:
        wdt.feed()  # Keep watchdog happy
        
        # Check reset button first
        if check_reset():
            reset_puzzle()
            time.sleep(0.5)  # Debounce
        
        # Update mirrors
        angle_a = read_joystick()
        angle_b = read_pot()
        
        if abs(angle_a - last_a) > 1:
            set_servo_a(angle_a)
            last_a = angle_a
        if abs(angle_b - last_b) > 1:
            set_servo_b(angle_b)
            last_b = angle_b
        
        # Servo idle timeout check
        if servos_active:
            idle_time = time.ticks_diff(time.ticks_ms(), last_servo_move)
            if idle_time > SERVO_IDLE_MS:
                print("Servos idle - disabling to save power")
                disable_servos()
        
        # Check trigger 1: Laser
        if check_laser_hit():
            if not laser_triggered:
                print("LASER HIT detected!")
                advance_curtain()
                laser_triggered = True
        else:
            laser_triggered = False
        
        # Check trigger 2: Touch
        if check_touch():
            if not touch_triggered:
                print("TOUCH detected!")
                advance_curtain()
                touch_triggered = True
        else:
            touch_triggered = False
        
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nShutting down...")
    disable_servos()
    ENABLE_STEPPER.value(1)  # Disable stepper
    servo_a.deinit()
    servo_b.deinit()
