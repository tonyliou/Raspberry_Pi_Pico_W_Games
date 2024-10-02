import time
import rp2
import random
from libraries.Mpu6050_mahony import MPU6050
from machine import mem32, Pin, I2C
import libraries.sh1107 as sh1107
import libraries.TimeToDo as TimeToDo

# ==================== OLED 驅動程式 ====================

class OLED:
    def __init__(self, display):
        self.display = display
    
    def display_text(self, text):
        self.display.fill(0)  # 清空顯示內容
        self.display.text(text[:16], 0, 0)  # 顯示一行最多16個字符
        self.display.show()  # 更新顯示內容
    
    def clear(self):
        """清空顯示內容"""
        self.display.fill(0)
        self.display.show()

# ==================== Game ====================

class Game:
    GRID_SIZE = 8
    SCREEN_WIDTH = 128
    SCREEN_HEIGHT = 128

    def __init__(self, oled, mpu):
        self.oled = oled
        self.mpu = mpu
        self.snake = []
        self.food = (0, 0)
        self.direction = (0, -1)  # 當前方向
        self.next_direction = self.direction  # 下一個方向
        self.game_over = False
        self.is_running = False
        self.update_timer = TimeToDo.TimeToDo(200)
        self.OnTiltAnglesTimeTo = TimeToDo.TimeToDo(10)

    def init(self):
        """
        Initialize game settings.
        """
        print("Game initialized.")
        self.oled.display_text("Game Start")
        self.init_game()

    def init_game(self):
        """Initialize game variables."""
        self.snake = [(4, 4), (4, 5), (4, 6)]  # Initial snake body
        self.direction = (0, -1)  # Initial direction
        self.next_direction = self.direction
        self.game_over = False
        self.init_food()

    def run(self):
        """
        Main game loop.
        """
        print("Game is running...")
        self.is_running = True
        try:
            while self.is_running:
                self.OnTiltAnglesTimeTo.Do(self.update_gyro_data)
                self.update_timer.Do(self.update_game)
                
                if self.check_button():
                    print("Detected a long press, preparing to return to main menu.")
                    self.is_running = False
                    break

                if self.game_over:
                    self.draw_game_over()
                    time.sleep(2)
                    self.init_game()
                else:
                    self.draw_game()
        except Exception as e:
            print(f"An error occurred: {e}")
            self.is_running = False

    def update_gyro_data(self):
        """Update gyro data to change direction."""
        self.mpu.update_mahony()
        roll, pitch, _ = self.mpu.get_angles()
        new_direction = self.next_direction  # 使用緩衝的方向

        if abs(roll) > abs(pitch):
            if roll > 10:
                new_direction = (1, 0)  # Right
            elif roll < -10:
                new_direction = (-1, 0)  # Left
        else:
            if pitch > 10:
                new_direction = (0, 1)  # Up
            elif pitch < -10:
                new_direction = (0, -1)  # Down

        # 防止蛇反向移動
        opposite_direction = (-self.direction[0], -self.direction[1])
        print(f"New direction request: {new_direction}, Opposite direction: {opposite_direction}")

        if new_direction != opposite_direction and new_direction != self.next_direction:
            print(f"Changing direction from {self.next_direction} to {new_direction}")
            self.next_direction = new_direction
        else:
            print(f"Direction unchanged: {self.next_direction}")

    def update_game(self):
        """Update game state, move snake, check for collisions and food."""
        # 在遊戲更新前應用下一個方向
        self.direction = self.next_direction
        print(f"Applying direction: {self.direction}")

        new_head = (self.snake[0][0] + self.direction[0], self.snake[0][1] + self.direction[1])

        # Debugging: 打印新的頭部位置和方向
        print(f"New head position: {new_head}, Direction: {self.direction}")

        if (new_head[0] < 0 or new_head[0] >= self.SCREEN_WIDTH // self.GRID_SIZE or
            new_head[1] < 0 or new_head[1] >= self.SCREEN_HEIGHT // self.GRID_SIZE or
            new_head in self.snake):
            print("Collision detected! Game Over.")
            self.game_over = True
            return

        self.snake.insert(0, new_head)

        if new_head == self.food:
            print("Food eaten!")
            self.init_food()
        else:
            self.snake.pop()

    def init_food(self):
        """Generate new food position."""
        while True:
            self.food = (random.randint(0, (self.SCREEN_WIDTH // self.GRID_SIZE) - 1),
                         random.randint(0, (self.SCREEN_HEIGHT // self.GRID_SIZE) - 1))
            if self.food not in self.snake:
                print(f"New food position: {self.food}")
                break

    def draw_game(self):
        """Draw the game on the OLED display."""
        self.oled.display.fill(0)
        for segment in self.snake:
            self.oled.display.fill_rect(segment[0] * self.GRID_SIZE, segment[1] * self.GRID_SIZE, self.GRID_SIZE, self.GRID_SIZE, 1)
        self.oled.display.fill_rect(self.food[0] * self.GRID_SIZE, self.food[1] * self.GRID_SIZE, self.GRID_SIZE, self.GRID_SIZE, 1)
        self.oled.display.show()

    def draw_game_over(self):
        """Display 'Game Over' on the OLED."""
        self.oled.display.fill(0)
        self.oled.display.text("GAME OVER", 28, 60, 1)
        self.oled.display.show()

    def check_button(self):
        """
        Check if a long button press has occurred to exit the game.
        """
        if rp2.bootsel_button():  # Check if the BOOTSEL button is pressed
            press_start = time.time()
            while rp2.bootsel_button():  # Wait for the button to be released
                time.sleep(0.01)
            press_duration = time.time() - press_start
            if press_duration > 1.0:  # Long press threshold
                self.oled.display_text("Exiting Game...")
                return True
        return False

# ==================== 主遊戲邏輯 ====================

def init_oled_power():
    """初始化OLED電源"""
    PAD_CONTROL_REGISTER = 0x4001c024
    mem32[PAD_CONTROL_REGISTER] = mem32[PAD_CONTROL_REGISTER] | 0b0110000
    pin9 = Pin(9, Pin.OUT, value=0)
    pin8 = Pin(8, Pin.OUT, value=0)
    time.sleep(1)
    pin8 = Pin(8, Pin.OUT, value=1)

def init_mpu6050_power():
    """初始化MPU6050電源"""
    PAD_CONTROL_REGISTER = 0x4001c05c
    mem32[PAD_CONTROL_REGISTER] = mem32[PAD_CONTROL_REGISTER] | 0b0110000
    pin22 = Pin(22, Pin.OUT, value=0)
    time.sleep(1)
    pin22 = Pin(22, Pin.OUT, value=1)

def main():
    # Initialize OLED power and MPU6050 power
    init_oled_power()
    init_mpu6050_power()

    # Initialize I2C and OLED display
    i2c1 = I2C(1, scl=Pin(7), sda=Pin(6), freq=400000)
    display = sh1107.SH1107_I2C(128, 128, i2c1, None, 0x3c)
    oled = OLED(display)

    # Initialize MPU6050
    i2c0 = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
    mpu = MPU6050(i2c0)

    # Create a Game instance
    game = Game(oled, mpu)
    game.init()
    game.run()

# Example usage
if __name__ == "__main__":
    main()
