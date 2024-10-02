'''
這是Micropython
sh1107.py 使用方法
import sh1107
import Pico_Wear
display, mpu = Pico_Ware_Tools.Pico_Ware_Init()

基本繪圖:
畫點: display.pixel(x, y, color)
畫線: display.line(x1, y1, x2, y2, color)
畫矩形: display.draw_rectangle(x, y, width, height, color)
填充矩形: display.fill_rectangle(x, y, width, height, color)
畫圓: display.draw_circle(x, y, radius, color)
填充圓: display.fill_circle(x, y, radius, color)
畫三角形: display.draw_triangle(x0, y0, x1, y1, x2, y2, color)
填充三角形: display.fill_triangle(x0, y0, x1, y1, x2, y2, color)
文字顯示:
顯示文字: display.text("Hello", x, y, color)
位圖顯示:
繪製位圖: display.drawBitmap(x, y, bitmap, width, height)
顯示控制:
更新顯示: display.show()
清除顯示: display.fill(0) 然後 display.show()
調整對比度: display.contrast(contrast_value)
屏幕翻轉: display.rotate(flag)
反轉顯示: display.invert(invert_flag)
電源管理:
開啟顯示: display.poweron()
關閉顯示: display.poweroff()
睡眠模式: display.sleep(sleep_flag)
注意:
顏色使用1表示點亮，0表示熄滅
座標系統從左上角(0,0)開始
在進行任何繪圖操作後，需要調用display.show()來更新顯示
畫面更新使用單獨TimeToDo 建議60FPS 如果效能不佳再往下調整
'''
from machine import Pin, I2C, RTC, Timer , mem32
from micropython import const
import utime as time
import framebuf
import math
import random

# Register definitions
_SET_CONTRAST        = const(0x81)
_SET_NORM_INV        = const(0xa6)
_SET_DISP            = const(0xae)
_SET_SCAN_DIR        = const(0xc0)
_SET_SEG_REMAP       = const(0xa0)
_LOW_COLUMN_ADDRESS  = const(0x00)
_HIGH_COLUMN_ADDRESS = const(0x10)
_SET_PAGE_ADDRESS    = const(0xB0)
_SET_DISPLAY_OFFSET  = const(0xD3)
_SET_DISPLAY_CLOCK   = const(0xD5)
_SET_PRECHARGE       = const(0xD9)
_SET_COM_PINS        = const(0xDA)
_SET_VCOM_DESELECT   = const(0xDB)
_CHARGE_PUMP         = const(0x8D)



# SH1107 class, inherits from framebuf.FrameBuffer
class SH1107(framebuf.FrameBuffer):
    def __init__(self, width, height, external_vcc):
        # Initialize screen width, height, and external VCC option
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        
        self.init_display()

    # Initialize the display
    def init_display(self):
        self.reset()
        self.poweroff()
        #self.write_cmd(0xD3)  # 設置顯示偏移
        #self.write_cmd(0x02)  # 偏移量，根據實際情況調整

        self.write_cmd(0xAE)  # Display OFF
        self.write_cmd(0xD5)  # Set Display Clock Divide Ratio/Oscillator Frequency
        self.write_cmd(241)  # 设置更高的频率以减少闪烁
        self.write_cmd(0xA8)  # Set Multiplex Ratio
        self.write_cmd(0x7F)  # 128MUX（对于128x128显示器）
        self.write_cmd(0xD3)  # Set Display Offset
        self.write_cmd(0x02)  # 2px
        
 
        self.write_cmd(0x81)  # Set Contrast Control
        self.write_cmd(0xFF)  # 最大对比度
        self.write_cmd(0xD9)  # Set Pre-charge Period
        self.write_cmd(215)  # 增加预充电周期以提高亮度
        self.write_cmd(0xDB)  # Set VCOMH Deselect Level
        self.write_cmd(0x30)  # VCOM Deselect Level
        self.write_cmd(0xAD)  # Set DC-DC Control Mode Set
        self.write_cmd(0x8A)  # 启用内部 DC-DC 转换器
        self.write_cmd(0xA4)  # Entire Display ON (resume)
        self.write_cmd(0xA6)  # Set Normal Display
        self.write_cmd(0xAF)  # Display ON


        self.fill(0)
        self.show()

    # Turn off the display
    def poweroff(self):
        self.write_cmd(_SET_DISP | 0x00)

    # Turn on the display
    def poweron(self):
        self.write_cmd(_SET_DISP | 0x01)

    # Rotate the display
    def rotate(self, flag, update=True):
        if flag:
            self.write_cmd(_SET_SEG_REMAP | 0x01)  # 垂直翻轉顯示
            self.write_cmd(_SET_SCAN_DIR | 0x08)  # 水平翻轉顯示
        else:
            self.write_cmd(_SET_SEG_REMAP | 0x00)
            self.write_cmd(_SET_SCAN_DIR | 0x00)
        if update:
            self.show()

    # Set sleep mode
    def sleep(self, value):
        self.write_cmd(_SET_DISP | (not value))

    # Adjust contrast
    def contrast(self, contrast):
        self.write_cmd(_SET_CONTRAST)
        self.write_cmd(contrast)

    # Invert display
    def invert(self, invert):
        self.write_cmd(_SET_NORM_INV | (invert & 1))

    # Display the buffer content
    def show(self):
        for page in range(self.height // 8):
            self.write_cmd(_SET_PAGE_ADDRESS | page)
            self.write_cmd(_LOW_COLUMN_ADDRESS | 2)
            self.write_cmd(_HIGH_COLUMN_ADDRESS | 0)
            self.write_data(self.buffer[
                self.width * page:self.width * page + self.width
            ])

    # Reset the display
    def reset(self, res):
        if res is not None:
            res(1)
            time.sleep_ms(1)
            res(0)
            time.sleep_ms(20)
            res(1)
            time.sleep_ms(20)

    # Draw a circle
    def draw_circle(self, x0, y0, radius, color):
        x, y = radius, 0
        err = 1 - radius
        while x >= y:
            self._draw_circle_points(x0, y0, x, y, color)
            y += 1
            if err < 0:
                err += 2 * y + 1
            else:
                x -= 1
                err += 2 * (y - x + 1)

    # Draw a filled circle
    def fill_circle(self, x0, y0, radius, color):
        x, y = radius, 0
        err = 1 - radius
        while x >= y:
            self._draw_filled_circle_lines(x0, y0, x, y, color)
            y += 1
            if err < 0:
                err += 2 * y + 1
            else:
                x -= 1
                err += 2 * (y - x + 1)

    # Draw a triangle with arbitrary points
    def draw_triangle(self, x0, y0, x1, y1, x2, y2, color):
        self.line(x0, y0, x1, y1, color)
        self.line(x1, y1, x2, y2, color)
        self.line(x2, y2, x0, y0, color)

    # Draw a filled triangle with arbitrary points
    def fill_triangle(self, x0, y0, x1, y1, x2, y2, color):
        points = [(x0, y0), (x1, y1), (x2, y2)]
        self._fill_polygon(points, color)

    # Draw a rectangle
    def draw_rectangle(self, x0, y0, width, height, color):
        self.rect(x0, y0, width, height, color)

    # Draw a filled rectangle
    def fill_rectangle(self, x0, y0, width, height, color):
        self.fill_rect(x0, y0, width, height, color)

    # Optimization: Fill polygon
    def _fill_polygon(self, points, color):
        points.sort(key=lambda p: p[1])
        for y in range(points[0][1], points[-1][1] + 1):
            nodes = []
            j = len(points) - 1
            for i in range(len(points)):
                if points[i][1] < y and points[j][1] >= y or points[j][1] < y and points[i][1] >= y:
                    nodes.append(int(points[i][0] + (y - points[i][1]) / (points[j][1] - points[i][1]) * (points[j][0] - points[i][0])))
                j = i
            nodes.sort()
            for i in range(0, len(nodes), 2):
                if i + 1 < len(nodes):
                    self.hline(nodes[i], y, nodes[i + 1] - nodes[i], color)

    # Optimization: Draw circle points
    def _draw_circle_points(self, x0, y0, x, y, color):
        points = [(x0 + x, y0 + y), (x0 - x, y0 + y), (x0 + x, y0 - y), (x0 - x, y0 - y),
                  (x0 + y, y0 + x), (x0 - y, y0 + x), (x0 + y, y0 - x), (x0 - y, y0 - x)]
        for point in points:
            self.pixel(point[0], point[1], color)

    # Optimization: Draw filled circle lines
    def _draw_filled_circle_lines(self, x0, y0, x, y, color):
        self.hline(x0 - x, y0 + y, 2 * x + 1, color)
        self.hline(x0 - x, y0 - y, 2 * x + 1, color)
        self.hline(x0 - y, y0 + x, 2 * y + 1, color)
        self.hline(x0 - y, y0 - x, 2 * y + 1, color)
        
    def drawBitmap(self, x, y, bitmap, width, height):
        """
        繪製位圖到 OLED 顯示器。

        @param x 水平起始位置。
        @param y 垂直起始位置。
        @param bitmap 包含位圖數據的字節陣列。
        @param width 位圖的寬度。
        @param height 位圖的高度。
        """
        for j in range(height):
            for i in range(width):
                # 計算位圖中的索引位置
                index = j * (width // 8) + i // 8
                # 讀取對應的位值
                if (bitmap[index] >> (7 - i % 8)) & 1:
                    self.pixel(x + i, y + j, 1)
                else:
                    self.pixel(x + i, y + j, 0)

# SH1107 I2C class, inherits from SH1107
class SH1107_I2C(SH1107):
    def __init__(self, width, height, i2c, res=None, addr=0x3c, external_vcc=False):
        # Initialize I2C address and reset pin
        self.i2c = i2c
        self.addr = addr
        self.res = res
        self.temp = bytearray(2)
        if res is not None:
            res.init(res.OUT, value=1)
        super().__init__(width, height, external_vcc)

    # Write command
    def write_cmd(self, cmd):
        self.temp[0] = 0x80  # Co=1, D/C#=0
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    # Write data
    def write_data(self, buf):
        self.i2c.writeto(self.addr, b'\x40'+buf)

    # Reset the display
    def reset(self):
        super().reset(self.res)


# 主函数
def main():
    # Initialization code as before
    # Initialize I2C and display
    #====================PICO WEAR Init====================================
    # Power for OLED
    PAD_CONTROL_REGISTER = 0x4001c024
    mem32[PAD_CONTROL_REGISTER] = mem32[PAD_CONTROL_REGISTER] | 0b0110000

    # Set GP9 as output and set to GND, GP8 as output and set to 1
    pin9 = Pin(9, Pin.OUT, value=0)
    pin8 = Pin(8, Pin.OUT, value=0)
    time.sleep(1)
    pin8 = Pin(8, Pin.OUT, value=1)
    i2c1 = I2C(1, scl=Pin(7), sda=Pin(6), freq=400000)
    display = SH1107_I2C(128, 128, i2c1, None, 0x3c)
    
    # Initialize 30 squares
    squares = []
    for _ in range(30):
        square = {
            'x': random.randint(0, 118),  # Ensure squares stay within boundaries
            'y': random.randint(0, 118),
            'size': 10,
            'dx': random.choice([-1, 1]),  # Random movement speed in x direction
            'dy': random.choice([-1, 1]),  # Random movement speed in y direction
            'color': 1
        }
        squares.append(square)
    
    frequency_value = 100
    last_update_time = time.ticks_ms()
    
    # Main loop
    while True:
        # Check if one second has passed
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, last_update_time) >= 1000:
            frequency_value = (frequency_value + 1) % 256  # Increment frequency_value modulo 256
            # Update the display clock setting
            
            
            #display.write_cmd(0xD9)  # Set Display Clock Divide Ratio/Oscillator Frequency
            #display.write_cmd(frequency_value)
            last_update_time = current_time
        
        display.fill(0)  # Clear the display
        for square in squares:
            # Update position
            square['x'] += square['dx']
            square['y'] += square['dy']
            
            # Check for collision with edges and bounce
            if square['x'] <= 0 or square['x'] + square['size'] >= display.width:
                square['dx'] *= -1
            if square['y'] <= 0 or square['y'] + square['size'] >= display.height:
                square['dy'] *= -1
                
            # Draw the square
            display.fill_rectangle(square['x'], square['y'], square['size'], square['size'], square['color'])
        
        # Display the current frequency value
        display.text('Freq: {}'.format(frequency_value), 0, 0, 1)
        
        display.show()  # Update the display


# 当脚本作为主程序运行时，执行 main 函数
if __name__ == '__main__':
    main()
