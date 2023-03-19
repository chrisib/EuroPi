#!/usr/bin/env python3
"""A EuroPi clone of ALM's Pamela's NEW Workout

The module has a master clock rate, with each channel outputting
a multiple/division of that rate.

Each channel supports the following options:
- clock multiplier/divider
- wave shape (?? -- may skip this)
    - square (default)
    - sine
    - saw
    - ramp
    - triangle
    - random
- amplitude %
- width %: how wide is the wave
- skip %: probability that any given trigger may skip (doesn't apply to sine/saw/ramp/triangle waves)
- euclidean rhythms
    - estep: # of steps
    - etrig: # of triggers
    - erot: pattern rotation
- output can be quantized to pre-generated scales
"""

from europi import *
from europi_script import EuroPiScript
from europi.contrib.quantizer import Quantizer
import time
import random

## The scales that each PamsOutput can quantize to
QSCALES = {
    #                        C      C#     D      D#     E      F      F#     G      G#     A      A#     B
    "Chromatic" : Quantizer([True,  True,  True,  True,  True,  True,  True,  True,  True,  True,  True,  True]),
    "Major"     : Quantizer([True,  False, True,  False, True,  True,  False, True,  False, True,  False, True]),
    "Maj135"    : Quantizer([True,  False, False, False, True,  False, False, True,  False, True,  False, True]),
    # TODO: more scales
    "Whole"     : Quantizer([True,  False, True,  False, True,  False, True,  False, True,  False, True,  False]),
}

class MasterClock:
    """The main clock that ticks and runs the outputs
    """
    
    def __init__(self, bpm):
        """Create the main clock to run at a given bpm
        """
        self.bpm = bpm

class PamsOutput:
    """Controls a single output pin
    """
    
    def __init__(self, pin_out):
        """Create a new output to control a single pin
        
        @param pin_out: One of the six output pins
        """
        self.output = pin_out

class EuroPams(EuroPiScript):
    def __init__(self):
        super().__init__()
        
    @classmethod
    def display_name(cls):
        return "EuroPam's"
        
    def main(self):
        pass
    
if __name__=="__main__":
    EuroPams().main()