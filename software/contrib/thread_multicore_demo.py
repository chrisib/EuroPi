import europi
import europi_script
import gc
import math
import time

import _thread

from europi import b1, b2, oled

GC_INTERVAL_MS = 250

class DigitalInputMonitor:
    """Polls the states of the digital inputs and sets bools to indicate if rising/falling edges are detected
    """
    def __init__(self):
        self.din_rising = False
        self.din_falling = False
        self.b1_rising = False
        self.b1_falling = False
        self.b2_rising = False
        self.b2_falling = False

        self.din_high = False
        self.b1_high = False
        self.b2_high = False

    def check(self):
        din_state = europi.din.value() != 0
        b1_state = europi.b1.value() != 0
        b2_state = europi.b2.value() != 0

        self.din_rising = not self.din_high and din_state
        self.din_falling = self.din_high and not din_state

        self.b1_rising = not self.b1_high and b1_state
        self.b1_falling = self.b1_high and not b1_state

        self.b2_rising = not self.b2_high and b2_state
        self.b2_falling = self.b2_high and not b2_state

        self.din_high = din_state
        self.b1_high = b1_state
        self.b2_high = b2_state


class MulticoreDemoScript(europi_script.EuroPiScript):
    def __init__(self):
        super().__init__()

        self.b1_time = time.ticks_ms()
        self.b2_time = time.ticks_ms()
        self.lfo_tick = 0

    def core0_thread(self):
        """Update the OLED and handle ISRs on the primary core

        This is technically the main loop of the program
        """
        io_state = DigitalInputMonitor()
        last_gc_at = time.ticks_ms()
        while True:
            io_state.check()

            if io_state.b1_rising:
                self.b1_time = time.ticks_ms()
            if io_state.b2_rising:
                self.b2_time = time.ticks_ms()

            oled.centre_text(f"{self.b1_time}\n{self.b2_time}\n{self.lfo_tick}")

            # do garbage collection periodically
            now = time.ticks_ms()
            if time.ticks_diff(now, last_gc_at) > GC_INTERVAL_MS:
                gc.collect()
                gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
                last_gc_at = now

    def core1_thread(self):
        """Output a sine wave on cv1
        """
        while True:
            voltage = (math.sin(self.lfo_tick * math.pi / 180.0) + 1) * europi.MAX_OUTPUT_VOLTAGE / 2
            europi.cv1.voltage(voltage)
            self.lfo_tick = (self.lfo_tick + 1) % 360

    def main(self):
        worker_thread = _thread.start_new_thread(self.core1_thread, ())
        self.core0_thread()


if __name__ == "__main__":
    MulticoreDemoScript().main()
