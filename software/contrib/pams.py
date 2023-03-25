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
    
    "NatMaj"    : Quantizer([True,  False, True,  False, True,  True,  False, True,  False, True,  False, True]),
    "HarMaj"    : Quantizer([True,  False, True,  False, True,  True,  False, True,  True,  False, True,  False]),
    
    "NatMin"    : Quantizer([True,  False, True,  True,  False, True,  False, True,  True,  False, True,  False]),
    "HarMin"    : Quantizer([True,  False, True,  True,  False, True,  False, True,  True,  False, False, True]),
    
    "Whole"     : Quantizer([True,  False, True,  False, True,  False, True,  False, True,  False, True,  False])
    
    # TODO: any additional scales?
    # maybe 1-3-5 or 1-3-5-b7 ?
    # Or some jazz scales?
}

class MasterClock:
    """The main clock that ticks and runs the outputs
    """
    
    ## The clock actually runs faster than its maximum BPM to allow
    #  clock divisions to work nicely
    #
    #  Use 24 internal clock pulses per quarter note, which is a
    #  valid MIDI standard.  This lets us handle triplets nicely, as
    #  well as smaller divisions down to /8
    PPQN = 24
    
    def __init__(self, bpm):
        """Create the main clock to run at a given bpm
        """
        self.bpm = bpm
        
        self.recalculate_ticks()
        
    def recalculate_ticks(self):
        """Recalculate the number of ms per tick
        """
        self.ms_per_beat = self.bpm / 60.0 * 1000.0
        self.ms_per_tick = self.ms_per_beat / self.PPQN

class PamsOutput:
    """Controls a single output jack
    """
    
    WAVE_SQUARE = 0
    WAVE_RANDOM = 1
    
    def __init__(self, cv_out):
        """Create a new output to control a single cv output
        
        @param cv_out: One of the six output pins
        """
        self.cv_out = cv_out
        
        ## What shape of wave are we generating?
        #
        #  For now, stick to square waves for triggers & gates
        self.wave = WAVE_SQUARE
        
        ## Euclidean -- number of steps in the pattern (0 = disabled)
        self.e_steps = 0
        
        ## Euclidean -- number of triggers in the pattern
        self.e_trigs = 0
        
        ## Euclidean -- rotation of the pattern
        self.e_rot = 0
        
        ## Probability that we skip an output [0-1]
        self.skip_prob = 0.0

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