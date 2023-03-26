#!/usr/bin/env python3
"""A EuroPi clone of ALM's Pamela's NEW Workout

The module has a master clock rate, with each channel outputting
a multiple/division of that rate.

Each channel supports the following options:
- clock multiplier/divider
- wave shape
    - square (default)
    - sine
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
from contrib.quantizer import Quantizer

from machine import Timer

import time
import random

SELECT_OPTION_Y = 16
HALF_CHAR_WIDTH = int(CHAR_WIDTH / 2)

## How many ms does a button need to be held to qualify as a long press?
LONG_PRESS_MS = 500

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

## Sorted list of names for the quantizers to display
QUANTIZER_LABELS = [
    "None",
    "Chromatic",
    "Nat Maj",
    "Har Maj",
    "Nat Min",
    "Har Min",
    "Whole"
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
    "/16" : 1/16.0,
    "/24" : 1/24.0,
    "/32" : 1/32.0
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
    "/16",
    "/24",
    "/32"
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
WAVE_SHAPES = [
    WAVE_SQUARE,
    WAVE_TRIANGLE,
    WAVE_SIN,
    WAVE_RANDOM,
    WAVE_RESET
]


WAVE_SHAPE_LABELS = [
    "Sq.",
    "Tri.",
    "Sin",
    "Rnd",
    "Rst"
]

## Sorted list of wave shapes to display
#
#  These are 12x12 bitmaps
WAVE_SHAPE_IMGS = [
    b'\xfe\x00\x82\x00\x82\x00\x82\x00\x82\x00\x82\x00\x82\x00\x82\x00\x82\x00\x82\x00\x82\x00\x83\xf0',
    b'\x06\x00\x06\x00\t\x00\t\x00\x10\x80\x10\x80 @ @@ @ \x80\x10\x80\x10',
    b'\x10\x00(\x00D\x00D\x00\x82\x00\x82\x00\x82\x10\x82\x10\x01\x10\x01\x10\x00\xa0\x00@',
    b'\x00\x00\x08\x00\x08\x00\x14\x00\x16\x80\x16\xa0\x11\xa0Q\xf0Pp`P@\x10\x80\x00',
    b'\x03\xf0\x02\x00\x02\x00\x02\x00\x02\x00\x02\x00\x02\x00\x02\x00\x02\x00\x02\x00\x02\x00\xfe\x00'
]

class MasterClock:
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
        self.__recalculate_ticks()
        
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
            
            # Fire a reset trigger on any channels that have the WAVE_RESET mode set
            # This trigger lasts 10ms
            for ch in self.channels:
                if ch.wave == WAVE_RESET:
                    ch.cv_out.voltage(MAX_OUTPUT_VOLTAGE * ch.amplitude / 100.0)
            time.sleep(10)
            for ch in self.channels:
                if ch.wave == WAVE_RESET:
                    ch.cv_out.voltage(0)
        
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

class PamsOutput:
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

class SettingChooser(MenuItem):
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
        
    def draw(self):
        """Draw the menu to the screen
        """
        
        oled.fill(0)
        oled.text(f"{self.title}", 0, 0)
        
        if self.is_writable:
            if self.validate_settings_fn:
                self.options = self.validate_settings_fn()
            
            # draw the selection in inverted text
            selected_item = k2.choice(self.options)
            choice_text = f"{selected_item}"
            text_width = len(choice_text)*CHAR_WIDTH
            
            oled.fill_rect(0, SELECT_OPTION_Y, text_width+3, CHAR_HEIGHT+4, 1)
            oled.text(choice_text, 1, SELECT_OPTION_Y+2, 0)
        else:
            # draw the selection in normal text
            choice_text = f"{self.dest_obj[self.dest_prop]}"
            oled.text(choice_text, 1, SELECT_OPTION_Y+2, 1)
        
        oled.show()
        
    def on_click(self):
        if self.is_writable:
            self.set_editable(False)
            selected_item = k2.choice(self.options)
        
            self.dest_obj[self.dest_prop] = selected_item
            self.dest_obj.apply_changes()
        else:
            self.set_editable(True)

class PamsMenu:
    def __init__(self, script):
        """Create the top-level menu for the application

        @param script  The PamsWorkout object the meny belongs to
        """
        
        self.pams_workout = script
        
        self.items = [
            SettingChooser("BPM", list(range(MasterClock.MIN_BPM, MasterClock.MAX_BPM+1)), script.clock, "bpm", self, [
                SettingChooser("Reset", [True, False], script.clock, "reset_on_start", self)
            ])
        ]
        for i in range(len(script.channels)):
            self.items.append(SettingChooser(f"CV{i+1}|Clk Mod", CLOCK_MODS, script.channels[i], "clock_mod_txt", [
                SettingChooser(f"CV{i+1}|Wave", WAVE_SHAPE_LABELS, script.channels[i], "wave_shape_txt", gfx=WAVE_SHAPE_IMGS),
                SettingChooser(f"CV{i+1}|Ampl.", list(range(101)), script.channels[i], "amplitude"),
                SettingChooser(f"CV{i+1}|Skip%", list(range(101)), script.channels[i], "skip_prob"),
                SettingChooser(f"CV{i+1}|ESteps", list(range(33)), script.channels[i], "e_steps"),
                SettingChooser(f"CV{i+1}|EPulses", list(range(33)), script.channels[i], "e_trigs",
                               validate_settings = lambda:list(range(script.channels[i].e_steps+1))),
                SettingChooser(f"CV{i+1}|ERot.", list(range(33)), script.channels[i], "e_rot",
                               validate_settings = lambda:list(range(script.channels[i].e_steps+1))),
                SettingChooser(f"CV{i+1}|Quant.", QUANTIZER_LABELS, script.channels[i], "quantizer_key")
            ]))
            
        self.active_items = self.items
        
    def on_long_press(self):
        # return the active item to the read-only state
        item = k1.choice(self.active_items)
        item.set_editable(False)
        
        # toggle between the two menu levels
        if self.active_items == self.items:
            self.active_items = k1.choice(self.items).submenu
        else:
            self.active_items = self.items
            
    def on_click(self):
        item = k1.choice(self.active_items)
        item.on_click()
            
    def draw(self):
        active_item = k1.choice(self.active_items)
        active_item.draw()

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
        
        ## The master top-level menu
        self.main_menu = PamsMenu(self)
        
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
                # change between the main & sub menus
                self.main_menu.on_long_press()
            else:
                # short press
                self.main_menu.on_click()
            
        
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
            self.main_menu.draw()
    
if __name__=="__main__":
    PamsWorkout().main()
