# Auction House Intranet - ESP32 Multi-Page Puzzle
# A fake corporate intranet with multiple stages leading to vault unlock
# NON-BLOCKING VERSION using asyncio

import network
import socket
import machine
import time
import os
import asyncio
import select

# === CONFIGURATION ===
WIFI_SSID = "AUCTION_HOUSE"
WIFI_PASSWORD = ""  # Open network for easy player access
TRIGGER_PIN = 5  # GPIO5 - relay/maglock (remapped from GPIO4)
# Note: Ensure main.py also remaps TRIGGER_MAGLOCK_1_PIN to 5 trigger

# Puzzle state (simple in-memory tracking)
puzzle_state = {
    'logged_in': False,
    'vault_unlocked': False,
    'inventory_searched': False,
    'security_cleared': False
}

# === SETUP ===
trigger = machine.Pin(TRIGGER_PIN, machine.Pin.OUT)
trigger.value(0)

status_led = machine.Pin(2, machine.Pin.OUT)
status_led.value(1)

# === WIFI ACCESS POINT ===
ap = network.WLAN(network.AP_IF)
ap.active(True)
if WIFI_PASSWORD:
    ap.config(essid=WIFI_SSID, password=WIFI_PASSWORD, authmode=network.AUTH_WPA_WPA2_PSK)
else:
    ap.config(essid=WIFI_SSID)

print(f"AP started: {WIFI_SSID}")
print(f"IP address: {ap.ifconfig()[0]}")

async def blink_led():
    """Non-blocking LED blink sequence during startup"""
    for _ in range(3):
        status_led.value(0)
        await asyncio.sleep(0.2)
        status_led.value(1)
        await asyncio.sleep(0.2)
    status_led.value(0)

# === HTML TEMPLATES ===

def base_page(title, content, nav=True):
    nav_html = """
    <nav>
        <a href="/">Home</a>
        <a href="/inventory">Inventory</a>
        <a href="/security">Security</a>
        <a href="/vault">Vault</a>
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
        .login-box {{
            max-width: 400px;
            margin: 50px auto;
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        .login-box h2 {{
            color: #1e3c72;
            margin-bottom: 10px;
        }}
        .login-box p {{
            color: #666;
            margin-bottom: 30px;
        }}
        input[type="text"], input[type="password"] {{
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
            transition: border-color 0.3s;
        }}
        input[type="text"]:focus, input[type="password"]:focus {{
            outline: none;
            border-color: #1e3c72;
        }}
        button {{
            width: 100%;
            padding: 15px;
            background: #1e3c72;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: background 0.3s;
        }}
        button:hover {{
            background: #2a5298;
        }}
        .error {{
            color: #d32f2f;
            background: #ffebee;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .success {{
            color: #388e3c;
            background: #e8f5e9;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .card {{
            background: #f5f5f5;
            padding: 20px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 4px solid #1e3c72;
        }}
        .card h3 {{
            color: #1e3c72;
            margin-bottom: 10px;
        }}
        .locked {{
            opacity: 0.5;
            pointer-events: none;
        }}
        .unlock-hint {{
            background: #fff3e0;
            border-left-color: #ff9800;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #1e3c72;
            color: white;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }}
        .status-ok {{ background: #4caf50; }}
        .status-warn {{ background: #ff9800; }}
        .status-locked {{ background: #f44336; }}
        .terminal {{
            background: #1a1a1a;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .terminal pre {{
            margin: 0;
            line-height: 1.6;
        }}
        footer {{
            text-align: center;
            padding: 20px;
            color: rgba(255,255,255,0.7);
            font-size: 12px;
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
        <footer>
            <p>© 2024 Estate Auction Systems | Authorized Personnel Only</p>
            <p>Server: ESP32-LOCAL | Connection: Secure</p>
        </footer>
    </div>
</body>
</html>"""

# === PAGE CONTENT ===

def login_page(error=None):
    error_msg = f'<div class="error">{error}</div>' if error else ''
    content = f"""
    <div class="login-box">
        <h2>🔐 Staff Login</h2>
        <p>Enter your credentials to access the auction house intranet.</p>
        {error_msg}
        <form method="GET" action="/login">
            <input type="text" name="user" placeholder="Username" required>
            <input type="password" name="pass" placeholder="Password" required>
            <button type="submit">Sign In</button>
        </form>
        <p style="margin-top: 20px; font-size: 12px; color: #999;">
            Hint: Check the employee badge found in the coat check.
        </p>
    </div>
    """
    return base_page("Login", content, nav=False)

def home_page():
    content = """
    <h2>🏠 Welcome to Estate Auction Systems</h2>
    <p>You are logged in as: <strong>Field Agent</strong></p>
    
    <div class="card">
        <h3>📋 System Status</h3>
        <p><span class="status-indicator status-ok"></span> Inventory Database: Online</p>
        <p><span class="status-indicator status-ok"></span> Security Systems: Active</p>
        <p><span class="status-indicator status-locked"></span> Vault Access: Restricted</p>
    </div>
    
    <div class="card">
        <h3>📢 Recent Announcements</h3>
        <p><strong>URGENT:</strong> The estate sale has been compromised. All high-value items 
        have been moved to secure storage. Contact security for vault access protocols.</p>
        <p style="margin-top: 10px; font-size: 12px; color: #666;">Posted: Today at 09:47 AM</p>
    </div>
    
    <div class="card unlock-hint">
        <h3>🔍 Mission Objective</h3>
        <p>Locate the target artifact in the inventory database. Security clearance 
        required for vault access. Complete all checks to proceed.</p>
    </div>
    """
    return base_page("Dashboard", content)

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

def security_cleared_page():
    content = """
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
        <a href="/vault" style="display: inline-block; margin-top: 15px; padding: 12px 30px; background: #4caf50; color: white; text-decoration: none; border-radius: 5px;">→ Open Vault</a>
    </div>
    """
    return base_page("Security", content)

def vault_unlocked_page():
    content = """
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
    
    <p style="text-align: center; margin-top: 30px;">
        <a href="/" style="display: inline-block; padding: 15px 40px; background: #1e3c72; color: white; text-decoration: none; border-radius: 5px; font-size: 16px;">← Return to Dashboard</a>
    </p>
    """
    return base_page("Vault Unlocked", content)

# === REQUEST HANDLING ===

def parse_params(request):
    """Extract GET parameters from request"""
    params = {}
    try:
        lines = request.decode().split('\r\n')
        first_line = lines[0]
        if '?' in first_line:
            query = first_line.split('?')[1].split(' ')[0]
            for pair in query.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    params[key] = value.replace('+', ' ')
    except:
        pass
    return params

def get_path(request):
    """Extract path from request"""
    try:
        lines = request.decode().split('\r\n')
        first_line = lines[0]
        path = first_line.split(' ')[1]
        return path.split('?')[0]
    except:
        return '/'

async def handle_request(cl, addr):
    """Handle a single HTTP request asynchronously"""
    try:
        # Set socket to non-blocking for recv
        cl.setblocking(False)
        
        # Read request with timeout using asyncio
        request = b""
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < 2000:  # 2 second timeout
            try:
                chunk = cl.recv(2048)
                if chunk:
                    request += chunk
                    # Check if we have the full HTTP request
                    if b"\r\n\r\n" in request:
                        break
                else:
                    # No data yet, yield control
                    await asyncio.sleep_ms(10)
            except OSError as e:
                if e.errno == 11:  # EAGAIN - no data available
                    await asyncio.sleep_ms(10)
                else:
                    raise
        
        if not request:
            cl.close()
            return
        
        path = get_path(request)
        params = parse_params(request)
        
        # Route handling
        if path == '/' or path == '/index':
            if puzzle_state['logged_in']:
                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + home_page()
            else:
                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + login_page()
        
        elif path == '/login':
            user = params.get('user', '')
            password = params.get('pass', '')
            if user == 'agent' and password == 'estate2024':
                puzzle_state['logged_in'] = True
                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + home_page()
            else:
                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + login_page("Invalid credentials")
        
        elif path == '/inventory':
            if not puzzle_state['logged_in']:
                response = "HTTP/1.0 302 Found\r\nLocation: /\r\n\r\n"
            else:
                puzzle_state['inventory_searched'] = True
                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + inventory_page()
        
        elif path == '/security':
            if not puzzle_state['logged_in']:
                response = "HTTP/1.0 302 Found\r\nLocation: /\r\n\r\n"
            else:
                code = params.get('code', '')
                if code == '1847':
                    puzzle_state['security_cleared'] = True
                    response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + security_cleared_page()
                elif code:
                    page = security_page().replace(
                        '<button type="submit"',
                        '<div class="error">Invalid code. Access denied.</div><button type="submit"'
                    )
                    response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + page
                else:
                    response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + security_page()
        
        elif path == '/vault':
            if not puzzle_state['logged_in']:
                response = "HTTP/1.0 302 Found\r\nLocation: /\r\n\r\n"
            elif puzzle_state['security_cleared'] and not puzzle_state['vault_unlocked']:
                # Unlock the vault!
                puzzle_state['vault_unlocked'] = True
                trigger.value(1)  # ACTIVATE RELAY/MAGLOCK
                print("*** VAULT UNLOCKED! Trigger activated ***")
                # Blink LED async
                asyncio.create_task(blink_led())
                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + vault_unlocked_page()
            elif puzzle_state['vault_unlocked']:
                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + vault_unlocked_page()
            else:
                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + security_page()  # Show security page if not cleared
        
        else:
            response = "HTTP/1.0 404 Not Found\r\n\r\nPage not found"
        
        # Send response asynchronously
        cl.setblocking(True)  # Blocking is OK for sending in most cases
        cl.send(response.encode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cl.close()

# === WEB SERVER ===

async def start_server():
    """Async web server - non-blocking accept"""
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(5)
    s.setblocking(False)  # NON-BLOCKING!
    print(f"Server listening on port 80...")
    
    while True:
        try:
            # Non-blocking accept
            cl, addr = s.accept()
            print(f"Client: {addr}")
            # Handle request in background - don't block the accept loop
            asyncio.create_task(handle_request(cl, addr))
        except OSError as e:
            if e.errno == 11:  # EAGAIN - no connection waiting
                await asyncio.sleep_ms(10)  # Yield to other tasks
            else:
                raise

# === MAIN ===
async def main():
    """Main async entry point"""
    print("\n" + "="*50)
    print("AUCTION HOUSE INTRANET - ESP32 SERVER (asyncio)")
    print("="*50)
    print(f"WiFi: {WIFI_SSID}")
    print(f"IP: {ap.ifconfig()[0]}")
    print(f"\nPUZZLE FLOW:")
    print("1. Connect to WiFi, go to http://192.168.4.1")
    print("2. Login: user=agent, pass=estate2024")
    print("3. Check Inventory → find code 1847")
    print("4. Go to Security → enter code 1847")
    print("5. Go to Vault → maglock releases!")
    print("="*50 + "\n")
    
    # Start server
    await start_server()

if __name__ == "__main__":
    asyncio.run(main())
