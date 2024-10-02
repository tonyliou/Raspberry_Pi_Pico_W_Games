import utime as time

class TimeToDo:
    def __init__(self, interval_ms):
        """
        初始化TimeToDo對象。
        
        :param interval_ms: 以毫秒為單位的執行間隔。
        """
        self.interval = interval_ms * 1000
        self.last_time = time.ticks_us()

    def Do(self, func, *args, **kwargs):
        """
        檢查是否應該執行指定的函數，如果時間到則執行。
        
        :param func: 要執行的函數。
        :param args: 函數的參數。
        :param kwargs: 函數的關鍵字參數。
        """
        current_time = time.ticks_us()
        if time.ticks_diff(current_time, self.last_time) >= self.interval:
            self.last_time = current_time
            func(*args, **kwargs)

