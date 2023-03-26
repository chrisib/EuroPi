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
    
    "Nat Maj"   : Quantizer([True,  False, True,  False, True,  True,  False, True,  False, True,  False, True]),
    "Har Maj"   : Quantizer([True,  False, True,  False, True,  True,  False, True,  True,  False, True,  False]),
    
    "Nat Min"   : Quantizer([True,  False, True,  True,  False, True,  False, True,  True,  False, True,  False]),
    "Har Min"   : Quantizer([True,  False, True,  True,  False, True,  False, True,  True,  False, False, True]),
    
    "Whole"     : Quantizer([True,  False, True,  False, True,  False, True,  False, True,  False, True,  False])
    
    # TODO: any additional scales?
    # maybe 1-3-5 or 1-3-5-b7 ?
    # Or some jazz scales?
}

QUANTIZERS = [
    "None",
    "Chromatic",
    "Nat Maj",
    "Har Maj",
    "Nat Min",
    "Har Min",
    "Whole"
]

## How many ms does a button need to be held to qualify as a long press?
LONG_PRESS_MS = 500

CLOCK_MODS = [
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
    "/16",
    "/24",
    "/32"
]

CLOCK_RATIOS = {
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
    "/16" : 1/16.0,
    "/24" : 1/24.0,
    "/32" : 1/32.0
}

WAVE_SQUARE = 0
WAVE_RANDOM = 1
WAVE_SHAPES = [
    "Square",
    "Random"
]
WAVE_SHAPE_IDS= {
    "Square": WAVE_SQUARE,
    "Random": WAVE_RANDOM
}

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
    
    def __init__(self, cv_out):
        """Create a new output to control a single cv output
        
        @param cv_out: One of the six output pins
        """
        self.cv_out = cv_out
        
        ## What quantization are we using?
        #
        #  See contrib.pams.QSCALES
        self.quantizer_key = "None"
        self.quantizer = None
        
        ## The clock modifier for this channel
        #
        #  - 1.0 is the same as the main clock's BPM
        #  - <1.0 will tick slower than the BPM (e.g. 0.5 will tick once every 2 beats)
        #  - >1.0 will tick faster than the BPM (e.g. 3.0 will tick 3 times per beat)
        self.clock_mod = 1.0
        self.clock_mod_txt = "x1"
        
        ## What shape of wave are we generating?
        #
        #  For now, stick to square waves for triggers & gates
        self.wave = WAVE_SQUARE
        self.wave_shape_txt = "Wave"
        
        ## The amplitude of the output as a [0, 100] percentage
        self.amplitude = 50   # default to 5V gates
        
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
            "clock_mod" : self.clock_mod_txt,
            "e_step"    : self.e_steps,
            "e_trigs"   : self.e_trigs,
            "e_rot"     : self.e_rot,
            "skip"      : self.skip_prob,
            "wave"      : self.wave_shape_txt,
            "amplitude" : self.amplitude,
            "quant"     : self.quantizer_key
        }
    
    def load_settings(self, settings):
        """Apply the settings loaded from storage

        @param settings  A dict with the same keys as the one returned by to_dict()
        """
        
        self.clock_mod_txt = settings["clock_mod"]
        self.clock_mod = CLOCK_RATIOS[self.clock_mod_txt]
        self.e_step = settings["e_step"]
        self.e_trigs = settings["e_trigs"]
        self.e_rot = settings["e_rot"]
        self.skip = settings["skip"]
        self.wave_shape_txt = settings["wave"]
        self.wave = WAVE_SHAPE_IDS[self.wave_shape_txt]
        self.amplitude = settings["amplitude"]
        self.quantizer_key = settings["quant"]
        
        if self.quantizer_key in QSCALES.keys():
            self.quantizer = QSCALES[self.quantizer_key]
        else:
            self.quantizer = None
        
        self.recalculate_pattern()
        
    def apply_changes(self):
        """If we've changed anything via the menu, recalculate the necessary changes
        """
        super().apply_changes()
        
        # look up the numerical clock mod from the text
        self.clock_mod = CLOCK_RATIOS[self.clock_mod_txt]
        
        # make sure the euclidean limits are valid
        # the rotation & number of triggers must always be <= the number of steps!
        if self.e_rot > self.e_steps:
            self.e_rot = 0
        if self.e_trigs > self.e_steps:
            self.e_trigs = self.e_steps
            
        # Choose the correct quantizer
        if self.quantizer_key in QSCALES.keys():
            self.quantizer = QSCALES[self.quantizer_key]
        else:
            self.quantizer = None
        
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
    def __init__(self, title, options, dest_obj, dest_prop):
        """Create a setting chooser for a given item
        
        We use dest_obj.__setattr__(dest_prop, X) to set the new value. If this was C or C++
        we could use a pointer, but that's not an option here so we're using a Pythony
        work-around.

        @param title  The title of this menu item
        @param available_values  A list of available options to choose from
        @param dest_obj  The object whose property we're editing, e.g. a MasterClock instance
        @param dest_prop  The name of the attribute of dest_obj to edit.
        """
        self.title = title
        self.options = options
        self.dest_obj = None
        self.dest_prop = None
        
        self.is_writable = False
        
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
        

class Menu:
    """Generic menu object
    """
    def __init__(self):
        self.items = []
        
        self.active_item = None
        
    def draw(self):
        if self.active_item:
            self.active_item.draw()
        else:
            oled.fill(0)
            oled.show()
            
    def on_long_press():
        if self.active_item:
            self.active_item.on_long_press()

class TopLevelMenu(Menu):
    def __init__(self, script):
        """Create the top-level menu for the application

        @param script  The PamsWorkout object the meny belongs to
        """
        Menu.__init__(self)
        
        self.pams_workout = script
        
        self.submenus = [
            ClockMenu(self, script.clock)
        ]
        for i in range(len(script.channels)):
            self.submenus.append(ChannelMenu(self, script.channels[i]))
        
        self.items = [
            SettingChooser("BPM", list(range(MasterClock.MIN_BPM, MasterClock.MAX_BPM+1)), script.clock, "bpm"),
            SettingChooser("CV1 Mod", CLOCK_MODS, script.channels[0], "clock_mod_txt"),
            SettingChooser("CV2 Mod", CLOCK_MODS, script.channels[1], "clock_mod_txt"),
            SettingChooser("CV3 Mod", CLOCK_MODS, script.channels[2], "clock_mod_txt"),
            SettingChooser("CV4 Mod", CLOCK_MODS, script.channels[3], "clock_mod_txt"),
            SettingChooser("CV5 Mod", CLOCK_MODS, script.channels[4], "clock_mod_txt"),
            SettingChooser("CV6 Mod", CLOCK_MODS, script.channels[5], "clock_mod_txt")
        ]
        
        self.active_item = k1.choice(self.items)
        
class Submenu(Menu):
    def __init__(self, parent):
        Menu.__init__(self)
        self.parent = parent
        self.parent.child = self
        
class ClockMenu(Submenu):
    """Submenu for the main clock
    """
    def __init__(self, parent, clock):
        Submenu.__init__(self, parent)
        self.clock = clock
        
        self.items.append(
            SettingChooser("Reset", [True, False], clock, "reset_on_start")
        )
    
class ChannelMenu(Submenu):
    """Submenu for a single CV channel
    """
    def __init__(self, parent, channel):
        Submenu.__init__(self, parent)
        self.channel = channel
        
        self.items.append(SettingChooser("Wave", WAVE_SHAPES, channel, "wave_shape_txt"))
        self.items.append(SettingChooser("Amplitude", list(range(0, 101)), channel, "amplitude"))
        self.items.append(SettingChooser("Skip %", list(range(0, 101)), channel, "skip_prob"))
        self.items.append(SettingChooser("Eucl. Steps", list(range(0, 33)), channel, "e_steps"))
        self.items.append(SettingChooser("Eucl. Pulses", list(range(0, 33)), channel, "e_trigs"))
        self.items.append(SettingChooser("Eucl. Rot.", list(range(0, 33)), channel, "e_rot"))
        self.items.append(SettingChooser("Quant.", QUANTIZERS, channel, "quantizer_key"))

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
        
        self.menu = TopLevelMenu(self)
        
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