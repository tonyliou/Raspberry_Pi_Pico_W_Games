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
        self.display.text(text[:16], int(x), int(y), 1)
        self.display.show()

    def clear(self):
        """清空顯示內容"""
        self.display.fill(0)
        self.display.show()

# ==================== Bird 類 ====================

class Bird:
    GRAVITY = 1
    JUMP_STRENGTH = -6

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.dy = 0
        self.radius = 5  # 鳥的半徑
        self.alive = True

    def update(self):
        self.dy += self.GRAVITY
        self.y += self.dy

    def jump(self):
        self.dy = self.JUMP_STRENGTH

    def show(self, oled):
        # 繪製一個圓形代表鳥
        oled.display.fill_circle(int(self.x), int(self.y), self.radius, 1)

    def get_bounds(self):
        return (self.x - self.radius, self.y - self.radius,
                self.x + self.radius, self.y + self.radius)

# ==================== Pipe 類 ====================

class Pipe:
    def __init__(self, x, gap_y, gap_height):
        self.x = x
        self.gap_y = gap_y
        self.gap_height = gap_height
        self.w = 20  # 管道寬度
        self.passed = False  # 是否已被鳥通過

    def update(self, speed):
        self.x -= speed

    def show(self, oled):
        # 上管道
        oled.display.fill_rect(int(self.x), 0, self.w, int(self.gap_y - self.gap_height // 2), 1)
        # 下管道
        oled.display.fill_rect(int(self.x), int(self.gap_y + self.gap_height // 2),
                               self.w, 128 - int(self.gap_y + self.gap_height // 2), 1)

    def off_screen(self):
        return self.x + self.w < 0

    def collides_with(self, bird):
        bird_left, bird_top, bird_right, bird_bottom = bird.get_bounds()

        # 檢查與上管道的碰撞
        if (bird_right > self.x and bird_left < self.x + self.w and
                bird_top < self.gap_y - self.gap_height // 2):
            return True

        # 檢查與下管道的碰撞
        if (bird_right > self.x and bird_left < self.x + self.w and
                bird_bottom > self.gap_y + self.gap_height // 2):
            return True

        return False

# ==================== Game 類 ====================

class Game:
    SCREEN_WIDTH = 128
    SCREEN_HEIGHT = 128
    PIPE_GAP_HEIGHT = 50
    PIPE_SPACING = 60
    PIPE_SPEED = 2

    def __init__(self, oled, mpu):
        self.oled = oled
        self.mpu = mpu
        self.bird = Bird(30, self.SCREEN_HEIGHT // 2)
        self.pipes = []
        self.score = 0
        self.best_score = 0
        self.game_over = False
        self.update_timer = TimeToDo.TimeToDo(63)  # 遊戲更新頻率約 63 FPS
        self.OnTiltAnglesTimeTo = TimeToDo.TimeToDo(10)  # 傾斜讀取頻率 10 Hz
        self.is_running = True
        self.prev_accel = (0, 0, 0)  # 用於存儲上一個加速度值
        self.shake_threshold = 0.5  # 設置搖晃檢測的閾值

    def init_game(self):
        """初始化遊戲變數"""
        self.bird = Bird(30, self.SCREEN_HEIGHT // 2)
        self.pipes = []
        self.score = 0
        self.game_over = False
        self.oled.clear()
        self.oled.display_text("Flappy Bird", y=60)
        time.sleep(1)

    def run(self):
        """主遊戲迴圈"""
        self.init_game()
        print("Game is running...")
        self.is_running = True
        try:
            while self.is_running:
                if self.update_timer.Do(self.update_game):
                    pass

                if self.OnTiltAnglesTimeTo.Do(self.update_control):
                    pass

                if self.check_button():
                    print("Detected a long press, preparing to exit.")
                    self.is_running = False
                    break

                if self.game_over:
                    self.draw_game_over()
                    time.sleep(2)
                    self.init_game()

        except Exception as e:
            print(f"An error occurred: {e}")
            self.is_running = False

    def update_control(self):
        """根據 MPU6050 加速度數據檢測搖晃"""
        # 讀取加速度數據
        accel = self.mpu.read_accel()
        ax, ay, az = accel

        # 計算加速度的變化量
        delta_ax = ax - self.prev_accel[0]
        delta_ay = ay - self.prev_accel[1]
        delta_az = az - self.prev_accel[2]

        # 計算加速度變化的絕對值總和
        delta_a_total = abs(delta_ax) + abs(delta_ay) + abs(delta_az)

        # 檢測是否超過搖晃閾值
        if delta_a_total > self.shake_threshold:
            self.bird.jump()

        # 更新上一個加速度值
        self.prev_accel = accel

    def update_game(self):
        """更新遊戲狀態"""
        if not self.game_over:
            self.bird.update()

            # 添加新的管道
            if len(self.pipes) == 0 or self.pipes[-1].x < self.SCREEN_WIDTH - self.PIPE_SPACING:
                gap_y = random.randint(20 + self.PIPE_GAP_HEIGHT // 2,
                                       self.SCREEN_HEIGHT - 20 - self.PIPE_GAP_HEIGHT // 2)
                new_pipe = Pipe(self.SCREEN_WIDTH, gap_y, self.PIPE_GAP_HEIGHT)
                self.pipes.append(new_pipe)

            # 更新管道
            for pipe in self.pipes:
                pipe.update(self.PIPE_SPEED)

                # 檢查碰撞
                if pipe.collides_with(self.bird):
                    self.game_over = True

                # 檢查是否通過管道
                if not pipe.passed and pipe.x + pipe.w < self.bird.x:
                    pipe.passed = True
                    self.score += 1
                    if self.score > self.best_score:
                        self.best_score = self.score

            # 移除離開螢幕的管道
            self.pipes = [pipe for pipe in self.pipes if not pipe.off_screen()]

            # 檢查是否撞到地面或天空
            if self.bird.y - self.bird.radius < 0 or self.bird.y + self.bird.radius > self.SCREEN_HEIGHT:
                self.game_over = True

            # 繪製遊戲畫面
            self.draw_game()

    def draw_game(self):
        """在 OLED 上繪製遊戲畫面"""
        self.oled.display.fill(0)
        # 繪製鳥
        self.bird.show(self.oled)
        # 繪製管道
        for pipe in self.pipes:
            pipe.show(self.oled)
        # 繪製分數
        score_text = f"Score: {self.score}"
        self.oled.display.text(score_text, int(0), int(0), 1)
        self.oled.display.show()

    def draw_game_over(self):
        """顯示遊戲結束訊息"""
        self.oled.display.fill(0)
        self.oled.display_text("GAME OVER", x=20, y=50)
        self.oled.display_text(f"Score: {self.score}", x=20, y=70)
        self.oled.display_text(f"Best: {self.best_score}", x=20, y=90)
        self.oled.display.show()

    def check_button(self):
        """
        檢查是否有長按按鈕以退出遊戲。
        """
        if rp2.bootsel_button():
            press_start = time.time()
            while rp2.bootsel_button():
                time.sleep(0.01)
            press_duration = time.time() - press_start
            if press_duration > 1.0:
                self.oled.display_text("Exiting Game...")
                return True
        return False

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
    display = sh1107.SH1107_I2C(128, 128, i2c1, addr=0x3c)
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
