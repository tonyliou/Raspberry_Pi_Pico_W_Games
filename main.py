import time
from machine import I2C, Pin, mem32
import libraries.sh1107 as sh1107
from libraries.Mpu6050_mahony import MPU6050
import random
import rp2
import uos

# ==================== 硬體初始化 ====================

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

def init_i2c_display():
    """初始化I2C和顯示"""
    i2c0 = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
    i2c1 = I2C(1, scl=Pin(7), sda=Pin(6), freq=400000)
    display = sh1107.SH1107_I2C(128, 128, i2c1, None, 0x3c)
    display.fill(0)
    display.show()
    return display, i2c0

# ==================== 顯示器控制類 ====================

class OLED:
    def __init__(self, display):
        self.display = display
    
    def display_text(self, text):
        self.display.fill(0)  # 清空顯示內容
        self.display.text(text[:16], 0, 0)  # 顯示一行最多16個字符
        self.display.show()  # 更新顯示內容

# ==================== 菜單選擇邏輯 ====================

class MainMenu:
    DEBOUNCE_DELAY = 0.05  # 50 milliseconds

    def __init__(self, oled):
        self.oled = oled
        self.menu_items = self.scan_py_files()
        if not self.menu_items:
            self.menu_items = ['game1', 'game2']  # Default menu items
        self.current_index = 0

    def scan_py_files(self):
        # 使用 uos.listdir("/") 來列出根目錄的所有檔案
        py_files = []
        try:
            for file in uos.listdir("/"):
                # 使用 uos.stat() 確認是檔案且以 .py 結尾
                if file.endswith(".py"):
                    file_path = "/" + file
                    file_info = uos.stat(file_path)
                    # 檢查是否為檔案 (uos.stat() 的第一個值代表檔案類型)
                    if file_info[0] & 0x8000:  # 0x8000 表示普通檔案
                        py_files.append(file)
        except Exception as e:
            print("Error scanning files:", e)
        return py_files

    def display_current_selection(self):
        item = self.menu_items[self.current_index]
        self.oled.display_text(item)

    def next_item(self):
        self.current_index = (self.current_index + 1) % len(self.menu_items)
        self.display_current_selection()

    def get_selected_game(self):
        item = self.menu_items[self.current_index]
        return item

# ==================== 按鈕偵測邏輯 ====================

class ButtonHandler:
    def __init__(self):
        self.last_press_time = 0
        self.press_threshold = 1.0  # 1 second threshold for long press
        self.debounce_time = 0.05  # 50 milliseconds debounce

    def get_press_duration(self):
        """檢查按鈕狀態並返回按下的持續時間"""
        if rp2.bootsel_button():  # 按鈕被按下
            current_time = time.time()
            if current_time - self.last_press_time > self.debounce_time:
                press_start = current_time
                while rp2.bootsel_button():  # 持續按住按鈕
                    time.sleep(0.01)
                press_duration = time.time() - press_start
                self.last_press_time = time.time()  # 更新最後一次按下的時間
                return press_duration
        return None

# ==================== 動態載入方法 ====================
def dynamic_import_and_run(module_name, class_name, method_name):
    # 動態載入模組
    module = __import__(module_name)
    
    # 取得類別
    class_ = getattr(module, class_name)
    
    # 創建類別實例
    instance = class_()
    
    # 取得方法
    method = getattr(instance, method_name)
    
    # 執行方法
    method()

# ==================== 主邏輯 ====================

def main():
    # 初始化硬體
    init_oled_power()
    init_mpu6050_power()
    display, i2c0 = init_i2c_display()

    # 初始化 MPU6050 傳感器
    mpu = MPU6050(i2c0)

    # 初始化 OLED 顯示
    oled = OLED(display)

    # 初始化菜單與按鈕處理
    menu = MainMenu(oled)
    button_handler = ButtonHandler()

    menu.display_current_selection()

    state = 'menu'
    current_game = None

    while True:
        press_duration = button_handler.get_press_duration()

        if press_duration is None:
            time.sleep(0.1)  # 若無按鍵事件，稍微延遲，避免浪費資源
            continue

        # 按鍵消抖處理
        time.sleep(MainMenu.DEBOUNCE_DELAY)

        if press_duration >= button_handler.press_threshold:
            press_type = 'long'
        else:
            press_type = 'short'

        if state == 'menu':
            if press_type == 'short':
                print("Main Menu: Short press detected, moving to next menu item.")
                menu.next_item()
            elif press_type == 'long':
                print("Main Menu: Long press detected, selecting current menu item and running the game.")
                selected_game_name = menu.get_selected_game()
                
                # 使用 replace 方法將 ".py" 替換成空字串
                selected_game_name = selected_game_name.replace(".py", "")
                try:
                    print(f"Running {selected_game_name}")
                    oled.display_text(f"Running {selected_game_name}")
                    
                    # 動態導入模組
                    module = __import__(selected_game_name)
                    
                    # 呼叫模組的 main 函數
                    if hasattr(module, 'main'):
                        module.main()
                    else:
                        raise AttributeError(f"The module '{selected_game_name}' does not have a 'main' function.")

                    state = 'game'
                except Exception as e:
                    oled.display_text(f"Error: {str(e)}")
                    print(f"Error: {e}")
                    print("Returning to main menu in 5 seconds.")
                    time.sleep(5)
                    menu.display_current_selection()
                    state = 'menu'
        elif state == 'game':
            state = 'menu'
            print("Returning to main menu.")
            menu.display_current_selection()

    print("Program terminated.")

if __name__ == "__main__":
    main()

