# Art Heist Escape Room - Main Controller (Room Brain)
# ESP32 MicroPython with asyncio
# Integrates: Intranet, UDP mesh, puzzle orchestration, master reset

import network
import socket
import machine
import time
import asyncio
import json
from machine import Pin, PWM, ADC, TouchPad

# === CONFIGURATION ===
WIFI_SSID = "AUCTION_HOUSE"
WIFI_PASSWORD = ""  # Open network for players
DEVICE_ID = "ROOM_BRAIN"  # Identify in UDP mesh

# UDP Network
UDP_PORT = 5005
UDP_BROADCAST = "192.168.4.255"
HEARTBEAT_INTERVAL_MS = 1000

# Puzzle State (master record)
puzzle_state = {
    'logged_in': False,
    'vault_unlocked': False,
    'inventory_searched': False,
    'security_cleared': False,
    'laser_stage': 0,        # 0=unsolved, 1=stage1, 2=complete
    'curtain_position': 0,   # 0=closed, 1=half, 2=open
    'three_stage_servo': 0,  # 0=inactive, 1=phase1, 2=phase2, 3=phase3, 4=complete
    'touch_leds_active': False,
    'dead_drop_solved': False,
    'environmental_scanner': 'locked',  # locked/unlocked
    'room_reset_count': 0,
    'last_udp_seen': {}  # Track prop controller heartbeats
}

# === CONFIG: DRY_RUN ===
# When True the script logs actions instead of driving hardware. Toggle to False once you've verified inputs.
DRY_RUN = True

# === HARDWARE PINS (Room Brain) ===
TRIGGER_MAGLOCK_1_PIN = 5
TRIGGER_MAGLOCK_2_PIN = 19
STATUS_LED_PIN = 23  # keep status LED on 23 (NeoPixel strip moved to 15)
RESET_BUTTON_PIN = 21
AUDIO_DAC_PIN = 25

TRIGGER_MAGLOCK_1 = Pin(TRIGGER_MAGLOCK_1_PIN, Pin.OUT)
TRIGGER_MAGLOCK_2 = Pin(TRIGGER_MAGLOCK_2_PIN, Pin.OUT)
STATUS_LED = Pin(STATUS_LED_PIN, Pin.OUT)
RESET_BUTTON = Pin(RESET_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
AUDIO_DAC = Pin(AUDIO_DAC_PIN)

# Initialize outputs (respect DRY_RUN)
if not DRY_RUN:
    TRIGGER_MAGLOCK_1.value(0)
    TRIGGER_MAGLOCK_2.value(0)
    STATUS_LED.value(1)
else:
    print("DRY_RUN: Hardware outputs are disabled. Logs will show intended actions.")

# === WIFI ACCESS POINT ===
ap = network.WLAN(network.AP_IF)
ap.active(True)
if WIFI_PASSWORD:
    ap.config(essid=WIFI_SSID, password=WIFI_PASSWORD, authmode=network.AUTH_WPA_WPA2_PSK)
else:
    ap.config(essid=WIFI_SSID)

print(f"AP started: {WIFI_SSID}")
ip = ap.ifconfig()[0]
print(f"IP address: {ip}")

# === UDP SOCKET ===
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
udp_sock.setblocking(False)
udp_sock.bind(('0.0.0.0', UDP_PORT))

# === UDP PROTOCOL ===
async def send_udp_command(command, target=None):
    """Broadcast command to all props or specific target"""
    msg = json.dumps({
        'from': DEVICE_ID,
        'cmd': command,
        'timestamp': time.ticks_ms()
    })
    dest = (target, UDP_PORT) if target else (UDP_BROADCAST, UDP_PORT)
    try:
        udp_sock.sendto(msg.encode(), dest)
        print(f"UDP TX: {command}")
    except Exception as e:
        print(f"UDP send error: {e}")

async def udp_listener():
    """Listen for commands from prop controllers"""
    print("UDP listener started...")
    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)
            msg = json.loads(data.decode())
            print(f"UDP RX from {addr}: {msg}")
            
            # Update heartbeat tracking
            device = msg.get('from', 'unknown')
            puzzle_state['last_udp_seen'][device] = time.ticks_ms()
            
            # Handle specific commands
            cmd = msg.get('cmd', '')
            if cmd == 'LASER_STAGE_1':
                puzzle_state['laser_stage'] = 1
                await on_laser_stage_1()
            elif cmd == 'LASER_STAGE_2':
                puzzle_state['laser_stage'] = 2
                await on_laser_stage_2()
            elif cmd == 'SERVO_PUZZLE_PHASE_1':
                puzzle_state['three_stage_servo'] = 1
            elif cmd == 'SERVO_PUZZLE_PHASE_2':
                puzzle_state['three_stage_servo'] = 2
            elif cmd == 'SERVO_PUZZLE_PHASE_3':
                puzzle_state['three_stage_servo'] = 3
            elif cmd == 'SERVO_PUZZLE_COMPLETE':
                puzzle_state['three_stage_servo'] = 4
                print("Three-stage servo puzzle complete!")
            elif cmd == 'DEAD_DROP_SOLVED':
                puzzle_state['dead_drop_solved'] = True
            elif cmd == 'TOUCH_LEDS_ACTIVE':
                puzzle_state['touch_leds_active'] = True
            elif cmd == 'STATUS_QUERY':
                # Respond with current state
                await send_udp_command(f"STATUS_ROOM:{json.dumps(puzzle_state)}", addr[0])
            
        except OSError as e:
            if e.errno == 11:  # EAGAIN
                await asyncio.sleep_ms(10)
            else:
                print(f"UDP recv error: {e}")
        except Exception as e:
            print(f"UDP parse error: {e}")
            await asyncio.sleep_ms(10)

async def heartbeat_sender():
    """Send periodic heartbeat so props know room brain is alive"""
    while True:
        await send_udp_command(f"HEARTBEAT:{DEVICE_ID}")
        await asyncio.sleep_ms(HEARTBEAT_INTERVAL_MS)

# === EVENT HANDLERS ===
async def on_laser_stage_1():
    """Laser hit first target - curtain to 50%"""
    print("EVENT: Laser stage 1 - curtain half open")
    puzzle_state['curtain_position'] = 1
    # No direct action needed - laser controller handles curtain

async def on_laser_stage_2():
    """Laser complete - curtain fully open"""
    print("EVENT: Laser stage 2 - curtain fully open, back wall revealed")
    puzzle_state['curtain_position'] = 2

async def vault_unlock():
    """Final vault unlock - trigger maglocks"""
    print("*** VAULT UNLOCK ***")
    puzzle_state['vault_unlocked'] = True
    TRIGGER_MAGLOCK_1.value(1)
    TRIGGER_MAGLOCK_2.value(1)
    # Victory fanfare
    asyncio.create_task(victory_sequence())

async def victory_sequence():
    """LED flash + audio cue"""
    for _ in range(5):
        STATUS_LED.value(0)
        await asyncio.sleep_ms(100)
        STATUS_LED.value(1)
        await asyncio.sleep_ms(100)
    print("Victory sequence complete!")

async def reset_room():
    """Master reset - return all to initial state"""
    global puzzle_state
    print("\n*** ROOM RESET INITIATED ***")
    
    # Increment reset counter
    puzzle_state['room_reset_count'] += 1
    
    # Notify all props to reset
    await send_udp_command("ROOM_RESET")
    
    # Reset local state
    puzzle_state['logged_in'] = False
    puzzle_state['vault_unlocked'] = False
    puzzle_state['inventory_searched'] = False
    puzzle_state['security_cleared'] = False
    puzzle_state['laser_stage'] = 0
    puzzle_state['curtain_position'] = 0
    puzzle_state['three_stage_servo'] = 0
    puzzle_state['touch_leds_active'] = False
    puzzle_state['dead_drop_solved'] = False
    
    # Release maglocks
    TRIGGER_MAGLOCK_1.value(0)
    TRIGGER_MAGLOCK_2.value(0)
    
    print("All systems reset")
    print(f"Reset count: {puzzle_state['room_reset_count']}")

def inventory_page():
    content = """
    <h2>📦 Inventory Database</h2>
    <p>Current estate sale catalog. Search for specific items using the database.</p>
    
    <table>
        <tr>
            <th>Lot #</th>
            <th>Item</th>
            <th>Category</th>
            <th>Status</th>
        </tr>
        <tr>
            <td>001</td>
            <td>Victorian Writing Desk</td>
            <td>Furniture</td>
            <td>Available</td>
        </tr>
        <tr>
            <td>002</td>
            <td>Oil Painting - "Sunset Harbor"</td>
            <td>Art</td>
            <td>Available</td>
        </tr>
        <tr>
            <td>003</td>
            <td>Brass Samurai Helmet</td>
            <td>Antiquities</td>
            <td><strong>MOVED TO VAULT</strong></td>
        </tr>
        <tr>
            <td>004</td>
            <td>Crystal Chandelier</td>
            <td>Lighting</td>
            <td>Available</td>
        </tr>
        <tr>
            <td>005</td>
            <td>First Edition Books (Set of 12)</td>
            <td>Books</td>
            <td>Available</td>
        </tr>
        <tr>
            <td>006</td>
            <td>Gold Pocket Watch (1887)</td>
            <td>Jewelry</td>
            <td><strong>MOVED TO VAULT</strong></td>
        </tr>
        <tr>
            <td>007</td>
            <td>Marble Bust - Roman Style</td>
            <td>Sculpture</td>
            <td>Available</td>
        </tr>
        <tr>
            <td>008</td>
            <td>📁 [CLASSIFIED ARTIFACT]</td>
            <td>Special Collection</td>
            <td><span style="color: #f44336;">SECURE STORAGE</span></td>
        </tr>
    </table>
    
    <div class="card">
        <h3>🔍 Item Details - Lot #008</h3>
        <p><strong>Access Code:</strong> <span style="font-family: monospace; background: #333; color: #0f0; padding: 5px 10px;">1847</span></p>
        <p><strong>Location:</strong> Secure Vault, Sector 7</p>
        <p><strong>Notes:</strong> Requires dual authentication. Contact security desk.</p>
    </div>
    """
    return base_page("Inventory", content)

def security_page():
    content = """
    <h2>🔒 Security Systems</h2>
    <p>Security clearance verification required for vault access.</p>
    
    <div class="card">
        <h3>Security Log - Recent Events</h3>
        <div class="terminal">
<pre>[09:47] ALERT: Unauthorized access attempt - East Wing
[09:52] SYSTEM: Vault lockdown initiated
[10:15] NOTICE: Security protocols updated
[10:33] CHECK: Perimeter sensors - NORMAL
[11:02] AUTH: Field Agent login - GRANTED</pre>
        </div>
    </div>
    
    <div class="card">
        <h3>🔐 Clearance Verification</h3>
        <p>Enter the artifact access code from inventory to proceed:</p>
        <form method="GET" action="/security">
            <input type="text" name="code" placeholder="Enter code" maxlength="10" style="width: 200px;">
            <button type="submit" style="width: auto; padding: 12px 30px; margin-left: 10px;">Verify</button>
        </form>
    </div>
    """
    return base_page("Security", content)

# === WEB SERVER (from auction_house_intranet) ===
# [Include the base_page, login_page, inventory_page, etc. from auction_house_intranet_async.py]
# For brevity, placeholder - you'll copy the HTML templates from auction_house_intranet_async.py

def base_page(title, content, nav=True):
    nav_html = """
    <nav>
        <a href="/">Home</a>
        <a href="/inventory">Inventory</a>
        <a href="/security">Security</a>
        <a href="/vault">Vault</a>
        <a href="/status">Status</a>
    </nav>
    """ if nav else ""
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title} | Estate Auction Systems</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            color: #333;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background: rgba(255,255,255,0.95);
            padding: 20px;
            border-radius: 10px 10px 0 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        header h1 {{
            color: #1e3c72;
            font-size: 24px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .logo {{
            width: 40px;
            height: 40px;
            background: #1e3c72;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }}
        nav {{
            background: #1e3c72;
            padding: 0;
            border-radius: 0;
        }}
        nav a {{
            display: inline-block;
            color: white;
            text-decoration: none;
            padding: 15px 20px;
            transition: background 0.3s;
        }}
        nav a:hover {{
            background: rgba(255,255,255,0.1);
        }}
        .content {{
            background: rgba(255,255,255,0.95);
            padding: 30px;
            border-radius: 0 0 10px 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            min-height: 400px;
        }}
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin: 20px 0;
        }}
        .status-card {{
            background: #f5f5f5;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #ccc;
        }}
        .status-card.ok {{ border-left-color: #4caf50; }}
        .status-card.warn {{ border-left-color: #ff9800; }}
        .status-card.locked {{ border-left-color: #f44336; }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .live {{ 
            color: #4caf50; 
            animation: pulse 2s infinite;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1><div class="logo">EA</div> Estate Auction Systems</h1>
        </header>
        {nav_html}
        <div class="content">
            {content}
        </div>
        <footer style="text-align: center; padding: 20px; color: rgba(255,255,255,0.7);">
            <p>Room Controller v2.0 | Device: {DEVICE_ID}</p>
            <p>UDP Mesh: {len(puzzle_state['last_udp_seen'])} devices online</p>
        </footer>
    </div>
</body>
</html>"""

def status_page():
    """Real-time room status page"""
    laser_status = ['🔴 Inactive', '🟡 Stage 1', '🟢 Complete'][puzzle_state['laser_stage']]
    servo_status = ['⚪ Inactive', '🔵 Phase 1', '🔵 Phase 2', '🔵 Phase 3', '🟢 Complete'][puzzle_state['three_stage_servo']]
    
    content = f"""
    <h2>📊 Room Status Dashboard</h2>
    <div class="status-grid">
        <div class="status-card {'ok' if puzzle_state['laser_stage'] == 2 else 'warn'}">
            <h4>Laser Puzzle</h4>
            <p>{laser_status}</p>
            <small>Curtain: {['Closed', '50%', 'Open'][puzzle_state['curtain_position']]}</small>
        </div>
        <div class="status-card {'ok' if puzzle_state['three_stage_servo'] == 4 else 'warn'}">
            <h4>Servo Alignment</h4>
            <p>{servo_status}</p>
        </div>
        <div class="status-card {'ok' if puzzle_state['dead_drop_solved'] else 'locked'}">
            <h4>Dead Drop</h4>
            <p>{'🟢 Solved' if puzzle_state['dead_drop_solved'] else '🔴 Unsolved'}</p>
        </div>
        <div class="status-card {'ok' if puzzle_state['vault_unlocked'] else 'locked'}">
            <h4>Vault</h4>
            <p>{'🔓 UNLOCKED' if puzzle_state['vault_unlocked'] else '🔒 Locked'}</p>
        </div>
    </div>
    
    <h3>🖥️ Connected Devices</h3>
    <ul>
    """
    
    for device, last_seen in puzzle_state['last_udp_seen'].items():
        ago = time.ticks_diff(time.ticks_ms(), last_seen) // 1000
        status = '🟢 <span class="live">Live</span>' if ago < 2 else f'⚪ {ago}s ago'
        content += f"<li>{device}: {status}</li>"
    
    if not puzzle_state['last_udp_seen']:
        content += "<li>No devices reporting (yet)</li>"
    
    content += """
    </ul>
    """
    
    return base_page("System Status", content)

# === WEB SERVER LOGIC (simplified) ===
import select

def get_path(request):
    try:
        lines = request.decode().split('\r\n')
        return lines[0].split(' ')[1].split('?')[0]
    except:
        return '/'

def parse_params(request):
    params = {}
    try:
        lines = request.decode().split('\r\n')
        if '?' in lines[0]:
            query = lines[0].split('?')[1].split(' ')[0]
            for pair in query.split('&'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    params[k] = v
    except:
        pass
    return params

async def http_server():
    """Async HTTP server"""
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(5)
    s.setblocking(False)
    print(f"HTTP server on port 80...")
    
    while True:
        try:
            cl, addr = s.accept()
            cl.setblocking(True)
            
            # Quick request read
            request = b""
            start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start) < 1000:
                try:
                    chunk = cl.recv(2048)
                    if chunk:
                        request += chunk
                        if b"\r\n\r\n" in request:
                            break
                except:
                    break
            
            if not request:
                cl.close()
                continue
            
            path = get_path(request)
            params = parse_params(request)
            
            # Routes
            if path == '/' and not puzzle_state['logged_in']:
                html = base_page("Login", '''
                <div style="max-width: 400px; margin: 50px auto; background: white; padding: 40px; border-radius: 10px;">
                    <h2>Staff Login</h2>
                    <form method="GET" action="/login">
                        <input type="text" name="user" placeholder="Username" style="width: 100%; padding: 12px; margin: 10px 0;">
                        <input type="password" name="pass" placeholder="Password" style="width: 100%; padding: 12px; margin: 10px 0;">
                        <button type="submit" style="width: 100%; padding: 15px; background: #1e3c72; color: white; border: none; border-radius: 5px;">Sign In</button>
                    </form>
                    <p style="margin-top: 20px; font-size: 12px; color: #999;">Hint: Check employee badge</p>
                </div>
                ''', nav=False)
                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
            
            elif path == '/login':
                if params.get('user') == 'agent' and params.get('pass') == 'estate2024':
                    puzzle_state['logged_in'] = True
                    response = "HTTP/1.0 302 Found\r\nLocation: /\r\n\r\n"
                else:
                    response = "HTTP/1.0 302 Found\r\nLocation: /\r\n\r\n"
            
            elif path == '/':
                html = base_page("Dashboard", f"""
                    <h2>Welcome, Field Agent</h2>
                    <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3>System Status</h3>
                        <p>Laser Puzzle: {['Inactive', 'Stage 1', 'Complete'][puzzle_state['laser_stage']]}</p>
                        <p>Servo Puzzle: Phase {puzzle_state['three_stage_servo']}</p>
                        <p>Vault: {'Unlocked' if puzzle_state['vault_unlocked'] else 'Locked'}</p>
                    </div>
                    <p>Use the navigation to access inventory, security, and vault systems.</p>
                """)
                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
            
            elif path == '/inventory':
                html = inventory_page()
                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
            
            elif path == '/security':
                code = params.get('code', '')
                if code == '1847':
                    puzzle_state['security_cleared'] = True
                    html = base_page("Security", '''
                    <h2>🔒 Security Systems</h2>
                    
                    <div class="success">✓ Clearance verified. Vault access authorized.</div>
                    
                    <div class="card">
                        <h3>Security Log - Updated</h3>
                        <div class="terminal">
<pre>[09:47] ALERT: Unauthorized access attempt - East Wing
[09:52] SYSTEM: Vault lockdown initiated
[10:15] NOTICE: Security protocols updated
[10:33] CHECK: Perimeter sensors - NORMAL
[11:02] AUTH: Field Agent login - GRANTED
[<span style="color: #ffff00;">NOW</span>] <span style="color: #00ff00;">CLEARANCE: Vault access authorized</span></pre>
                        </div>
                    </div>
                    
                    <div class="card" style="border-left-color: #4caf50;">
                        <h3>✓ Authentication Complete</h3>
                        <p>You may now access the vault. Proceed to the Vault page to complete your mission.</p>
                        <p style="text-align: center; margin-top: 20px;">
                            <a href="/vault" style="display: inline-block; padding: 15px 40px; background: #1e3c72; color: white; text-decoration: none; border-radius: 5px; font-size: 16px;">Enter Vault →</a>
                        </p>
                    </div>
                    ''')
                    response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
                elif code:
                    html = base_page("Security", '''
                    <h2>🔒 Security Systems</h2>
                    
                    <div class="card">
                        <h3>Security Log - Recent Events</h3>
                        <div class="terminal">
<pre>[09:47] ALERT: Unauthorized access attempt - East Wing
[09:52] SYSTEM: Vault lockdown initiated
[10:15] NOTICE: Security protocols updated
[10:33] CHECK: Perimeter sensors - NORMAL
[11:02] AUTH: Field Agent login - GRANTED</pre>
                        </div>
                    </div>
                    
                    <div class="error">Invalid code. Access denied.</div>
                    
                    <div class="card">
                        <h3>🔐 Clearance Verification</h3>
                        <p>Enter the artifact access code from inventory to proceed:</p>
                        <form method="GET" action="/security">
                            <input type="text" name="code" placeholder="Enter code" maxlength="10" style="width: 200px;">
                            <button type="submit" style="width: auto; padding: 12px 30px; margin-left: 10px;">Verify</button>
                        </form>
                    </div>
                    ''')
                    response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
                else:
                    html = security_page()
                    response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
            
            elif path == '/status':
                html = status_page()
                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
            
            elif path == '/vault':
                if not puzzle_state['logged_in']:
                    response = "HTTP/1.0 302 Found\r\nLocation: /\r\n\r\n"
                elif puzzle_state['security_cleared'] and not puzzle_state['vault_unlocked']:
                    # Unlock the vault!
                    await vault_unlock()
                    puzzle_state['vault_unlocked'] = True
                    html = base_page("Vault Unlocked", '''
                    <h2>🔓 VAULT UNLOCKED</h2>
                    
                    <div style="text-align: center; padding: 40px;">
                        <div style="font-size: 72px; margin-bottom: 20px;">🔓</div>
                        <h2 style="color: #4caf50; font-size: 32px;">ACCESS GRANTED</h2>
                        <p style="font-size: 18px; margin: 20px 0;">The secure compartment has been unlocked.</p>
                        <p style="font-family: monospace; background: #1a1a1a; color: #00ff00; padding: 20px; border-radius: 5px; display: inline-block;">
                            GPIO TRIGGER: ACTIVATED<br>
                            RELAY: ENGAGED<br>
                            MAGLOCK: RELEASED
                        </p>
                    </div>
                    
                    <div class="card" style="border-left-color: #4caf50;">
                        <h3>🎯 Mission Status: COMPLETE</h3>
                        <p>You have successfully bypassed security and unlocked the vault.</p>
                        <p>The artifact is now accessible. Physical lock has been disengaged.</p>
                    </div>
                    ''')
                    response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
                elif puzzle_state['vault_unlocked']:
                    html = base_page("Vault Unlocked", '''
                    <h2>🔓 VAULT UNLOCKED</h2>
                    <p>Access granted. Physical maglocks have been released.</p>
                    ''')
                    response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
                else:
                    html = security_page()
                    response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
            
            else:
                response = "HTTP/1.0 404 Not Found\r\n\r\nNot found"
            
            cl.send(response.encode())
            cl.close()
            
        except OSError as e:
            if e.errno == 11:
                await asyncio.sleep_ms(10)
        except Exception as e:
            print(f"HTTP error: {e}")
            await asyncio.sleep_ms(10)

# === MAIN LOOP ===
async def reset_monitor():
    """Monitor physical reset button"""
    while True:
        if RESET_BUTTON.value() == 0:  # Pressed
            print("Physical reset button pressed")
            await reset_room()
            await asyncio.sleep_ms(1000)  # Debounce
        await asyncio.sleep_ms(50)

async def main():
    print("\n" + "="*50)
    print("ART HEIST ROOM BRAIN - Starting...")
    print("="*50)
    print(f"WiFi: {WIFI_SSID}")
    print(f"IP: {ip}")
    print(f"UDP Port: {UDP_PORT}")
    print("\nConnect to WiFi, then visit http://192.168.4.1")
    print("="*50 + "\n")
    
    # Start all tasks
    await asyncio.gather(
        http_server(),      # Web intranet
        udp_listener(),     # Mesh network listener
        heartbeat_sender(), # Keep-alive broadcast
        reset_monitor()     # Physical reset button
    )

if __name__ == "__main__":
    asyncio.run(main())
