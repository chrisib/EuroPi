#!/usr/bin/env python3
"""A EuroPi clone of ALM's Pamela's NEW Workout

@author Chris Iverach-Brereton <ve4cib@gmail.com>
@year   2023

The module has a master clock rate, with each channel outputting
a multiple/division of that rate.

Each channel supports the following options:
- clock multiplier/divider
- wave shape
    - square (default)
    - sine
    - triangle
    - random
    - reset (trigger on clock stop)
- amplitude %: height of the wave as a percentage of the maximum output voltage
- width %: how wide is the wave
    - PWM for square waves: 0% is always off, 100% is always on
    - symmetry for triangle waves:
        - 0  : |\
        - 50 : /\
        - 100: /|
    - offset for random waves:
        - output = rnd(0, 1) * MAX_VOLTS * amplitude% + MAX_VOLTS * width%
    - ignored for sine waves
- skip %: probability that any given trigger may skip (doesn't apply to sine/saw/ramp/triangle waves)
- euclidean rhythms
    - estep: # of steps
    - etrig: # of triggers
    - erot: pattern rotation
- output can be quantized to pre-generated scales
"""

from europi import *
from europi_script import EuroPiScript

from contrib.euclid import generate_euclidean_pattern
from contrib.quantizer import Quantizer
from contrib.screensaver import Screensaver

from machine import Timer

import math
import time
import random

SELECT_OPTION_Y = 16
HALF_CHAR_WIDTH = int(CHAR_WIDTH / 2)

## How many ms does a button need to be held to qualify as a long press?
LONG_PRESS_MS = 500

## The scales that each PamsOutput can quantize to
QUANTIZERS = {
    #                        C      C#     D      D#     E      F      F#     G      G#     A      A#     B
    "Chromatic" : Quantizer([True,  True,  True,  True,  True,  True,  True,  True,  True,  True,  True,  True]),
    
    "Nat Maj"   : Quantizer([True,  False, True,  False, True,  True,  False, True,  False, True,  False, True]),
    "Har Maj"   : Quantizer([True,  False, True,  False, True,  True,  False, True,  True,  False, True,  False]),
    "Maj 135"   : Quantizer([True,  False, False, False, True,  False, False, True,  False, False, False, False]),
    
    "Nat Min"   : Quantizer([True,  False, True,  True,  False, True,  False, True,  True,  False, True,  False]),
    "Har Min"   : Quantizer([True,  False, True,  True,  False, True,  False, True,  True,  False, False, True]),
    "Min 135"   : Quantizer([True,  False, False, True,  False, False, False, True,  False, False, False, False]),
    
    "Whole"     : Quantizer([True,  False, True,  False, True,  False, True,  False, True,  False, True,  False]),
    
    "135b7"     : Quantizer([True,  False, False,  False, True, False, False, True,  False, False, True,  False])
    
    # TODO: any additional scales?
    # maybe 1-3-5 or 1-3-5-b7 ?
    # Or some jazz scales?
}

## Sorted list of names for the quantizers to display
QUANTIZER_LABELS = [
    "None",
    "Chromatic",
    "Nat Maj",
    "Har Maj",
    "Maj 135",
    "Nat Min",
    "Har Min",
    "Min 135",
    "Whole",
    "135b7"
]

## Available clock modifiers
CLOCK_MODS = {
    "x8" : 8.0,
    "x6" : 6.0,
    "x4" : 4.0,
    "x3" : 3.0,
    "x2" : 2.0,
    "x1" : 1.0,
    "/2" : 1/2.0,
    "/3" : 1/3.0,
    "/4" : 1/4.0,
    "/6" : 1/6.0,
    "/8" : 1/8.0,
    "/12" : 1/12.0,
    "/16" : 1/16.0
}

## Sorted list of labels for the clock modifers to display
CLOCK_MOD_LABELS = [
    "x8",
    "x6",
    "x4",
    "x3",
    "x2",
    "x1",
    "/2",
    "/3",
    "/4",
    "/6",
    "/8",
    "/12",
    "/16"
]

## Standard pulse/square wave with PWM
WAVE_SQUARE = 0

## Triangle wave
#
#  - When width is 50 this is a symmetrical triangle /\
#  - When width is < 50 we become more saw-like |\
#  - When sidth is > 50 we become more ramp-like /|
WAVE_TRIANGLE = 1

## Sine wave
#
#  Width is ignored
WAVE_SIN = 2

## Random wave
#
#  Width is ignored
WAVE_RANDOM = 3

## Reset gate
#
#  Turns on when the clock stops
WAVE_RESET = 4

## Available wave shapes
WAVE_SHAPES = {
    "Squ" : WAVE_SQUARE,
    "Tri" : WAVE_TRIANGLE,
    "Sin" : WAVE_SIN,
    "Rnd" : WAVE_RANDOM,
    "Rst" : WAVE_RESET
}

## Ordered list of labels for the wave shape chooser menu
WAVE_SHAPE_LABELS = [
    "Squ",
    "Tri",
    "Sin",
    "Rnd",
    "Rst"
]

## Sorted list of wave shapes to display
#
#  Same order as WAVE_SHAPE_LABELS
#
#  These are 12x12 bitmaps. See:
#  - https://github.com/Allen-Synthesis/EuroPi/blob/main/software/oled_tips.md
#  - https://github.com/novaspirit/img2bytearray
WAVE_SHAPE_IMGS = [
    b'\xfe\x00\x82\x00\x82\x00\x82\x00\x82\x00\x82\x00\x82\x00\x82\x00\x82\x00\x82\x00\x82\x00\x83\xf0',
    b'\x06\x00\x06\x00\t\x00\t\x00\x10\x80\x10\x80 @ @@ @ \x80\x10\x80\x10',
    b'\x10\x00(\x00D\x00D\x00\x82\x00\x82\x00\x82\x10\x82\x10\x01\x10\x01\x10\x00\xa0\x00@',
    b'\x00\x00\x08\x00\x08\x00\x14\x00\x16\x80\x16\xa0\x11\xa0Q\xf0Pp`P@\x10\x80\x00',
    b'\x03\xf0\x02\x00\x02\x00\x02\x00\x02\x00\x02\x00\x02\x00\x02\x00\x02\x00\x02\x00\x02\x00\xfe\x00'
]

## Duration before we activate the screensaver
SCREENSAVER_TIMEOUT_MS = 1000 * 60 * 5

## Duration before we blank the screen
BLANK_TIMEOUT_MS = 1000 * 60 * 20

class MasterClock:
    """The main clock that ticks and runs the outputs
    """
    
    ## The clock actually runs faster than its maximum BPM to allow
    #  clock divisions to work nicely
    #
    #  Use 24 internal clock pulses per quarter note. This is slow enough
    #  that we won't choke the CPU with interrupts, but smooth enough that we
    #  should be able to approximate complex waves.  Must be a multiple of
    #  3 to properly support triplets
    PPQN = 24
    
    ## The absolute slowest the clock can go
    MIN_BPM = 1
    
    ## The absolute fastest the clock can go
    MAX_BPM = 300
    
    def __init__(self, bpm, channels):
        """Create the main clock to run at a given bpm
        @param bpm  The initial BPM to run the clock at
        @param channels  A list of PamsOutput objects corresponding to the
                         output channels
        """
        self.is_running = False
        self.bpm = bpm
        self.reset_on_start = True
        self.channels = channels
        self.timer = Timer()
        self.recalculate_ticks()
        
    def to_dict(self):
        """Return a dict with the clock's parameters
        """
        return {
            "bpm": self.bpm,
            "reset_on_start": self.reset_on_start
        }
    
    def load_settings(self, settings):
        """Apply settings loaded from the configuration file
        @param settings  A dict containing the same fields as to_dict(self)
        """
        if "bpm" in settings:
            self.bpm = settings["bpm"]
        if "reset_on_start" in settings:
            self.reset_on_start = settings["reset_on_start"]
            
        self.recalculate_ticks()
        
    def __getitem__(self, key):
        """Equivalent of __getattr__ for values that can be set by the SettingChooser
        @param key  The name of the attribute we're getting
        
        @raises KeyError if the key is invalid
        """
        if key == "bpm":
            return self.bpm
        elif key == "reset_on_start":
            return self.reset_on_start
        else:
            raise KeyError(f"Key \"{key}\" is not valid")
        
    def __setitem__(self, key, value):
        """Equivalent of __setattr__ for values that can be set by the SettingChooser
        @param key  The name of the attribute we're setting
        @param value  The value we're assigning
        
        @raises KeyError if the key is invalid
        """
        if key == "bpm":
            self.change_bpm(value)
        elif key == "reset_on_start":
            self.reset_on_start = value
        else:
            raise KeyError(f"Key \"{key}\" is not valid")
        
    def on_tick(self, timer):
        """Callback function for the timer's tick
        """
        for ch in self.channels:
            ch.tick()
        
    def start(self):
        """Start the timer
        """
        if not self.is_running:
            self.is_running = True
            
            if self.reset_on_start:
                for ch in self.channels:
                    ch.reset()
            
            self.timer.init(period=round(self.ms_per_tick), mode=Timer.PERIODIC, callback=self.on_tick)
        
    def stop(self):
        """Stop the timer
        """
        if self.is_running:
            self.is_running = False
            self.timer.deinit()
            
            # Fire a reset trigger on any channels that have the WAVE_RESET mode set
            # This trigger lasts 10ms
            # Turn all other channels off so we don't leave hot wires
            for ch in self.channels:
                if ch.wave_shape == WAVE_RESET:
                    ch.cv_out.voltage(MAX_OUTPUT_VOLTAGE * ch.amplitude / 100.0)
                else:
                    ch.cv_out.voltage(0.0)
            time.sleep(0.01)   # time.sleep works in SECONDS not ms
            for ch in self.channels:
                if ch.wave_shape == WAVE_RESET:
                    ch.cv_out.voltage(0)
        
    def recalculate_ticks(self):
        """Recalculate the number of ms per tick
        If the timer is currently running deinitialize it and reset it to use the correct BPM
        """
        min_per_beat = 1.0 / self.bpm
        self.ms_per_beat = min_per_beat * 60.0 * 1000.0
        self.ms_per_tick = self.ms_per_beat / self.PPQN
        
        if self.is_running:
            self.timer.deinit()
            self.timer.init(period=round(self.ms_per_tick), mode=Timer.PERIODIC, callback=self.on_tick)
        
    def change_bpm(self, new_bpm):
        self.bpm = new_bpm
        self.recalculate_ticks()

class PamsOutput:
    """Controls a single output jack
    """
    
    ## The maximum length of a Euclidean pattern we allow
    #
    #  Because we need to generate the whole sequence at whatever our PPQN is
    #  with a potentially very slow clock mod, this cannot be too high to avoid
    #  issues with RAM usage
    MAX_EUCLID_LENGTH = 16
    
    def __init__(self, cv_out):
        """Create a new output to control a single cv output
        
        @param cv_out: One of the six output pins
        """
        self.cv_out = cv_out
        
        ## What quantization are we using?
        #
        #  See contrib.pams.QUANTIZERS
        self.quantizer_txt = "None"
        self.quantizer = None
        
        ## The clock modifier for this channel
        #
        #  - 1.0 is the same as the main clock's BPM
        #  - <1.0 will tick slower than the BPM (e.g. 0.5 will tick once every 2 beats)
        #  - >1.0 will tick faster than the BPM (e.g. 3.0 will tick 3 times per beat)
        self.clock_mod_txt = "x1"
        self.clock_mod = CLOCK_MODS[self.clock_mod_txt]
        
        ## What shape of wave are we generating?
        #
        #  For now, stick to square waves for triggers & gates
        self.wave_shape = WAVE_SQUARE
        self.wave_shape_txt = WAVE_SHAPE_LABELS[self.wave_shape]
        
        ## The amplitude of the output as a [0, 100] percentage
        self.amplitude = 50   # default to 5V gates
        
        ## Wave width
        self.width = 50
        
        ## Euclidean -- number of steps in the pattern (0 = disabled)
        self.e_step = 0
        
        ## Euclidean -- number of triggers in the pattern
        self.e_trig = 0
        
        ## Euclidean -- rotation of the pattern
        self.e_rot = 0
        
        ## Probability that we skip an output [0-100]
        self.skip = 0
        
        ## The position we're currently playing inside playback_pattern
        self.playback_position = 0
        
        ## The pre-calculated waveform we step through during playback
        self.playback_pattern = [0]
        
        ## If we change patterns while playing store the next one here and
        #  change when the current pattern ends
        #
        #  This helps ensure all outputs stay synchronized. The down-side is
        #  that a slow pattern may take a long time to reset
        self.next_pattern = None
        
        ## The previous voltage we output
        self.previous_voltage = 0
        
        ## Used during the tick() function to store whether or not we're skipping
        #  the current step
        self.skip_this_step = False
        
        self.recalculate_pattern()
        
    def to_dict(self):
        """Return a dictionary with all the configurable settings to write to disk
        """
        return {
            "clock_mod" : self.clock_mod_txt,
            "e_step"    : self.e_step,
            "e_trig"   : self.e_trig,
            "e_rot"     : self.e_rot,
            "skip"      : self.skip,
            "wave"      : self.wave_shape_txt,
            "amplitude" : self.amplitude,
            "width"     : self.width,
            "quant"     : self.quantizer_txt
        }
    
    def load_settings(self, settings):
        """Apply the settings loaded from storage

        @param settings  A dict with the same keys as the one returned by to_dict()
        """
        if "clock_mod" in settings:
            self.clock_mod_txt = settings["clock_mod"]
            self.clock_mod = CLOCK_MODS[self.clock_mod_txt]
        if "e_step" in settings:
            self.e_step = settings["e_step"]
        if "e_trig" in settings:
            self.e_trig = settings["e_trig"]
        if "e_rot" in settings:
            self.e_rot = settings["e_rot"]
        if "skip" in settings:
            self.skip = settings["skip"]
        if "wave" in settings:
            self.wave_shape_txt = settings["wave"]
            self.wave_shape = WAVE_SHAPES[self.wave_shape_txt]
        if "amplitude" in settings:
            self.amplitude = settings["amplitude"]
        if "width" in settings:
            self.width = settings["width"]
        if "quant" in settings:
            self.quantizer_txt = settings["quant"]
            if self.quantizer_txt in QUANTIZERS.keys():
                self.quantizer = QUANTIZERS[self.quantizer_txt]
            else:
                self.quantizer = None
        
        self.recalculate_pattern()
        
    def __getitem__(self, key):
        """Equivalent of __setattr__ for values that can be set by the SettingChooser

        @param key  The name of the attribute we're getting
        
        @raises KeyError if the key is invalid
        """
        if key == "clock_mod_txt":
            return self.clock_mod_txt
        elif key == "e_step":
            return self.e_step
        elif key == "e_trig":
            return self.e_trig
        elif key == "e_rot":
            return self.e_rot
        elif key == "skip":
            return self.skip
        elif key == "wave_shape_txt":
            return self.wave_shape_txt
        elif key == "amplitude":
            return self.amplitude
        elif key == "width":
            return self.width
        elif key == "quantizer_txt":
            return self.quantizer_txt
        else:
            raise KeyError(f"Key \"{key}\" is not valid")
        
    def __setitem__(self, key, value):
        """Equivalent of __setattr__ for values that can be set by the SettingChooser

        @param key  The name of the attribute we're setting
        @param value  The value we're assigning
        
        @raises KeyError if the key is invalid
        """
        if key == "clock_mod_txt":
            self.clock_mod_txt = value
            self.clock_mod = CLOCK_MODS[self.clock_mod_txt]
            self.recalculate_pattern()
        elif key == "e_step":
            self.e_step = value
            # make sure the number of pulses & rotation are still valid!
            if self.e_trig > self.e_step:
                self.e_trig = self.e_step
            if self.e_rot > self.e_step:
                self.e_rot = self.e_step
            self.recalculate_pattern()
        elif key == "e_trig":
            self.e_trig = value
            self.recalculate_pattern()
        elif key == "e_rot":
            self.e_rot = value
            self.recalculate_pattern()
        elif key == "skip":
            self.skip = value
        elif key == "wave_shape_txt":
            self.wave_shape_txt = value
            self.wave_shape = WAVE_SHAPES[self.wave_shape_txt]
            self.recalculate_pattern()
        elif key == "amplitude":
            self.amplitude = value
        elif key == "width":
            self.width = value
            self.recalculate_pattern()
        elif key == "quantizer_txt":
            self.quantizer_txt = value
            if value in QUANTIZERS.keys():
                self.quantizer = QUANTIZERS[self.quantizer_txt]
            else:
                self.quantizer = None
        else:
            raise KeyError(f"Key \"{key}\" is not valid")
        
    def recalculate_pattern(self):
        """Recalculate the internal trigger pattern for this channel

        The generated pattern has values in the range [0, 1] which can be multiplied
        by the amplitude and output voltage to produce the correct output
        """
        
        # always assume we're doing some kind of euclidean pattern
        e_pattern = [1]
        if self.e_step > 0:
            e_pattern = generate_euclidean_pattern(self.e_step, self.e_trig, self.e_rot)
            
        # determine the number of clock pulses in the whole pattern
        pulses = round(MasterClock.PPQN / self.clock_mod * len(e_pattern))
        
        # How many clock pulses do we need per note?
        # All regular waveforms will be stretched to be exactly this long
        # Note that we've set up our clock mods so this will _always_ be an integer
        # and round is just there to handle floating point weirdness
        ticks_per_note = round(MasterClock.PPQN / self.clock_mod)
        
        # the generated samples as floats
        # for most waveforms this is the raw voltage to send to the output
        # for random waves this is just a 0/1 value to indicate when we should
        # choose a new random voltage
        samples = []
        
        for pulse in e_pattern:
            for tick in range(ticks_per_note):
                if pulse == 0:
                    # this is an off-pulse; don't do anything
                    samples.append(0.0)
                else:
                    # the signal should be on
                    # generate the appropriate waveform
                    if self.wave_shape == WAVE_RANDOM:
                        samples.append(1.0)
                    elif self.wave_shape == WAVE_SQUARE:
                        duty_cycle = ticks_per_note * self.width / 100.0
                        if tick < duty_cycle:
                            samples.append(1.0)
                        else:
                            samples.append(0.0)
                    elif self.wave_shape == WAVE_TRIANGLE:
                        rising_ticks = round(ticks_per_note * self.width / 100.0)
                        falling_ticks = ticks_per_note - rising_ticks
                        
                        peak = 1.0
                        
                        if tick < rising_ticks:
                            # we're on the rising side of the triangle wave
                            step = peak / rising_ticks
                            volts = step * tick
                            samples.append(volts)
                        elif tick == rising_ticks:
                            # we're at the peak of the triangle
                            samples.append(peak)
                        else:
                            # we're on the falling side of the triangle
                            step = peak / falling_ticks
                            volts = peak - step * (tick - rising_ticks)
                            samples.append(volts)
                        
                    elif self.wave_shape == WAVE_SIN:
                        theta = tick / ticks_per_note * 2 * math.pi  # covert the tick to radians
                        s_theta = (math.sin(theta) + 1 / 2)           # (sin(x) + 1)/2 since we can't output negative voltages
                        
                        samples.append(s_theta)
                    else:
                        # unknown wave or not implemented yet
                        # leave things off for safety
                        samples.append(0.0)
        
        self.next_pattern = samples
    
    def reset(self):
        """Reset the current output to the beginning
        """
        self.playback_position = 0
        if self.next_pattern:
            self.playback_pattern = self.next_pattern
            self.next_pattern = None
    
    def tick(self):
        """Advance the current pattern one tick and set the output voltage
        """
        # advance the playback position to the next sample
        previous_sample_position = self.playback_position
        self.playback_position = self.playback_position + 1
        if self.playback_position >= len(self.playback_pattern):
            self.playback_position = 0
            
            # if we've queued a pattern change, apply it now, once the current one ends
            if self.next_pattern:
                self.playback_pattern = self.next_pattern
                self.next_pattern = None
                previous_sample_position = len(self.playback_pattern) - 1
        
        out_volts = self.playback_pattern[self.playback_position]
        
        # are we restarting the pattern OR hitting a new pulse inside the euclidean rhythm?
        rising_edge = self.playback_position == 0 or (self.playback_pattern[previous_sample_position] == 0 and self.playback_pattern[self.playback_position] > 0)
        
        # if we're starting a new signal, determine if we should skip it
        if rising_edge:
            self.skip_this_step = random.randint(0, 100) < self.skip
        
        # generate a new random voltage on the rising edge of the playback pattern
        # otherwise just sustain the previous output
        if self.wave_shape == WAVE_RANDOM:
            if rising_edge and not self.skip_this_step:
                out_volts = MAX_OUTPUT_VOLTAGE * random.random() * (self.amplitude / 100.0) + MAX_OUTPUT_VOLTAGE * (self.width / 100.0)
            else:
                out_volts = self.previous_voltage
        else:
            if not self.skip_this_step:
                out_volts = MAX_OUTPUT_VOLTAGE * self.playback_pattern[self.playback_position] * (self.amplitude / 100.0)
            else:
                out_volts = 0.0
            
        if self.quantizer is not None:
            (out_volts, note) = self.quantizer.quantize(out_volts)
            
        self.cv_out.voltage(out_volts)
        
        # save the new voltage for the next tick's previous
        self.previous_voltage = out_volts

class CVController:
    """Allows the signal from AIN to be routed to another object to control its properties
    """
    
    DESTINATIONS = [
        "None",
        "Clock",
        "CV1",
        "CV2",
        "CV3",
        "CV4",
        "CV5",
        "CV6"
    ]
    
    def __init__(self, cv_in, application):
        self.app = application
        self.cv_in = cv_in
        self.dest_obj = None
        self.dest_obj_txt = "None"
        self.dest_key = "None"
        self.gain = 100
        
        self.dest_objects = {
            "None"  : None,
            "Clock" : self.app.clock,
            "CV1"   : self.app.channels[0],
            "CV2"   : self.app.channels[1],
            "CV3"   : self.app.channels[2],
            "CV4"   : self.app.channels[3],
            "CV5"   : self.app.channels[4],
            "CV6"   : self.app.channels[5]
        }
        
        cv_channel_dests = [
            "Clock Mod",
            "Wave",
            "Width",
            "Ampl.",
            "Skip%",
            "ESteps",
            "ETrigs",
            "ERot",
            "Quant."
        ]
        
        self.dest_keys = {
            "None"  : ["None"],
            "Clock" : ["BPM"],
            "CV1"   : cv_channel_dests,
            "CV2"   : cv_channel_dests,
            "CV3"   : cv_channel_dests,
            "CV4"   : cv_channel_dests,
            "CV5"   : cv_channel_dests,
            "CV6"   : cv_channel_dests
        }
        
        self.none_keys = {
            "None": "none"
        }
        
        self.clock_keys = {
            "BPM": "bpm"
        }
        
        self.cv_keys = {
            "Clock Mod" : "clock_mod_txt",
            "Wave"      : "wave_shape_txt",
            "Width"     : "width",
            "Ampl."     : "amplitude",
            "Skip%"     : "skip",
            "ESteps"    : "e_step",
            "ETrigs"    : "e_trig",
            "ERot"      : "e_rot",
            "Quant."    : "quantizer_txt"
        }
        
        self.low_level_keys = {
            "None"  : self.none_keys,
            "Clock" : self.clock_keys,
            "CV1"   : self.cv_keys,
            "CV2"   : self.cv_keys,
            "CV3"   : self.cv_keys,
            "CV4"   : self.cv_keys,
            "CV5"   : self.cv_keys,
            "CV6"   : self.cv_keys
        }
        
    def __clamp_euclid_range(self):
        return list(range(self.dest_obj.e_step+1))
    
    def __get_applicable_options(self):
        if self.dest_key == "ETrigs" or self.dest_key == "ERot":
            return self.__clamp_euclid_range()
        elif self.dest_key == "ESteps":
            return list(range(PamsOutput.MAX_EUCLID_LENGTH+1))
        elif self.dest_key == "BPM":
            return list(range(MasterClock.MIN_BPM, MasterClock.MAX_BPM+1))
        elif self.dest_key == "Clock Mod":
            return CLOCK_MOD_LABELS
        elif self.dest_key == "Wave":
            return WAVE_SHAPE_LABELS
        elif self.dest_key == "Width" or self.dest_key == "Ampl." or self.dest_key == "Skip%":
            return list(range(101))
        elif self.dest_key == "Quant.":
            return QUANTIZER_LABELS
        else:
            return [0]
        
    def get_dest_options(self):
        return self.dest_keys[self.dest_obj_txt]
        
    def to_dict(self):
        """Return a dictionary with all the configurable settings to write to disk
        """
        return {
            "dest_obj"  : self.dest_obj_txt,
            "dest_key"  : self.dest_key,
            "gain"      : self.gain
        }
    
    def load_settings(self, settings):
        """Apply the settings loaded from storage

        @param settings  A dict with the same keys as the one returned by to_dict()
        """
        
        if "dest_obj" in settings:
            self.dest_obj_txt = settings["dest_obj"]
            self.dest_obj = self.dest_objects[self.dest_obj_txt]
            
        if "dest_key" in settings:
            self.dest_key = settings["dest_key"]
            
        if "gain" in settings:
            self.gain = settings["gain"]
        
    def __getitem__(self, key):
        if key == "dest_obj_txt":
            return self.dest_obj_txt
        elif key == "dest_key":
            return self.dest_key
        elif key == "gain":
            return self.gain
        else:
            raise KeyError(f"Key \"{key}\" is not valid")
    
    def __setitem__(self, key, value):
        if key == "dest_obj_txt":
            self.dest_obj_txt = value
            self.dest_obj = self.dest_objects[value]
            
            # Make sure the dest key is in the valid options for the dest object
            if not (self.dest_key in self.dest_keys[self.dest_obj_txt]):
                self.dest_key = self.dest_keys[self.dest_obj_txt][0]
        elif key == "dest_key":
            self.dest_key = value
        elif key == "gain":
            self.gain = value
        else:
            raise KeyError(f"Key \"{key}\" is not valid")
    
    def read_and_apply(self):
        """Read the analogue input and apply it to the destination object
        """
        try:
            if self.dest_obj:
                options = self.__get_applicable_options()
                low_level_key = self.low_level_keys[self.dest_obj_txt][self.dest_key]
                
                volts = self.cv_in.read_voltage()
                volts = volts * self.gain / 100.0
                index = min(len(options)-1, round(volts / MAX_INPUT_VOLTAGE * len(options)))
                self.dest_obj[low_level_key] = options[index]
        except:
            # If we're unlucky and modify the destination _during_ a thread interruption
            # we can get thread-unsafe and have a bad key
            # Just suppress the error and carry on
            pass

class SettingChooser:
    """Menu UI element for displaying an option and the choices associated with it
    """
    def __init__(self, title, options, dest_obj, dest_prop, submenu=None, gfx=None, validate_settings=None):
        """Create a setting chooser for a given item
        
        The dest_obj must implement __getitem__ and __setitem__, since this version of
        micropython doesn't support __getattr__ and __setattr__.
        
        When the value is written to dest_obj we call
        ```
        dest_obj[dest_pro] = NEW_VALUE
        ```
        
        Any validation must be done on the object end inside the __setitem__ implementation

        @param title  The title of this menu item
        @param options  The available values we actually choose from
        @param dest_obj  The object whose property we're editing, e.g. a MasterClock instance
        @param dest_prop  The name of the attribute of dest_obj to edit.
        @param submenu  A list of SettingChooser items that make up this setting's submenu
        @param gfx  A list of 12x12 pixel bitmaps we can optionally display beside option_txt
        @param validate_settings  A function for this chooser to call that will return a new value for options
               to ensure that we have the correct range.  Needed if setting X's options depend on the value of
               setting Y
        """
        
        self.title = title
        self.options = options
        self.option_gfx = gfx
        self.dest_obj = dest_obj
        self.dest_prop = dest_prop
        
        self.submenu = submenu
        
        self.validate_settings_fn = validate_settings
        
        self.is_writable = False
        
    def __str__(self):
        return f"Setting Chooser for {dest_obj}.{dest_prop}"
        
    def reconfigure_options(self, options):
        """Reconfigure the the available options.

        For example, if we change the number of steps in a Euclidean rhythm, the number of
        pulses cannot exceed the number of steps
        
        @param options  The new set of options we allow
        """
        
        self.options = options
        
    def set_editable(self, can_edit):
        """Set whether or not we can write to this setting
        
        @param can_edit  If True, we can write a new value
        """
        
        self.is_writable = can_edit
        
    def is_editable(self):
        return self.is_writable
        
    def draw(self):
        """Draw the menu to the screen
        """
        
        text_left = 0
        
        oled.fill(0)
        oled.text(f"{self.title}", 0, 0)
        
        if self.option_gfx is not None:
            # draw the option thumbnail to the screen
            text_left = 14
            if self.is_writable:
                img = bytearray(k2.choice(self.option_gfx))
            else:
                key = self.dest_obj[self.dest_prop]
                index = self.options.index(key)
                img = bytearray(self.option_gfx[index])
            imgFB = FrameBuffer(img, 12, 12, MONO_HLSB)
            oled.blit(imgFB,0,SELECT_OPTION_Y)
            
        
        if self.is_writable:
            if self.validate_settings_fn:
                self.options = self.validate_settings_fn()
            
            # draw the selection in inverted text
            selected_item = k2.choice(self.options)
            choice_text = f"{selected_item}"
            text_width = len(choice_text)*CHAR_WIDTH
            
            oled.fill_rect(text_left, SELECT_OPTION_Y, text_left+text_width+3, CHAR_HEIGHT+4, 1)
            oled.text(choice_text, text_left+1, SELECT_OPTION_Y+2, 0)
        else:
            # draw the selection in normal text
            choice_text = f"{self.dest_obj[self.dest_prop]}"
            oled.text(choice_text, text_left+1, SELECT_OPTION_Y+2, 1)
        
        oled.show()
        
    def on_click(self):
        if self.is_writable:
            self.set_editable(False)
            selected_item = k2.choice(self.options)
        
            self.dest_obj[self.dest_prop] = selected_item
        else:
            self.set_editable(True)

class PamsMenu:
    def __init__(self, script):
        """Create the top-level menu for the application

        @param script  The PamsWorkout object the meny belongs to
        """
        
        self.pams_workout = script
        
        self.items = [
            SettingChooser("BPM", list(range(MasterClock.MIN_BPM, MasterClock.MAX_BPM+1)), script.clock, "bpm", [
                SettingChooser("Reset", [True, False], script.clock, "reset_on_start")
            ])
        ]
        for i in range(len(script.channels)):
            self.items.append(SettingChooser(f"CV{i+1} | Clk Mod", CLOCK_MOD_LABELS, script.channels[i], "clock_mod_txt", [
                SettingChooser(f"CV{i+1} | Wave", WAVE_SHAPE_LABELS, script.channels[i], "wave_shape_txt", gfx=WAVE_SHAPE_IMGS),
                SettingChooser(f"CV{i+1} | Width.", list(range(101)), script.channels[i], "width"),
                SettingChooser(f"CV{i+1} | Ampl.", list(range(101)), script.channels[i], "amplitude"),
                SettingChooser(f"CV{i+1} | Skip%", list(range(101)), script.channels[i], "skip"),
                SettingChooser(f"CV{i+1} | ESteps", list(range(PamsOutput.MAX_EUCLID_LENGTH+1)), script.channels[i], "e_step"),
                SettingChooser(f"CV{i+1} | EPulses", list(range(PamsOutput.MAX_EUCLID_LENGTH+1)), script.channels[i], "e_trig",
                               validate_settings = lambda:list(range(script.channels[i].e_step+1))),
                SettingChooser(f"CV{i+1} | ERot.", list(range(PamsOutput.MAX_EUCLID_LENGTH+1)), script.channels[i], "e_rot",
                               validate_settings = lambda:list(range(script.channels[i].e_step+1))),
                SettingChooser(f"CV{i+1} | Quant.", QUANTIZER_LABELS, script.channels[i], "quantizer_txt")
            ]))
            
        self.items.append(SettingChooser(f"AIN | Gain%", list(range(301)), script.cv_in, "gain", [
            SettingChooser("Dest.", CVController.DESTINATIONS, script.cv_in, "dest_obj_txt"),
            SettingChooser("Prop", [], script.cv_in, "dest_key", validate_settings = script.cv_in.get_dest_options)
        ]))
            
        self.active_items = self.items
        
        ## The item we're actually drawing to the screen _right_now_
        self.visible_item = k1.choice(self.active_items)
        
    def on_long_press(self):
        # return the active item to the read-only state
        self.visible_item.set_editable(False)
        
        # toggle between the two menu levels
        if self.active_items == self.items:
            self.active_items = self.visible_item.submenu
        else:
            self.active_items = self.items
            
    def on_click(self):
        self.visible_item.on_click()
            
    def draw(self):
        if not self.visible_item.is_editable():
            self.visible_item = k1.choice(self.active_items)
            
        self.visible_item.draw()

class PamsWorkout(EuroPiScript):
    """The main script for the Pam's Workout implementation
    """
    def __init__(self):
        super().__init__()
        
        self.channels = [
            PamsOutput(cv1),
            PamsOutput(cv2),
            PamsOutput(cv3),
            PamsOutput(cv4),
            PamsOutput(cv5),
            PamsOutput(cv6),
        ]
        self.clock = MasterClock(120, self.channels)
        self.cv_in = CVController(ain, self)
        
        ## The master top-level menu
        self.main_menu = PamsMenu(self)
        
        ## The screensaver
        self.screensaver = Screensaver()
        
        ## How long ago was _either_ button pressed?
        #
        #  This is used to wake the screensaver up and suppress the normal
        #  button operations while doing so
        self.last_interaction_time = time.ticks_ms()
        
        @b1.handler
        def on_b1_press():
            """Handler for pressing button 1

            Button 1 starts/stops the master clock
            """
            if self.clock.is_running:
                self.clock.stop()
            else:
                self.clock.start()
                
        @b1.handler_falling
        def on_b1_release():
            """Handler for releasing button 1

            Wake up the display if it's asleep.  We do this on release to keep the
            wake up behavior the same for both buttons
            """
            now = time.ticks_ms()
            self.last_interaction_time = now
            
            
        @b2.handler_falling
        def on_b2_release():
            """Handler for releasing button 2

            Handle long vs short presses differently

            Button 2 is used to cycle between screens
            
            If the screensaver is visible, just wake up the display & don't process
            the actual button click/long-press
            """
            now = time.ticks_ms()
            if time.ticks_diff(now, self.last_interaction_time) <= SCREENSAVER_TIMEOUT_MS:
                if time.ticks_diff(now, b2.last_pressed()) > LONG_PRESS_MS:
                    # long press
                    # change between the main & sub menus
                    self.main_menu.on_long_press()
                else:
                    # short press
                    self.main_menu.on_click()
                    self.save()
            
            self.last_interaction_time = now
            
        
    def load(self):
        """Load parameters from persistent storage and apply them
        """
        state = self.load_state_json()
        
        channel_cfgs = state.get("channels", [])
        for i in range(len(channel_cfgs)):
            self.channels[i].load_settings(channel_cfgs[i])
            
        clock_cfg = state.get("clock", None)
        if clock_cfg:
            self.clock.load_settings(clock_cfg)
            
        cv_cfg = state.get("ain", None)
        if cv_cfg:
            self.cv_in.load_settings(cv_cfg)
        
    def save(self):
        """Save current settings to the persistent storage
        """
        state = {
            "clock": self.clock.to_dict(),
            "channels": [],
            "ain": self.cv_in.to_dict()
        }
        for i in range(len(self.channels)):
            state["channels"].append(self.channels[i].to_dict())
        
        self.save_state_json(state)
        
    @classmethod
    def display_name(cls):
        return "Pam's Workout"
        
    def main(self):
        self.load()
        
        while True:
            now = time.ticks_ms()
            
            self.cv_in.read_and_apply()
            
            if time.ticks_diff(now, self.last_interaction_time) > BLANK_TIMEOUT_MS:
                self.screensaver.draw_blank()
            elif time.ticks_diff(now, self.last_interaction_time) > SCREENSAVER_TIMEOUT_MS:
                self.screensaver.draw()
            else:
                self.main_menu.draw()
    
if __name__=="__main__":
    PamsWorkout().main()
