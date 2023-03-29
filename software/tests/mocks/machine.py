class ADC:
    def __init__(self, *args):
        pass

    def read_u16(self, *args):
        return 0


class I2C:
    def __init__(self, channel, sda, scl, freq, *args):
        pass

    def scan(self):
        return []


class Pin:
    IN = "in"

    def __init__(self, id, *args):
        pass

    def irq(self, handler=None, trigger=None):
        pass

    def value(self, *args):
        pass


class PWM:
    def __init__(self, *args):
        pass

    def freq(self, f):
        pass

    def duty_u16(self, f):
        pass

class Timer:
    ONE_SHOT = 0
    PERIODIC = 1
    
    def __init__(mode=Timer.PERIODIC, freq=1000, callback=mycallback):
        pass
    
    def init(mode=Timer.PERIODIC, freq=1000, callback=mycallback):
        pass
    
    def deinit():
        pass

def freq(_):
    pass
