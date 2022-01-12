from europi import *
from math import cos, radians


MAX_VOLTAGE = 10
HARMONICS = [1, 3, 5, 7, 11, 13]


def reset():
    global degree
    degree = 0
din.handler(reset)
b1.handler(reset)

def get_delay_increment_value():
    delay = (0.1 - (k1.read_position(100)/1000)) + (ain.read_voltage(1)/100)
    return delay, round((((1/delay)-10)/1)+1)

degree = 0
delay, increment_value = get_delay_increment_value()
pixel_x = OLED_WIDTH-1
pixel_y = OLED_HEIGHT-1
while True:
    rad = radians(degree)
    oled.vline(pixel_x,0,OLED_HEIGHT,0)
    for cv, multiplier in zip(cvs, HARMONICS):
        volts = ((0-(cos(rad*(1/multiplier)))+1))*(MAX_VOLTAGE/2)
        cv.voltage(volts)
        if cv != cv1:
            oled.pixel(pixel_x,pixel_y-int(volts*(pixel_y/10)),1)
    
    degree += increment_value
    sleep(delay)
    oled.scroll(-1,0)
    
    if round(degree, -1) % 10 == 0:
        delay, increment_value = get_delay_increment_value()
        oled.show()

