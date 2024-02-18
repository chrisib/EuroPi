import europi
import europi_script
import math
import time

import _thread

from europi import b1, b2, oled

class MulticoreDemoScript(europi_script.EuroPiScript):
    def __init__(self):
        super().__init__()

        self.b1_time = time.ticks_ms()
        self.b2_time = time.ticks_ms()

        self.lfo_tick = 0

        @b1.handler
        def on_b1_press():
            self.b1_time = time.ticks_ms()

        def on_b2_press():
            self.b2_time = time.ticks_ms()

    def core0_thread(self):
        """Update the OLED and handle ISRs on the primary core

        This is technically the main loop of the program
        """
        while True:
            oled.centre_text(f"{self.b1_time}\n{self.b2_time}\n{self.lfo_tick}")

    def core1_thread(self):
        """Output a sine wave on cv1
        """
        while True:
            voltage = (math.sin(self.lfo_tick * math.pi / 180.0) + 1) * europi.MAX_OUTPUT_VOLTAGE / 2
            europi.cv1.voltage(voltage)
            self.lfo_tick = (self.lfo_tick + 1) % 360

    def main(self):
        worker_thread = _thread.start_new_thread(self.core1_thread, ())
        core0_thread()


if __name__ == "__main__":
    MulticoreDemoScript().main()
