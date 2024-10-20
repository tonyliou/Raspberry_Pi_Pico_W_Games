# game1.py
import time
import rp2
import math
import random
import gc
import micropython
from machine import Pin, I2C, RTC, Timer, mem32
import libraries.sh1107 as sh1107
from libraries.Mpu6050_mahony import MPU6050
import libraries.TimeToDo as TimeToDo

class OLED:
    def __init__(self, display):
        self.display = display

    def display_text(self, text):
        self.display.fill(0)  # 清空顯示內容
        self.display.text(text[:16], 0, 0)  # 顯示一行最多16個字符
        self.display.show()  # 更新顯示內容

    def draw_circle(self, x, y, radius, color=1):
        self.display.fill_circle(int(x), int(y), radius, color)

    def draw_triangle(self, x0, y0, x1, y1, x2, y2, color=1):
        self.display.draw_triangle(int(x0), int(y0), int(x1), int(y1), int(x2), int(y2), color)

    def clear(self):
        self.display.fill(0)
        # self.display.show()
    
    def fill(self, color):
        self.display.fill(color)

    def show(self):
        self.display.show()

class Game:
    def __init__(self, oled):
        """
        Initialize the game with the OLED display.
        """
        self.oled = oled
        self.is_running = False

        # =================== 遊戲相關變數 ===================
        # 主球的位置和大小
        self.ball_x, self.ball_y = 64, 64
        self.ball_radius = 4

        # 其他球的數據
        self.num_balls = 5  # 可以改變此數值增加或減少敵方球數量
        self.balls = []
        self.triangles = []

        # 初始化 MPU6050
        self.mpu = None

        # 初始化計時器
        self.gyro_update_timer = None
        self.enemy_ball_timer = None
        self.triangle_timer = None
        self.draw_timer = None

    def init_hardware(self):
        """
        初始化硬件，包括 OLED 電源、I2C、MPU6050 等。
        """
        # =====================PICO WARE Init====================================
        # OLED 的電源
        PAD_CONTROL_REGISTER = 0x4001c024
        mem32[PAD_CONTROL_REGISTER] = mem32[PAD_CONTROL_REGISTER] | 0b0110000

        # 設定 GP9 為輸出，並設置輸出(GND), GP8 為輸出，並設置輸出 1
        pin9 = Pin(9, Pin.OUT, value=0)
        pin8 = Pin(8, Pin.OUT, value=0)
        time.sleep(1)
        pin8 = Pin(8, Pin.OUT, value=1)

        # mpu6050 的電源
        PAD_CONTROL_REGISTER = 0x4001c05c
        mem32[PAD_CONTROL_REGISTER] = mem32[PAD_CONTROL_REGISTER] | 0b0110000

        # GP22 為輸出，並設置輸出 1
        pin22 = Pin(22, Pin.OUT, value=0)
        time.sleep(1)
        pin22 = Pin(22, Pin.OUT, value=1)
        time.sleep(1)

        # 初始化I2C
        self.i2c0 = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
        self.i2c1 = I2C(1, scl=Pin(7), sda=Pin(6), freq=400000)
        self.display = sh1107.SH1107_I2C(128, 128, self.i2c1, None, 0x3c)
        self.oled.display = self.display

        # 清空顯示屏
        self.oled.clear()

        # 初始化 MPU6050
        self.mpu = MPU6050(self.i2c0)

        # =====================PICO WARE Init End====================================

    def init_game_elements(self):
        """
        初始化遊戲元素，如敵方球和三角形。
        """
        self.balls = []
        self.triangles = []
        for _ in range(self.num_balls):
            self.add_new_ball()
            self.add_new_triangle()

    def add_new_ball(self):
        # 隨機生成敵方球的位置（在屏幕邊緣）
        side = random.choice(['left', 'right', 'top', 'bottom'])
        if side == 'left':
            x = 0
            y = random.randint(0, 128)
        elif side == 'right':
            x = 128
            y = random.randint(0, 128)
        elif side == 'top':
            x = random.randint(0, 128)
            y = 0
        else:  # bottom
            x = random.randint(0, 128)
            y = 128

        # 計算朝向主球的方向向量
        dx = self.ball_x - x
        dy = self.ball_y - y
        distance = math.sqrt(dx**2 + dy**2)
        if distance == 0:
            distance = 1  # 防止除以零
        vx = dx / distance  # 單位向量
        vy = dy / distance

        # 設定敵方球的速度
        speed = 1
        vx *= speed
        vy *= speed

        self.balls.append({
            'x': x,
            'y': y,
            'vx': vx,
            'vy': vy,
            'radius': 3
        })

    def add_new_triangle(self):
        side = random.choice(['left', 'right', 'top', 'bottom'])
        if side == 'left':
            x = 0
            y = random.randint(0, 128)
        elif side == 'right':
            x = 128
            y = random.randint(0, 128)
        elif side == 'top':
            x = random.randint(0, 128)
            y = 0
        else:  # bottom
            x = random.randint(0, 128)
            y = 128

        # 計算朝向主球的方向向量
        dx = self.ball_x - x
        dy = self.ball_y - y
        distance = math.sqrt(dx**2 + dy**2)
        if distance == 0:
            distance = 1  # 防止除以零
        vx = dx / distance
        vy = dy / distance

        # 設定三角形的速度
        speed = 1
        vx *= speed
        vy *= speed

        self.triangles.append({
            'x': x,
            'y': y,
            'vx': vx,
            'vy': vy,
            'size': 6
        })

    def update_enemy_balls(self):
        for ball in self.balls[:]:
            ball['x'] += ball['vx']
            ball['y'] += ball['vy']

            # 檢查是否碰撞主球
            dx = ball['x'] - self.ball_x
            dy = ball['y'] - self.ball_y
            distance = math.sqrt(dx**2 + dy**2)
            if distance < self.ball_radius + ball['radius']:
                self.ball_radius += 1  # 吃掉球後主球變大
                self.balls.remove(ball)  # 移除被吃掉的球
                self.add_new_ball()  # 增加一顆新的球
            else:
                if (ball['x'] < -ball['radius'] or ball['x'] > 128 + ball['radius'] or
                    ball['y'] < -ball['radius'] or ball['y'] > 128 + ball['radius']):
                    self.balls.remove(ball)
                    self.add_new_ball()

    def update_triangles(self):
        for triangle in self.triangles[:]:
            triangle['x'] += triangle['vx']
            triangle['y'] += triangle['vy']

            # 檢查是否碰撞主球
            dx = triangle['x'] - self.ball_x
            dy = triangle['y'] - self.ball_y
            distance = math.sqrt(dx**2 + dy**2)
            if distance < self.ball_radius + triangle['size'] // 2:
                self.ball_radius -= 1  # 吃掉三角形後主球變小
                self.triangles.remove(triangle)  # 移除被吃掉的三角形
                self.add_new_triangle()  # 增加新的三角形
            else:
                if (triangle['x'] < -triangle['size'] or triangle['x'] > 128 + triangle['size'] or
                    triangle['y'] < -triangle['size'] or triangle['y'] > 128 + triangle['size']):
                    self.triangles.remove(triangle)
                    self.add_new_triangle()

    def draw_balls_and_triangles(self):
        self.oled.clear()

        # 繪製敵方球
        for ball in self.balls:
            self.oled.draw_circle(ball['x'], ball['y'], ball['radius'])

        # 繪製三角形
        for triangle in self.triangles:
            x0, y0 = triangle['x'], triangle['y'] - triangle['size'] // 2
            x1, y1 = triangle['x'] - triangle['size'] // 2, triangle['y'] + triangle['size'] // 2
            x2, y2 = triangle['x'] + triangle['size'] // 2, triangle['y'] + triangle['size'] // 2
            self.oled.draw_triangle(x0, y0, x1, y1, x2, y2)

        # 繪製主球
        self.oled.draw_circle(self.ball_x, self.ball_y, self.ball_radius)

        self.oled.show()

    def update_gyro_data(self):
        self.mpu.update_mahony()
        roll, pitch, _ = self.mpu.get_angles()

        # 使用 roll 和 pitch 控制球的移動速度和方向
        if abs(roll) > 5:
            self.ball_x += int(roll / 10)
        if abs(pitch) > 5:
            self.ball_y += int(pitch / 10)

        # 限制球在屏幕範圍內
        self.ball_x = max(self.ball_radius, min(128 - self.ball_radius, self.ball_x))
        self.ball_y = max(self.ball_radius, min(128 - self.ball_radius, self.ball_y))

    def init(self):
        """
        Initialize game settings and hardware.
        """
        print("Game initialized.")
        self.oled.display_text("Game Start")

        # 初始化硬件
        self.init_hardware()

        # 初始化遊戲元素
        self.init_game_elements()

    def run(self):
        """
        Main game loop integrating the original run method and the new game mechanics.
        """
        print("Game is running...")
        self.is_running = True
        try:
            # 初始化計時器
            self.gyro_update_timer = TimeToDo.TimeToDo(10)  # 每 10 毫秒更新主球
            self.enemy_ball_timer = TimeToDo.TimeToDo(50)  # 每 50 毫秒更新敵方球
            self.triangle_timer = TimeToDo.TimeToDo(50)  # 每 50 毫秒更新三角形
            self.draw_timer = TimeToDo.TimeToDo(50)  # 每 50 毫秒繪製畫面

            while self.is_running:
                # 更新按鈕狀態
                if self.check_button():
                    print("Game detected a long press, preparing to return to main menu.")
                    self.is_running = False
                    break

                # 執行定時任務
                self.gyro_update_timer.Do(self.update_gyro_data)
                self.enemy_ball_timer.Do(self.update_enemy_balls)
                self.triangle_timer.Do(self.update_triangles)
                self.draw_timer.Do(self.draw_balls_and_triangles)

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            # 遊戲結束後顯示完成信息
            if self.is_running:
                print("Game completed all steps, returning to main menu.")
                self.oled.display_text("Game Completed")
                time.sleep(1)

    def check_button(self):
        """
        Check if a long button press has occurred to exit the game.
        """
        if rp2.bootsel_button():  # 檢查 BOOTSEL 按鈕是否被按下
            press_start = time.time()
            while rp2.bootsel_button():  # 等待按鈕被釋放
                time.sleep(0.01)
            press_duration = time.time() - press_start
            if press_duration > 1.0:  # 長按閾值
                self.oled.display_text("Exiting Game...")
                return True
        return False

def main():
    # 初始化 I2C 和 OLED 顯示器
    i2c1 = I2C(1, scl=Pin(7), sda=Pin(6), freq=400000)
    display = sh1107.SH1107_I2C(128, 128, i2c1, None, 0x3c)
    oled = OLED(display)

    # 創建 Game 實例
    game = Game(oled)
    game.init()
    game.run()

# Example usage
if __name__ == "__main__":
    main()
