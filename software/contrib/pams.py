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

from machine import Timer

import time
import random

SELECT_OPTION_Y = 16
HALF_CHAR_WIDTH = int(CHAR_WIDTH / 2)

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

## How many ms does a button need to be held to qualify as a long press?
LONG_PRESS_MS = 500

class MenuEditableObject:
    """An object that can be dynamically edited via the UI menu
    """
    def apply_changes(self):
        """Reimplement this in every inherited class
        """
        pass

class MasterClock(MenuEditableObject):
    """The main clock that ticks and runs the outputs
    """
    
    ## The clock actually runs faster than its maximum BPM to allow
    #  clock divisions to work nicely
    #
    #  Use 48 internal clock pulses per quarter note. This is slow enough
    #  that we won't choke the CPU with interrupts, but smooth enough that we
    #  should be able to approximate complex waves.  Must be a multiple of
    #  3 to properly support triplets
    PPQN = 48
    
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
        self.__recalculate_ticks()
        
    def to_dict(self):
        """Return a dict with the clock's parameters
        """
        return {
            "bpm": self.bpm
            "reset_on_start": self.reset_on_start
        }
    
    def load_settings(self, settings):
        """Apply settings loaded from the configuration file

        @param settings  A dict containing the same fields as to_dict(self)
        """
        self.bpm = settings["bpm"]
        self.reset_on_start = settings["reset_on_start"]
        self.__recalculate_ticks()
        
    def on_tick(self, timer):
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
            
            self.timer.init(period=self.ms_per_tick, mode=Timer.PERIODIC, callback=self.on_tick)
        
    def stop(self):
        """Stop the timer
        """
        if self.is_running:
            self.is_running = False
            self.timer.deinit()
        
    def apply_changes(self):
        """If we've changed anything via the menu, recalculate the necessary changes
        """
        super().apply_changes()
        self.__recalcualte_ticks()
        
    def __recalculate_ticks(self):
        """Recalculate the number of ms per tick

        If the timer is currently running deinitialize it and reset it to use the correct BPM
        """
        self.ms_per_beat = self.bpm / 60.0 * 1000.0
        self.ms_per_tick = self.ms_per_beat / self.PPQN
        
        if self.is_running:
            self.timer.deinit()
            self.timer.init(period=self.ms_per_tick, mode=Timer.PERIODIC, callback=self.on_tick)
        
    def change_bpm(self, new_bpm):
        self.bpm = bpm
        self.__recalculate_ticks()

class PamsOutput(MenuEditableObject):
    """Controls a single output jack
    """
    
    WAVE_SQUARE = 0
    WAVE_RANDOM = 1
    
    def __init__(self, cv_out):
        """Create a new output to control a single cv output
        
        @param cv_out: One of the six output pins
        """
        self.cv_out = cv_out
        
        ## What quantization are we using?
        #
        #  See contrib.pams.QSCALES
        #
        #  Disabled when negative
        self.quantizer_index = -1
        
        ## The clock modifier for this channel
        #
        #  - 1.0 is the same as the main clock's BPM
        #  - <1.0 will tick slower than the BPM (e.g. 0.5 will tick once every 2 beats)
        #  - >1.0 will tick faster than the BPM (e.g. 3.0 will tick 3 times per beat)
        self.clock_mod = 1.0
        
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
        
        self.__recalculate_pattern()
        
    def to_dict(self):
        """Return a dictionary with all the configurable settings to write to disk
        """
        return {
            "clock_mod" : self.clock_mod,
            "e_step"    : self.e_steps,
            "e_trigs"   : self.e_trigs,
            "e_rot"     : self.e_rot,
            "skip"      : self.skip_prob,
            "wave"      : self.wave,
            "quant"     : self.quantizer_index
        }
    
    def load_settings(self, settings):
        """Apply the settings loaded from storage

        @param settings  A dict with the same keys as the one returned by to_dict()
        """
        
        self.clock_mod = settings["clock_mod"]
        self.e_step = settings["e_step"]
        self.e_trigs = settings["e_trigs"]
        self.e_rot = settings["e_rot"]
        self.skip = settings["skip"]
        self.wave = settings["wave"]
        self.quantizer_index = settings["quant"]
        
        self.recalculate_pattern()
        
    def apply_changes(self):
        """If we've changed anything via the menu, recalculate the necessary changes
        """
        super().apply_changes()
        self.__recalculate_pattern()
        
    def __recalculate_pattern(self):
        """Recalculate the internal trigger pattern for this channel

        Every time we tick we just set the output level according to the pre-computed
        pattern
        """
        pass
    
    def reset(self):
        """Reset the current output to the beginning
        """
        pass
    
    def tick(self):
        """Advance the current pattern one tick
        """
        pass

class SettingChooser:
    """Menu UI element for displaying an option and the choices associated with it
    """
    def __init__(self):
        self.title = ""
        self.options = []
        self.value = None
        self.dest_obj = None
        self.dest_prop = None
        
        self.is_writable = False
        
    def reconfigure(self, title, current_value, available_values, dest_obj, dest_prop):
        """Reconfigure the UI to display a particular setting

        We use dest_obj.__setattr__(dest_prop, X) to set the new value. If this was C or C++
        we could use a pointer, but that's not an option here so we're using a Pythony
        work-around.

        @param title  The title of this menu item
        @param current_value  The current value of the option
        @param available_values  A list of available options to choose from
        @param dest_obj  The object whose property we're editing, e.g. a MasterClock instance
        @param dest_prop  The name of the attribute of dest_obj to edit.
        """
        
        self.title = title
        self.value = current_value
        self.options = available_values
        self.dest_obj = dest_obj
        self.dest_prop = dest_prop
        
    def set_editable(self, can_edit):
        """Set whether or not we can write to this setting
        
        @param can_edit  If True, we can write a new value
        """
        
        self.is_writable = can_edit
        
    def draw(self):
        """Draw the menu to the screen
        """
        
        oled.fill(0)
        oled.text(f"{self.title}", 0, 0)
        
        if self.is_writable:
            # draw the selection in inverted text
            selected_item = k2.choice(self.options)
            choice_text = f"{selected_item}"
            text_width = len(choice_text)*CHAR_WIDTH
            
            oled.fill_rect(0, SELECT_OPTION_Y, text_width+3, CHAR_HEIGHT+4, 1)
            oled.text(choice_text, 1, SELECT_OPTION_Y+2, 0)
        else:
            # draw the selection in normal text
            choice_text = f"{self.dest_obj.__getattr__(self.dest_prop)}"
            oled.text(choice_text, 1, SELECT_OPTION_Y+2, 1)
        
        oled.show()
        
    def on_click(self):
        self.set_editable(False)
        selected_item = k2.choice(self.options)
        
        self.dest_obj.__setattr(self.dest_prop, selected_item)
        self.dest_obj.apply_changes()
        

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
        
        @b1.handler
        def on_b1_press():
            """Handler for pressing button 1

            Button 1 starts/stops the master clock
            """
            if self.clock.is_running:
                self.clock.stop()
            else:
                self.clock.start()
            
        @b2.handler_falling
        def on_b2_release():
            """Handler for releasing button 2

            Handle long vs short presses differently

            Button 2 is used to cycle between screens
            """
            now = time.ticks_ms()
            if time.ticks_diff(now, b2.last_pressed()) > LONG_PRESS_MS:
                # long press
                # TODO
                pass
            else:
                # short press
                # TODO
                pass
            
        
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
        
    def save(self):
        """Save current settings to the persistent storage
        """
        state = {
            "clock": self.clock.to_dict(),
            "channels": []
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
            pass
    
if __name__=="__main__":
    PamsWorkout().main()