# LCD1602 I2C Driver for ESP32
# Works with PCF8574 backpack (address 0x27)

from machine import Pin, I2C
import time

# LCD Commands
LCD_RS = 0x01  # Register select
LCD_RW = 0x02  # Read/write
LCD_EN = 0x04  # Enable
LCD_BACKLIGHT = 0x08  # Backlight on
LCD_CMD = 0x00  # Send command mode

# LCD Commands
LCD_CLEAR = 0x01
LCD_HOME = 0x02
LCD_ENTRY_MODE = 0x04
LCD_DISPLAY_ON = 0x0C
LCD_DISPLAY_OFF = 0x08
LCD_CURSOR_OFF = 0x04
LCD_4BIT_MODE = 0x20

class LCD1602:
    def __init__(self, i2c=None, sda=21, scl=22, address=0x27):
        if i2c is None:
            i2c = I2C(0, sda=Pin(sda), scl=Pin(scl), freq=400000)
        self.i2c = i2c
        self.address = address
        self.backlight = LCD_BACKLIGHT
        
        # Initialize the LCD in 4-bit mode
        time.sleep_ms(50)  # Power-on delay
        self._write_nibble(0x30)  # Function set 8-bit
        time.sleep_ms(5)
        self._write_nibble(0x30)  # Function set 8-bit
        time.sleep_us(150)
        self._write_nibble(0x30)  # Function set 8-bit
        self._write_nibble(0x20)  # Set 4-bit mode
        self._send_cmd(0x28)  # 2 lines, 5x8 dots
        self._send_cmd(0x0C)  # Display on, cursor off
        self._send_cmd(0x06)  # Entry mode
        self.clear()
        
    def _write_nibble(self, nibble):
        data = nibble | self.backlight
        self.i2c.writeto(self.address, bytearray([data | LCD_EN]))
        time.sleep_us(1)
        self.i2c.writeto(self.address, bytearray([data & ~LCD_EN]))
        time.sleep_us(50)
        
    def _send(self, data, mode):
        data = data | mode | self.backlight
        self._write_nibble(data & 0xF0)  # High nibble
        self._write_nibble(data << 4 & 0xF0)  # Low nibble
        time.sleep_us(50)
        
    def _send_cmd(self, cmd):
        self._send(cmd, LCD_CMD)
        
    def _send_data(self, data):
        self._send(data, LCD_RS)
        
    def clear(self):
        self._send_cmd(LCD_CLEAR)
        time.sleep_ms(2)
        
    def home(self):
        self._send_cmd(LCD_HOME)
        time.sleep_ms(2)
        
    def set_cursor(self, row, col):
        offsets = [0x00, 0x40]  # Row 0 and 1 offsets
        if row < 2 and col < 16:
            self._send_cmd(0x80 | offsets[row] + col)
            
    def print(self, text):
        for char in text:
            self._send_data(ord(char))
            
    def print_at(self, row, col, text):
        self.set_cursor(row, col)
        self.print(text)
        
    def clear_line(self, row):
        self.set_cursor(row, 0)
        for _ in range(16):
            self._send_data(ord(' '))
        self.set_cursor(row, 0)


def test():
    print("LCD1602 Test - Connect LCD to H13 (SDA=21, SCL=22)")
    lcd = LCD1602(sda=21, scl=22, address=0x27)
    
    # Test sequence
    lcd.clear()
    lcd.print_at(0, 0, "Art Heist Room")
    lcd.print_at(1, 0, "Initialize...")
    time.sleep(2)
    
    lcd.clear()
    lcd.print_at(0, 0, "System Ready")
    lcd.print_at(1, 0, "Awaiting Input")
    
    print("Test complete - check LCD")
    

if __name__ == "__main__":
    test()