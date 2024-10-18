# Definitions for all analogue ins & outs
string AIN = "ain"
string K1 = "k1"
string K2 = "k2"
string CV1 = "cv1"
string CV2 = "cv2"
string CV3 = "cv3"
string CV4 = "cv4"
string CV5 = "cv5"
string CV6 = "cv6"

# The name of the channel (e.g. "cv1", "k1", "ain")
string name

# The 0-1 "percentage" of the pin's current voltage
float32 percent

# 0-12 indicating the actual voltage of the pin
# If the pin does not support voltages (e.g. k1, k2), this will be zero
float32 volts
