# game1.py
import time
import rp2
import random
import math
from machine import I2C, Pin, mem32
import utime as time_module  # 避免與 time 模組衝突
import libraries.sh1107 as sh1107
from libraries.Mpu6050_mahony import MPU6050
import libraries.TimeToDo as TimeToDo

# ==================== 顯示器控制類 ====================
class OLED:
    def __init__(self, display):
        self.display = display
    
    def display_text(self, text):
        self.display.fill(0)  # 清空顯示內容
        self.display.text(text[:16], 0, 0)  # 顯示一行最多16個字符
        self.display.show()  # 更新顯示內容

    def fill_rect(self, x, y, w, h, color):
        self.display.fill_rect(x, y, w, h, color)

    def fill_circle(self, x, y, r, color):
        self.display.fill_circle(x, y, r, color)

    def fill(self, color):
        self.display.fill(color)

    def text_custom(self, text, x, y, color):
        self.display.text(text, x, y, color)
    
    def show(self):
        self.display.show()

# ==================== 遊戲類別 ====================
class Game:
    def __init__(self, oled):
        """
        Initialize the game with the OLED display.
        """
        self.oled = oled
        self.is_running = False

        # ==================== 硬件初始化 ====================
        # OLED 电源初始化
        PAD_CONTROL_REGISTER_OLED = 0x4001c024
        mem32[PAD_CONTROL_REGISTER_OLED] |= 0b0110000
        
        self.pin9 = Pin(9, Pin.OUT, value=0)
        self.pin8 = Pin(8, Pin.OUT, value=0)
        time_module.sleep(1)
        self.pin8.value(1)
        
        # MPU6050 电源初始化
        PAD_CONTROL_REGISTER_MPU = 0x4001c05c
        mem32[PAD_CONTROL_REGISTER_MPU] |= 0b0110000
        
        self.pin22 = Pin(22, Pin.OUT, value=0)
        time_module.sleep(1)
        self.pin22.value(1)
        time_module.sleep(1)
        
        # 初始化I2C
        self.i2c0 = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
        self.i2c1 = I2C(1, scl=Pin(7), sda=Pin(6), freq=400000)
        
        # 初始化显示屏
        self.display = sh1107.SH1107_I2C(128, 128, self.i2c1, None, 0x3c)
        self.display.fill(0)
        self.display.show()
        
        # 初始化MPU6050
        self.mpu = MPU6050(self.i2c0)
        
        # ==================== 遊戲參數設置 ====================
        self.SCREEN_WIDTH = 128
        self.SCREEN_HEIGHT = 128
        
        self.PLAYER_WIDTH = 11  # 玩家寬度
        self.PLAYER_HEIGHT = 9  # 玩家高度
        
        self.player_pos = [self.SCREEN_WIDTH // 2 - self.PLAYER_WIDTH // 2, self.SCREEN_HEIGHT - 20]  # 主角初始位置
        self.player_speed = 2  # 主角移動速度
        self.player_life = 3  # 主角生命值
        
        self.bullets = []  # 主角的子彈列表
        self.enemies = []  # 敵人列表
        self.enemy_bullets = []  # 敵人的彈幕列表
        self.items = []  # 道具列表
        
        self.score = 0  # 分數
        self.level = 1  # 關卡
        self.game_over = False
        
        self.MAX_ENEMIES = 10  # 屏幕上最多敵人數量
        self.MAX_BULLETS = 50  # 屏幕上最多子彈數量
        
        # 定時器
        self.update_timer = TimeToDo.TimeToDo(0)  # 遊戲邏輯更新，立即執行
        self.draw_timer = TimeToDo.TimeToDo(67)  # 畫面更新頻率，大約15FPS
        self.bullet_timer = TimeToDo.TimeToDo(300)  # 主角射擊頻率
        self.enemy_spawn_timer = TimeToDo.TimeToDo(1500)  # 敵人生成頻率
        self.enemy_bullet_timer = TimeToDo.TimeToDo(700)  # 敵人射擊頻率
        self.item_spawn_timer = TimeToDo.TimeToDo(7000)  # 道具生成頻率
        self.gyro_update_timer = TimeToDo.TimeToDo(10)  # 陀螺儀更新頻率
        
        # 玩家道具效果
        self.player_items = []
        
        # 分身列表
        self.clones = []
        
        # 定義最小分身距離
        self.MIN_CLONE_DISTANCE = self.PLAYER_WIDTH + 5  # 分身與玩家之間的最小距離
    
    def init_game(self):
        """
        初始化遊戲狀態
        """
        self.bullets = []
        self.enemies = []
        self.enemy_bullets = []
        self.items = []
        self.game_over = False
        self.player_pos = [self.SCREEN_WIDTH // 2 - self.PLAYER_WIDTH // 2, self.SCREEN_HEIGHT - 20]
        self.player_life = 3
        self.score = 0
        self.level = 1
        self.player_speed = 2
        self.player_items = []
        self.clones = []
        
        # 重新初始化定時器
        self.update_timer = TimeToDo.TimeToDo(0)       # 遊戲邏輯更新，立即執行
        self.draw_timer = TimeToDo.TimeToDo(17)        # 畫面更新頻率，大約60FPS
        self.bullet_timer = TimeToDo.TimeToDo(300)     # 主角射擊頻率
        self.enemy_spawn_timer = TimeToDo.TimeToDo(1500)  # 敵人生成頻率
        self.enemy_bullet_timer = TimeToDo.TimeToDo(700)  # 敵人射擊頻率
        self.item_spawn_timer = TimeToDo.TimeToDo(7000)   # 道具生成頻率
        self.gyro_update_timer = TimeToDo.TimeToDo(10)    # 陀螺儀更新頻率

    # ==================== 定義玩家和敵人的形狀 ====================
    
    # 主角形狀（飛機）
    def draw_player(self, x, y):
        airplane = [
            '00000100000',
            '00001110000',
            '00011111000',
            '00111111100',
            '01111111110',
            '11111111111',
            '00011111000',
            '00001110000',
            '00000100000',
        ]
        for row, line in enumerate(airplane):
            for col, pixel in enumerate(line):
                if pixel == '1':
                    self.oled.fill_rect(x + col, y + row, 1, 1, 1)
    
    # 不同類型的敵人形狀
    def draw_enemy(self, enemy_type, x, y):
        if enemy_type == 1:
            # 星形敵人
            star = [
                '00010000',
                '00111000',
                '11111110',
                '00111000',
                '00010000',
                '00000000',
                '00000000',
                '00000000',
            ]
            shape = star
        elif enemy_type == 2:
            # 方塊敵人
            square = [
                '11111111',
                '10000001',
                '10011001',
                '10011001',
                '10000001',
                '11111111',
                '00000000',
                '00000000',
            ]
            shape = square
        elif enemy_type == 3:
            # 圓形敵人
            circle = [
                '00111100',
                '01111110',
                '11111111',
                '11111111',
                '11111111',
                '01111110',
                '00111100',
                '00000000',
            ]
            shape = circle
        else:
            shape = []
        for row, line in enumerate(shape):
            for col, pixel in enumerate(line):
                if pixel == '1':
                    self.oled.fill_rect(x + col, y + row, 1, 1, 1)
    
    # 道具形狀
    def draw_item(self, item_type, x, y):
        if item_type == 'speed':
            # 加速道具（箭頭）
            arrow = [
                '00010000',
                '00111000',
                '01111100',
                '11111110',
                '00111000',
                '00111000',
                '00111000',
                '00000000',
            ]
            shape = arrow
        elif item_type == 'shield':
            # 無敵道具（盾牌）
            shield = [
                '01111110',
                '11111111',
                '11111111',
                '11111111',
                '11111111',
                '01111110',
                '00111100',
                '00011000',
            ]
            shape = shield
        elif item_type == 'triple_shot':
            # 三重射擊道具（火焰）
            fire = [
                '00010000',
                '00111000',
                '01111100',
                '11111110',
                '01111100',
                '00111000',
                '00010000',
                '00000000',
            ]
            shape = fire
        elif item_type == 'clone':
            # 分身道具（雙子）
            twin = [
                '00100100',
                '01111110',
                '01111110',
                '01111110',
                '00111100',
                '00011000',
                '00000000',
                '00000000',
            ]
            shape = twin
        else:
            shape = []
        for row, line in enumerate(shape):
            for col, pixel in enumerate(line):
                if pixel == '1':
                    self.oled.fill_rect(x + col, y + row, 1, 1, 1)
    
    # ==================== 遊戲函數定義 ====================
    
    # 更新陀螺儀數據，控制主角移動
    def update_gyro_data(self):
        self.mpu.update_mahony()
        roll, pitch, _ = self.mpu.get_angles()
        dx = 0
        dy = 0
    
        if abs(roll) > 5:
            dx = int(math.copysign(1, roll)) * self.player_speed  # 左右移動
        if abs(pitch) > 5:
            dy = int(math.copysign(1, pitch)) * self.player_speed  # 上下移動
    
        # 更新主角位置，並限制在屏幕內
        self.player_pos[0] = max(0, min(self.SCREEN_WIDTH - self.PLAYER_WIDTH, self.player_pos[0] + dx))
        self.player_pos[1] = max(0, min(self.SCREEN_HEIGHT - self.PLAYER_HEIGHT, self.player_pos[1] + dy))
    
        # 更新分身位置
        for clone in self.clones:
            # 計算期望的x位置
            desired_x = clone['x'] + dx
            # 保持分身在屏幕內
            desired_x = max(0, min(self.SCREEN_WIDTH - self.PLAYER_WIDTH, desired_x))
            # 判斷分身是否碰到邊界
            if desired_x <= 0 or desired_x >= self.SCREEN_WIDTH - self.PLAYER_WIDTH:
                # 分身碰到邊界，向玩家方向移動，但保持最小距離
                if clone['x'] < self.player_pos[0]:
                    # 分身在左側
                    clone['x'] = max(self.player_pos[0] - self.MIN_CLONE_DISTANCE, desired_x)
                else:
                    # 分身在右側
                    clone['x'] = min(self.player_pos[0] + self.MIN_CLONE_DISTANCE, desired_x)
            else:
                clone['x'] = desired_x
                # 確保分身與玩家保持最小距離
                if clone['x'] < self.player_pos[0]:
                    clone['x'] = min(clone['x'], self.player_pos[0] - self.MIN_CLONE_DISTANCE)
                else:
                    clone['x'] = max(clone['x'], self.player_pos[0] + self.MIN_CLONE_DISTANCE)
            # 更新分身的y位置
            clone['y'] = self.player_pos[1]
    
    # 主角射擊
    def player_shoot(self):
        if len(self.bullets) < self.MAX_BULLETS:
            if 'triple_shot' in self.player_items:
                # 三方向射擊
                self.bullets.append({'x': self.player_pos[0] + self.PLAYER_WIDTH // 2, 'y': self.player_pos[1], 'dx': -1, 'dy': -5})
                self.bullets.append({'x': self.player_pos[0] + self.PLAYER_WIDTH // 2, 'y': self.player_pos[1], 'dx': 0, 'dy': -5})
                self.bullets.append({'x': self.player_pos[0] + self.PLAYER_WIDTH // 2, 'y': self.player_pos[1], 'dx': 1, 'dy': -5})
                # 分身射擊
                for clone in self.clones:
                    self.bullets.append({'x': clone['x'] + self.PLAYER_WIDTH // 2, 'y': clone['y'], 'dx': -1, 'dy': -5})
                    self.bullets.append({'x': clone['x'] + self.PLAYER_WIDTH // 2, 'y': clone['y'], 'dx': 0, 'dy': -5})
                    self.bullets.append({'x': clone['x'] + self.PLAYER_WIDTH // 2, 'y': clone['y'], 'dx': 1, 'dy': -5})
            else:
                # 普通射擊
                self.bullets.append({'x': self.player_pos[0] + self.PLAYER_WIDTH // 2, 'y': self.player_pos[1], 'dx': 0, 'dy': -5})
                # 分身射擊
                for clone in self.clones:
                    self.bullets.append({'x': clone['x'] + self.PLAYER_WIDTH // 2, 'y': clone['y'], 'dx': 0, 'dy': -5})
    
    # 更新主角子彈位置
    def update_bullets(self):
        for bullet in self.bullets[:]:
            bullet['x'] += bullet.get('dx', 0)
            bullet['y'] += bullet.get('dy', -5)
            if bullet['y'] < 0 or bullet['x'] < 0 or bullet['x'] > self.SCREEN_WIDTH:
                self.bullets.remove(bullet)
    
    # 生成敵人
    def spawn_enemy(self):
        if len(self.enemies) < self.MAX_ENEMIES:
            x = random.randint(0, self.SCREEN_WIDTH - 8)
            enemy_type = random.randint(1, min(3, self.level + 1))  # 根據關卡增加敵人類型，最多3種
            self.enemies.append({'x': x, 'y': 0, 'speed': self.level, 'type': enemy_type})
    
    # 更新敵人位置
    def update_enemies(self):
        for enemy in self.enemies[:]:
            enemy['y'] += enemy['speed']
            if enemy['y'] > self.SCREEN_HEIGHT:
                self.enemies.remove(enemy)
                # 允許敵人逃脫，不減少生命值
    
    # 敵人射擊
    def enemy_shoot(self):
        for enemy in self.enemies:
            if enemy['type'] == 1:
                # 星形敵人，直線射擊
                if len(self.enemy_bullets) < self.MAX_BULLETS:
                    self.enemy_bullets.append({'x': enemy['x'] + 3, 'y': enemy['y'] + 8, 'speed': 2 + self.level, 'dx': 0, 'dy': 2 + self.level})
            elif enemy['type'] == 2:
                # 方塊敵人，左右斜向射擊
                if len(self.enemy_bullets) + 2 <= self.MAX_BULLETS:
                    self.enemy_bullets.append({'x': enemy['x'] + 3, 'y': enemy['y'] + 8, 'speed': 2 + self.level, 'dx': -1, 'dy': 2 + self.level})
                    self.enemy_bullets.append({'x': enemy['x'] + 3, 'y': enemy['y'] + 8, 'speed': 2 + self.level, 'dx': 1, 'dy': 2 + self.level})
            elif enemy['type'] == 3:
                # 圓形敵人，環狀射擊，減少子彈數量
                angles = [0, 90, 180, 270]  # 四個方向
                for angle in angles:
                    if len(self.enemy_bullets) < self.MAX_BULLETS:
                        rad = math.radians(angle)
                        dx = math.cos(rad) * (1 + self.level)
                        dy = math.sin(rad) * (1 + self.level)
                        self.enemy_bullets.append({'x': enemy['x'] + 3, 'y': enemy['y'] + 8, 'dx': dx, 'dy': dy})
    
    # 更新敵人彈幕
    def update_enemy_bullets(self):
        for bullet in self.enemy_bullets[:]:
            if 'dy' in bullet and 'dx' in bullet:
                # 圓形敵人的子彈，斜向移動
                bullet['x'] += bullet['dx']
                bullet['y'] += bullet['dy']
            else:
                # 其他敵人的子彈，直線或斜向移動
                bullet['x'] += bullet.get('dx', 0)
                bullet['y'] += bullet.get('dy', 0)
            if (bullet['y'] > self.SCREEN_HEIGHT or bullet['y'] < 0 or
                bullet['x'] < 0 or bullet['x'] > self.SCREEN_WIDTH):
                self.enemy_bullets.remove(bullet)
    
    # 生成道具
    def spawn_item(self):
        x = random.randint(0, self.SCREEN_WIDTH - 8)
        item_type = random.choice(['speed', 'shield', 'triple_shot', 'clone'])  # 添加 'triple_shot' 和 'clone'
        self.items.append({'x': x, 'y': 0, 'speed': 1, 'type': item_type})
    
    # 更新道具位置
    def update_items(self):
        for item in self.items[:]:
            item['y'] += item['speed']
            if item['y'] > self.SCREEN_HEIGHT:
                self.items.remove(item)
    
    # 碰撞檢測
    def check_collisions(self):
        # 主角子彈與敵人
        for bullet in self.bullets[:]:
            bullet_x = int(bullet['x'])
            bullet_y = int(bullet['y'])
            for enemy in self.enemies[:]:
                enemy_x = int(enemy['x'])
                enemy_y = int(enemy['y'])
                if (enemy_x < bullet_x < enemy_x + 8 and
                    enemy_y < bullet_y < enemy_y + 8):
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)
                    if enemy in self.enemies:
                        self.enemies.remove(enemy)
                    self.score += 10  # 擊敗敵人獲得分數
                    break
    
        # 敵人彈幕與分身和主角
        player_hitbox = {'x': self.player_pos[0], 'y': self.player_pos[1], 'w': self.PLAYER_WIDTH, 'h': self.PLAYER_HEIGHT}
        clone_hitboxes = [{'x': clone['x'], 'y': clone['y'], 'w': self.PLAYER_WIDTH, 'h': self.PLAYER_HEIGHT, 'clone': clone} for clone in self.clones]
    
        for bullet in self.enemy_bullets[:]:
            bullet_x = int(bullet['x'])
            bullet_y = int(bullet['y'])
            # 檢查是否擊中分身
            clone_hit = False
            for ch in clone_hitboxes:
                if (ch['x'] < bullet_x < ch['x'] + ch['w'] and
                    ch['y'] < bullet_y < ch['y'] + ch['h']):
                    if bullet in self.enemy_bullets:
                        self.enemy_bullets.remove(bullet)
                    if ch['clone'] in self.clones:
                        self.clones.remove(ch['clone'])
                    clone_hit = True
                    break
            if clone_hit:
                continue  # 繼續檢查下一顆子彈
    
            # 檢查是否擊中主角
            if (player_hitbox['x'] < bullet_x < player_hitbox['x'] + player_hitbox['w'] and
                player_hitbox['y'] < bullet_y < player_hitbox['y'] + player_hitbox['h']):
                if bullet in self.enemy_bullets:
                    self.enemy_bullets.remove(bullet)
                if 'shield' in self.player_items:
                    self.player_items.remove('shield')  # 消耗盾牌
                else:
                    self.player_life -= 1
                    if self.player_life <= 0:
                        self.game_over = True
                continue  # 繼續檢查下一顆子彈
    
        # 主角與道具
        for item in self.items[:]:
            item_x = int(item['x'])
            item_y = int(item['y'])
            player_x = int(self.player_pos[0])
            player_y = int(self.player_pos[1])
            if (player_x < item_x + 8 and item_x < player_x + self.PLAYER_WIDTH and
                player_y < item_y + 8 and item_y < player_y + self.PLAYER_HEIGHT):
                if item in self.items:
                    self.items.remove(item)
                if item['type'] == 'speed':
                    self.player_speed = 4  # 加速
                    TimeToDo.TimeToDo(5000).Do(self.reset_speed)  # 5秒後恢復速度
                elif item['type'] == 'shield':
                    self.player_items.append('shield')  # 獲得盾牌
                elif item['type'] == 'triple_shot':
                    self.player_items.append('triple_shot')  # 獲得三重射擊
                    TimeToDo.TimeToDo(10000).Do(self.remove_triple_shot)  # 10秒後失效
                elif item['type'] == 'clone':
                    self.add_clone()
                    TimeToDo.TimeToDo(10000).Do(self.remove_clone)  # 10秒後移除分身
    
    # 恢復玩家速度
    def reset_speed(self, *args):
        self.player_speed = 2
    
    # 移除三重射擊效果
    def remove_triple_shot(self, *args):
        if 'triple_shot' in self.player_items:
            self.player_items.remove('triple_shot')
    
    # 添加分身
    def add_clone(self):
        # 在玩家左右各添加一個分身
        self.clones.append({'x': self.player_pos[0] - self.MIN_CLONE_DISTANCE, 'y': self.player_pos[1]})
        self.clones.append({'x': self.player_pos[0] + self.MIN_CLONE_DISTANCE, 'y': self.player_pos[1]})
    
    # 移除分身
    def remove_clone(self, *args):
        self.clones.clear()
    
    # 繪製遊戲畫面
    def draw_game(self):
        self.oled.fill(0)
        # 繪製主角（飛機形狀）
        self.draw_player(int(self.player_pos[0]), int(self.player_pos[1]))
        # 繪製分身
        for clone in self.clones:
            self.draw_player(int(clone['x']), int(clone['y']))
        # 繪製主角子彈
        for bullet in self.bullets:
            self.oled.fill_rect(int(bullet['x']), int(bullet['y']), 2, 4, 1)
        # 繪製敵人
        for enemy in self.enemies:
            self.draw_enemy(enemy['type'], int(enemy['x']), int(enemy['y']))
        # 繪製敵人彈幕
        for bullet in self.enemy_bullets:
            self.oled.fill_circle(int(bullet['x']), int(bullet['y']), 2, 1)
        # 繪製道具
        for item in self.items:
            self.draw_item(item['type'], int(item['x']), int(item['y']))
        # 顯示分數和生命值
        self.oled.text_custom(f"Score: {self.score}", 0, 0, 1)
        self.oled.text_custom(f"Life: {self.player_life}", 0, 10, 1)
        self.oled.text_custom(f"Level: {self.level}", 0, 20, 1)
        self.oled.show()
    
    # 遊戲結束畫面
    def draw_game_over(self):
        self.oled.fill(0)  # 清空螢幕
    
        # 定義每個字元的寬度（根據使用的字體調整）
        CHAR_WIDTH = 8
    
        # 顯示 "GAME OVER" 並居中
        game_over_text = "GAME OVER"
        game_over_width = len(game_over_text) * CHAR_WIDTH
        game_over_x = (128 - game_over_width) // 2
        self.oled.text_custom(game_over_text, game_over_x, 40, 1)
    
        # 顯示 "Final Score:" 並居中
        final_score_text = "Final Score:"
        final_score_width = len(final_score_text) * CHAR_WIDTH
        final_score_x = (128 - final_score_width) // 2
        self.oled.text_custom(final_score_text, final_score_x, 60, 1)
    
        # 顯示分數數值並居中
        score_text = str(self.score)
        score_width = len(score_text) * CHAR_WIDTH
        score_x = (128 - score_width) // 2
        self.oled.text_custom(score_text, score_x, 80, 1)
    
        self.oled.show()  # 更新顯示

    # 更新關卡
    def level_control(self):
        # 每達到一定分數提升一級
        if self.score // 100 + 1 > self.level:
            self.level += 1
            # 增加敵人生成和射擊頻率
            self.enemy_spawn_timer.interval = max(800, 1500 - (self.level - 1) * 100)
            self.enemy_bullet_timer.interval = max(500, 700 - (self.level - 1) * 50)
    
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
    
    # 更新遊戲邏輯
    def update_game(self):
        if not self.game_over:
            self.update_bullets()
            self.update_enemies()
            self.update_enemy_bullets()
            self.update_items()
            self.check_collisions()
            self.level_control()
    
    # 主遊戲循環
    def run(self):
        """
        主遊戲循環
        """
        print("Game is running...")
        self.is_running = True
        try:
            while self.is_running:
                # 執行定時器任務
                self.gyro_update_timer.Do(self.update_gyro_data)
                self.update_timer.Do(self.update_game)
                self.bullet_timer.Do(self.player_shoot)
                self.enemy_spawn_timer.Do(self.spawn_enemy)
                self.enemy_bullet_timer.Do(self.enemy_shoot)
                self.item_spawn_timer.Do(self.spawn_item)
                self.draw_timer.Do(self.draw_game)
                
                if self.check_button():
                    print("Detected a long press, preparing to return to main menu.")
                    self.is_running = False
                    break
    
                if self.game_over:
                    self.draw_game_over()
                    time_module.sleep(2)
                    self.init_game()
        except Exception as e:
            print(f"An error occurred: {e}")
            self.oled.display_text("Error Occurred")
    
    def init(self):
        """
        初始化遊戲設置
        """
        print("Game initialized.")
        self.oled.display_text("Game Start")
        self.init_game()

# ==================== 主函數 ====================
def main():
    # Initialize I2C and OLED display
    i2c1 = I2C(1, scl=Pin(7), sda=Pin(6), freq=400000)
    display = sh1107.SH1107_I2C(128, 128, i2c1, None, 0x3c)
    oled = OLED(display)

    # Create a Game instance
    game = Game(oled)
    game.init()
    game.run()

# 程式入口
if __name__ == "__main__":
    main()
