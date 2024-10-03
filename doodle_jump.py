import time
import rp2
import random
from machine import mem32, Pin, I2C
import libraries.sh1107 as sh1107
import libraries.TimeToDo as TimeToDo
from libraries.Mpu6050_mahony import MPU6050

# ==================== OLED 驅動程式 ====================

class OLED:
    def __init__(self, display):
        self.display = display

    def display_text(self, text, x=0, y=0, size=1):
        self.display.text(text[:16], x, y, 1)  # 顯示文字
        self.display.show()  # 更新顯示內容

    def clear(self):
        """清空顯示內容"""
        self.display.fill(0)
        self.display.show()

# ==================== Doodler 遊戲類 ====================

class Doodler:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = screen_width // 2
        self.y = screen_height - 20  # 初始位置
        self.w = 13  # 寬度
        self.h = 13  # 高度
        self.dy = 0
        self.dx = 0
        self.score = 0

    def show(self, oled):
        oled.display.fill_rect(self.x - self.w//2, self.y - self.h//2, self.w, self.h, 1)

    def lands(self, platform):
        if self.dy > 0:
            if (self.x + self.w // 2 >= platform.x - platform.w // 2 and
                self.x - self.w // 2 <= platform.x + platform.w // 2):
                if (self.y + self.h // 2 >= platform.y - platform.h // 2 and
                    self.y + self.h // 2 <= platform.y + platform.h // 2):
                    return True
        return False

    def jump(self):
        self.dy = -10  # 提高跳躍速度

    def move(self):
        # 重力
        self.dy += 1  # 可以調整為更小的值，如 0

        # 移動
        self.y += self.dy
        self.x += self.dx

        # 邊界處理
        if self.x > self.screen_width:
            self.x = 0
        elif self.x < 0:
            self.x = self.screen_width

# ==================== 平台類 ====================

class Platform:
    def __init__(self, x, y, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = x
        self.y = y
        self.w = 32  # 寬度
        self.h = 4   # 高度

    def show(self, oled):
        oled.display.fill_rect(self.x - self.w//2, self.y - self.h//2, self.w, self.h, 1)

# ==================== Game 類 ====================

class Game:
    SCREEN_WIDTH = 128
    SCREEN_HEIGHT = 128

    def __init__(self, oled, mpu):
        self.oled = oled
        self.mpu = mpu
        self.doodler = Doodler(self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        self.platforms = [
            Platform(self.SCREEN_WIDTH//2, self.SCREEN_HEIGHT - 10, self.SCREEN_WIDTH, self.SCREEN_HEIGHT),
            Platform(85, 26, self.SCREEN_WIDTH, self.SCREEN_HEIGHT),
            Platform(32, 51, self.SCREEN_WIDTH, self.SCREEN_HEIGHT),
            Platform(43, 77, self.SCREEN_WIDTH, self.SCREEN_HEIGHT),
            Platform(96, 102, self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        ]
        self.update_timer = TimeToDo.TimeToDo(50)  # 遊戲更新頻率 20 FPS
        self.OnTiltAnglesTimeTo = TimeToDo.TimeToDo(100)  # 傾斜讀取頻率 10 Hz
        self.game_over = False

    def init_game(self):
        """初始化遊戲變數"""
        self.doodler = Doodler(self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        self.platforms = [
            Platform(self.SCREEN_WIDTH//2, self.SCREEN_HEIGHT - 10, self.SCREEN_WIDTH, self.SCREEN_HEIGHT),
            Platform(85, 26, self.SCREEN_WIDTH, self.SCREEN_HEIGHT),
            Platform(32, 51, self.SCREEN_WIDTH, self.SCREEN_HEIGHT),
            Platform(43, 77, self.SCREEN_WIDTH, self.SCREEN_HEIGHT),
            Platform(96, 102, self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        ]
        self.game_over = False
        self.doodler.score = 0
        self.oled.clear()
        self.oled.display_text("Doodler Start", y=60)
        time.sleep(1)

    def run(self):
        """主遊戲迴圈"""
        self.init_game()
        while True:
            if self.update_timer.Do(self.update_game):
                pass  # 遊戲狀態已在 update_game 更新

            if self.OnTiltAnglesTimeTo.Do(self.update_control):
                pass  # 控制已在 update_control 更新

            if self.game_over:
                self.draw_game_over()
                time.sleep(2)
                self.init_game()

    def update_control(self):
        """根據 MPU6050 傾斜更新 Doodler 的水平移動"""
        self.mpu.update_mahony()
        roll, pitch, _ = self.mpu.get_angles()
        # 根據 roll 角度來控制左右移動
        if roll > 10:
            self.doodler.dx = 2  # 向右移動
        elif roll < -10:
            self.doodler.dx = -2  # 向左移動
        else:
            self.doodler.dx = 0  # 不移動

    def update_game(self):
        """更新遊戲狀態"""
        if not self.game_over:
            # 檢查是否落在平台上
            for platform in self.platforms:
                if self.doodler.lands(platform):
                    self.doodler.jump()
                    break

            # 移動 Doodler
            self.doodler.move()

            # 當 Doodler 移動到畫面上半部時，移動平台
            if self.doodler.y < self.SCREEN_HEIGHT // 2 and self.doodler.dy < 0:
                for platform in self.platforms:
                    platform.y -= self.doodler.dy
                    if platform.y > self.SCREEN_HEIGHT:
                        platform.x = random.randint(10, self.SCREEN_WIDTH - 10)
                        platform.y = random.randint(-20, 0)
                        self.doodler.score += 1

            # 檢查遊戲結束
            if self.doodler.y - self.doodler.h // 2 > self.SCREEN_HEIGHT:
                self.game_over = True

            # 繪製遊戲畫面
            self.draw_game()

    def draw_game(self):
        """在 OLED 上繪製遊戲畫面"""
        self.oled.display.fill(0)  # 清空顯示
        # 繪製平台
        for platform in self.platforms:
            platform.show(self.oled)
        # 繪製 Doodler
        self.doodler.show(self.oled)
        # 繪製分數
        score_text = f"Score: {self.doodler.score}"
        self.oled.display.text(score_text, 0, 0, 1)
        self.oled.display.show()

    def draw_game_over(self):
        """顯示遊戲結束訊息"""
        self.oled.display.fill(0)
        self.oled.display_text("GAME OVER", x=20, y=60)
        self.oled.display_text(f"Score: {self.doodler.score}", x=10, y=80)
        self.oled.display.show()

# ==================== 主遊戲邏輯 ====================

def init_oled_power():
    """初始化 OLED 電源"""
    PAD_CONTROL_REGISTER = 0x4001c024
    mem32[PAD_CONTROL_REGISTER] = mem32[PAD_CONTROL_REGISTER] | 0b0110000
    pin9 = Pin(9, Pin.OUT, value=0)
    pin8 = Pin(8, Pin.OUT, value=0)
    time.sleep(1)
    pin8 = Pin(8, Pin.OUT, value=1)

def init_mpu6050_power():
    """初始化 MPU6050 電源"""
    PAD_CONTROL_REGISTER = 0x4001c05c
    mem32[PAD_CONTROL_REGISTER] = mem32[PAD_CONTROL_REGISTER] | 0b0110000
    pin22 = Pin(22, Pin.OUT, value=0)
    time.sleep(1)
    pin22 = Pin(22, Pin.OUT, value=1)

def main():
    # 初始化 OLED 電源和 MPU6050 電源
    init_oled_power()
    init_mpu6050_power()

    # 初始化 I2C 和 OLED 顯示
    i2c1 = I2C(1, scl=Pin(7), sda=Pin(6), freq=400000)
    display = sh1107.SH1107_I2C(128, 128, i2c1, addr=0x3c)  # 移除 reset=None
    oled = OLED(display)

    # 初始化 MPU6050
    i2c0 = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
    mpu = MPU6050(i2c0)

    # 創建並運行遊戲實例
    game = Game(oled, mpu)
    game.run()

# Example usage
if __name__ == "__main__":
    main()
