'''
Mpu6050_mahony.py
這個 MPU6050 類別是為了在 MicroPython 環境中使用 MPU6050 陀螺儀和加速度計感測器設計的。
它可以進行平躺Roll Pitch ，站立時傾斜角度的計算，並透過Mahony濾波算法來實現更準確的姿態估計。
使用範例
from machine import Pin, I2C, RTC,Timer
from Mpu6050_mahony import MPU6050
from machine import mem32

# mpu6050 的電源
PAD_CONTROL_REGISTER = 0x4001c05c #讓PIN電流提升
mem32[PAD_CONTROL_REGISTER] = mem32[PAD_CONTROL_REGISTER] | 0b0110000
# GP22 為mpu6050的電源輸出，務必設置輸出 1 才能啟動mpu6050
pin22 = Pin(22, Pin.OUT, value=0)
time.sleep(1)
pin22 = Pin(22, Pin.OUT, value=1)
time.sleep(1)
# 初始化I2C
i2c0 = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
# 初始化MPU6050
mpu = MPU6050(i2c0)

務必每秒一百次計算才能取得穩定角度建議搭配TimeToDoFile
計算姿態與主程式使用不同TimeToDo以提升運算頻率
mpu.update_mahony()
mpu.calculate_tilt_angles()

主要方法
__init__(self, i2c, addr=0x68)
    初始化 MPU6050 類別。
    參數 i2c 是必須的，它是一個已配置的 I2C 對象。
    參數 addr 是設備的 I2C 地址，默認為 0x68。
calibrate(self, samples=100)
    校準 MPU6050，減少讀數誤差。這個方法會收集多個樣本來計算平均偏差。
update_mahony(self)
    計算mpu6050平躺的。更新姿態估計，使用 Mahony 濾波算法。
    這個方法會自動根據加速度計和陀螺儀的讀數更新四元數，從而得到較準確的姿態角。
    每秒需要進行100運算,運算結果使用get_angles() 取得
get_angles(self)
    獲取計算後的歐拉角（Roll, Pitch, Yaw）。角度以度（°）為單位。
read_accel(self)
    讀取加速度數據，從 MPU6050 的加速度計傳感器獲取數據。返回的加速度數據經過轉換為 g 單位（重力加速度的倍數）。
read_gyro(self)
    讀取陀螺儀數據，從 MPU6050 的陀螺儀傳感器獲取數據。返回的陀螺儀數據經過轉換為度每秒（deg/s），描述角速度。
read_accel_raw(self)
    直接讀取原始加速度數據。
calculate_tilt_angles_with_filter(self)
    計算mpu6050站立之後的傾斜角度，使用互補濾波器來平滑角度變化，以應對快速動態變化。
    此方法返回的角度以度（°）為單位，並會將角度維持在 -180° 到 180° 的範圍內。
Get_tilt_angles(self)
    取得Get_tilt_angles計算後的角度
calibrate_tilt(self, num_samples=100)
    校準站立時傾斜角度，主要用於設置加速度計的偏移值。
'''

import math
import time
import utime
from machine import Pin,I2C,Timer
from machine import mem32
from math import atan2, sqrt, pi, sin, cos,degrees
import math
import utime as time
import rp2


class MPU6050:
    def __init__(self, i2c, addr=0x68):
        time.sleep(1)  # 等待一秒讓電跟上
        self.i2c = i2c
        self.addr = addr
        self.init_device()
        self.roll = 0
        self.pitch = 0
        self.yaw = 0
        
        # Mahony算法相關參數
        self.twoKp = 2.0 * 5.0  # 2 * proportional gain
        self.twoKi = 2.0 * 0.0  # 2 * integral gain
        self.q0 = 0.0
        self.q1 = 1.0 #因為一開始倒置 所以設定初始狀態為倒置
        self.q2 = 0.0
        self.q3 = 0.0
        self.integralFBx = 0.0
        self.integralFBy = 0.0
        self.integralFBz = 0.0
        self.last_update = utime.ticks_us()
        self.inv_sample_freq = 1.0 / 100.0  # 假設採樣頻率為100Hz
        self.roll_offset = 0
        self.pitch_offset = 0
        
        self.accel_x_offset = 0
        self.accel_y_offset = 0
        self.accel_z_offset = 0
        self.inCalibrate = False
        self.last_tilt_angle = 0.0
    def init_device(self):
        # 初始化MPU6050
        self.i2c.writeto_mem(self.addr, 0x6B, b'\x00')  # 解除睡眠模式
        
    def calibrate(self, samples=100):
        print("Calibrating. Please keep the device still on a flat surface.")
        roll_sum = pitch_sum = 0
        for _ in range(samples):
            self.update_mahony()
            roll_sum += self.roll
            pitch_sum += self.pitch
            time.sleep_ms(10)
        
        self.roll_offset = roll_sum / samples
        self.pitch_offset = pitch_sum / samples
        print("Calibration complete.")
        
    def read_accel(self):
        # 讀取加速度數據
        data = self.i2c.readfrom_mem(self.addr, 0x3B, 6)
        accel_x = self._combine_bytes(data[0], data[1]) / 16384.0  # 轉換為 g 單位
        accel_y = self._combine_bytes(data[2], data[3]) / 16384.0
        accel_z = self._combine_bytes(data[4], data[5]) / 16384.0
        
        # 補償反向放置的影響
        accel_x = -accel_x
        accel_y = -accel_y
        return (accel_x, accel_y, accel_z)

    def read_gyro(self):
        # 讀取陀螺儀數據
        data = self.i2c.readfrom_mem(self.addr, 0x43, 6)
        gyro_x = self._combine_bytes(data[0], data[1]) / 131.0  # 轉換為 deg/s
        gyro_y = self._combine_bytes(data[2], data[3]) / 131.0
        gyro_z = self._combine_bytes(data[4], data[5]) / 131.0
         # 補償反向放置的影響
        gyro_x = -gyro_x
        gyro_y = -gyro_y
        
        return (gyro_x * math.pi / 180, gyro_y * math.pi / 180, gyro_z * math.pi / 180)  # 轉換為 rad/s

    def _combine_bytes(self, msb, lsb):
        # 組合高位和低位字節
        value = msb << 8 | lsb
        if value >= 0x8000:
            value = -((65535 - value) + 1)
        return value

    def update_mahony(self):
        ax, ay, az = self.read_accel()
        gx, gy, gz = self.read_gyro()
        
        # 計算採樣週期
        now = utime.ticks_us()
        dt = utime.ticks_diff(now, self.last_update) / 1000000.0
        self.last_update = now

        # 正規化加速度向量
        norm = math.sqrt(ax * ax + ay * ay + az * az)
        if (norm==0):
            return
        recipNorm = 1.0 / norm
        ax *= recipNorm
        ay *= recipNorm
        az *= recipNorm

        # 估算方向誤差向量
        halfvx = self.q1 * self.q3 - self.q0 * self.q2
        halfvy = self.q0 * self.q1 + self.q2 * self.q3
        halfvz = self.q0 * self.q0 - 0.5 + self.q3 * self.q3

        # 誤差是測量值和估算值的叉積
        halfex = (ay * halfvz - az * halfvy)
        halfey = (az * halfvx - ax * halfvz)
        halfez = (ax * halfvy - ay * halfvx)

        # 計算並應用積分反饋（如果啟用）
        if self.twoKi > 0.0:
            self.integralFBx += self.twoKi * halfex * dt
            self.integralFBy += self.twoKi * halfey * dt
            self.integralFBz += self.twoKi * halfez * dt
            gx += self.integralFBx
            gy += self.integralFBy
            gz += self.integralFBz
        else:
            self.integralFBx = 0.0
            self.integralFBy = 0.0
            self.integralFBz = 0.0

        # 應用比例反饋
        gx += self.twoKp * halfex
        gy += self.twoKp * halfey
        gz += self.twoKp * halfez

        # 積分四元數比率並正規化
        gx *= 0.5 * dt
        gy *= 0.5 * dt
        gz *= 0.5 * dt
        qa = self.q0
        qb = self.q1
        qc = self.q2
        self.q0 += (-qb * gx - qc * gy - self.q3 * gz)
        self.q1 += (qa * gx + qc * gz - self.q3 * gy)
        self.q2 += (qa * gy - qb * gz + self.q3 * gx)
        self.q3 += (qa * gz + qb * gy - qc * gx)

        # 正規化四元數
        norm = math.sqrt(self.q0 * self.q0 + self.q1 * self.q1 + self.q2 * self.q2 + self.q3 * self.q3)
        if (norm == 0):
            return
        recipNorm = 1.0 / norm
        self.q0 *= recipNorm
        self.q1 *= recipNorm
        self.q2 *= recipNorm
        self.q3 *= recipNorm

        # 計算歐拉角
        self.roll = math.atan2(2.0 * (self.q0 * self.q1 + self.q2 * self.q3), 1.0 - 2.0 * (self.q1 * self.q1 + self.q2 * self.q2))
        self.pitch = math.asin(2.0 * (self.q0 * self.q2 - self.q3 * self.q1))
        self.yaw = math.atan2(2.0 * (self.q0 * self.q3 + self.q1 * self.q2), 1.0 - 2.0 * (self.q2 * self.q2 + self.q3 * self.q3))

    
    def get_angles(self): #回傳Eular角度
        yaw = self.yaw * 57.29578  # 弧度轉度數
        pitch = self.pitch * 57.29578  # 弧度轉度數
        roll = self.roll * 57.29578 +  180 # 弧度轉度數
        if (roll > 180): 
            roll = roll - 360
        return -roll , pitch , yaw
    
    def read_accel_raw(self):
        data = self.i2c.readfrom_mem(self.addr, 0x3B, 6)
        accel_x = self._combine_bytes(data[0], data[1])
        accel_y = self._combine_bytes(data[2], data[3])
        accel_z = self._combine_bytes(data[4], data[5])
        # 使用校準值調整讀數
        if (self.inCalibrate == False):
            accel_x -= self.accel_x_offset
            accel_y -= self.accel_y_offset
            accel_z -= self.accel_z_offset
        return (accel_x, accel_y, accel_z)  
    
    def calculate_tilt_angles_with_filter(self):
        x, y, z = self.read_accel_raw()
        accel_angle = atan2(y, x) * (180 / pi)  # 轉換為度
        if (accel_angle < -180):
            accel_angle = theta + 360
        
        #return accel_angle #如果不需要互補算法 這裡就可以回傳
        # 低通
        a = 2.0
        if (self.last_tilt_angle > 90 and accel_angle < -90):
            # 180度跳到-180度
            self.last_tilt_angle -= 360
        elif (self.last_tilt_angle < -90 and accel_angle > 90):
            # -180度跳到180度
            self.last_tilt_angle += 360
        self.last_tilt_angle = (self.last_tilt_angle * a + accel_angle) / (a + 1)
        # 確保角度保持在 [-180, 180] 範圍內
        if self.last_tilt_angle > 180:
            self.last_tilt_angle -= 360
        elif self.last_tilt_angle < -180:
            self.last_tilt_angle += 360
        
        return self.last_tilt_angle
    '''    
    def calculate_tilt_angles_Acc(self):
        x, y, z = self.read_accel_raw()
        accel_angle = atan2(y, x) * (180 / pi)  # 轉換為度
        if (accel_angle < -180):
            accel_angle = theta + 360
        
        return accel_angle #如果不需要互補算法 這裡就可以回傳
    '''
    
    def calculate_tilt_angles(self):
        # 讀取加速度計和陀螺儀數據
        ax, ay, az = self.read_accel_raw()
        gx, gy, gz = self.read_gyro()

        # 計算採樣週期
        now = utime.ticks_us()
        dt = utime.ticks_diff(now, self.last_update) / 1000000.0
        self.last_update = now

        # 使用加速度計計算傾斜角度
        accel_angle = atan2(ay, ax) * (180 / pi)  # 轉換為度

        # 使用陀螺儀數據計算角速度
        gyro_rate = -gz * (180 / pi)  # 轉換為度/秒

        # 處理角度跨越 ±180 度的情況
        angle_diff = accel_angle - self.last_tilt_angle
        if angle_diff > 180:
            angle_diff -= 360
        elif angle_diff < -180:
            angle_diff += 360

        # 互補濾波器
        alpha = 0.4  # 濾波器係數
        self.last_tilt_angle += alpha * (gyro_rate * dt) + (1 - alpha) * angle_diff

        # 確保角度保持在 [-180, 180] 範圍內
        if self.last_tilt_angle > 180:
            self.last_tilt_angle -= 360
        elif self.last_tilt_angle < -180:
            self.last_tilt_angle += 360

        return self.last_tilt_angle

    def Get_tilt_angles(self):
        return  self.last_tilt_angle
    
    def calibrate_tilt(self, num_samples=100):
        self.inCalibrate = True
        sum_x, sum_y, sum_z = 0, 0, 0
        for _ in range(num_samples):
            accel_x, accel_y, accel_z = self.read_accel_raw()
            sum_x += accel_x
            sum_y += accel_y
            sum_z += accel_z

        self.accel_x_offset = (sum_x / num_samples ) - 16384  # 站立時 X軸應該接近 16384（即 1g）
        self.accel_y_offset = (sum_y / num_samples)  
        self.accel_z_offset = (sum_z / num_samples)
        self.inCalibrate = False
    

    
if __name__ == '__main__':
    # mpu6050 的電源
    PAD_CONTROL_REGISTER = 0x4001c05c
    mem32[PAD_CONTROL_REGISTER] = mem32[PAD_CONTROL_REGISTER] | 0b0110000
    # GP22 為輸出，並設置輸出 1
    pin22 = Pin(22, Pin.OUT, value=0)
    time.sleep(1)
    pin22 = Pin(22, Pin.OUT, value=1)
    time.sleep(1)
    
    # 初始化I2C
    i2c = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
     # 初始化MPU6050 感測器
    mpu = MPU6050(i2c)

    # 時間變數初始化
    lastPrint = time.ticks_us()
    timestamp = time.ticks_us()
    
    while True:
        # 每 10 毫秒讀取一次數據 (100Hz)
        if (time.ticks_us() - timestamp) > 10000:
            mpu.update_mahony()
            mpu.calculate_tilt_angles()
            timestamp = time.ticks_us()
        
        # 每 100 毫秒ㄒ顯示一次數據 (10Hz) 太常顯示會讓效能降低
        if (time.ticks_us() - lastPrint) > 100000:
            roll , pitch , yaw = mpu.get_angles()
            tilt1 =  mpu.last_tilt_angle
            print("titl: {:.2f} Orientation: Yaw: {:.2f}, Pitch: {:.2f}, Roll: {:.2f}".format(tilt1 ,yaw, pitch, roll))
            lastPrint = time.ticks_us()
        
        #按鈕按一下進行校正
        button = rp2.bootsel_button()
        if button == 1:
        # 只按一下
            while button == 1:
                button = rp2.bootsel_button()
            mpu.calibrate_tilt()
