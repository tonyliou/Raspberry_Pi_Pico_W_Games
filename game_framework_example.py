import time
import rp2

class Game:
    def __init__(self, oled):
        """
        Initialize the game with the OLED display.
        """
        self.oled = oled
        self.is_running = False

    def init(self):
        """
        Initialize game settings.
        """
        print("Game initialized.")
        self.oled.display_text("Game Start")

    def run(self):
        """
        Main game loop.
        """
        print("Game is running...")
        self.is_running = True
        try:
            for step in range(1, 6):
                if not self.is_running:
                    break
                print(f"Game Step {step}")
                self.oled.display_text(f"Step {step}")
                # Simulate game step duration
                time.sleep(0.5)
                # Check for button press after each step
                if self.check_button():
                    print("Game detected a long press, preparing to return to main menu.")
                    self.is_running = False
                    break
            if self.is_running:
                print("Game completed all steps, returning to main menu.")
                self.oled.display_text("Game Completed")
                time.sleep(1)
        except Exception as e:
            print(f"An error occurred: {e}")

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

# ==================== 顯示器控制類 ====================

class OLED:
    def __init__(self, display):
        self.display = display
    
    def display_text(self, text):
        self.display.fill(0)  # 清空顯示內容
        self.display.text(text[:16], 0, 0)  # 顯示一行最多16個字符
        self.display.show()  # 更新顯示內容

def main():
    from machine import I2C, Pin
    import libraries.sh1107 as sh1107

    # Initialize I2C and OLED display
    i2c1 = I2C(1, scl=Pin(7), sda=Pin(6), freq=400000)
    display = sh1107.SH1107_I2C(128, 128, i2c1, None, 0x3c)
    oled = OLED(display)

    # Create a Game instance
    game = Game(oled)
    game.init()
    game.run()

# Example usage
if __name__ == "__main__":
    main()
