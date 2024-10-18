#!/usr/bin/env python3
"""
Dumb serial I/O implementation to allow external control over the module

This is intended for use with the europi_ros ROS node, but can be used for other arbitrary serial-based
control systems
"""

from europi import *
from europi_script import EuroPiScript

import json
import machine
import time
import _thread

class Command:
    """
    A command to process from the serial client

    .cmd_type indicates the type of command to run
    .cv is the CV output to assign voltage to (e.g. europi.cv1)
    .data is either the text to display on screen OR the voltage to apply to the CV
    """
    TYPE_NONE = -1

    TYPE_CLEAR_SCREEN = 0
    TYPE_SET_TEXT = 1

    TYPE_SET_CV = 2

    def __init__(self, cmd_type=-1, cv=None, data=None):
        self.cmd_type = cmd_type

        self.cv = cv
        self.data = data

    def process(self):
        """Execute the command
        """
        if self.cmd_type == self.TYPE_CLEAR_SCREEN:
            oled.fill(0)
            oled.show()

        elif self.cmd_type == self.TYPE_SET_TEXT:
            oled.centre_text(self.data)

        elif self.cmd_type == self.TYPE_SET_CV:
            self.cv.voltage(self.data)

class Ros2SerialInterface(EuroPiScript):
    def __init__(self):
        super().__init__()

        # the LED on the Pico; used as a debugging heartbeat
        # this may be removed later
        self.heartbeat = machine.Pin("LED", machine.Pin.OUT)

        self.din_high = False
        self.b1_high = False
        self.b2_high = False

        @b1.handler
        def b1_press():
            self.b1_high = True

        @b1.handler_falling
        def b1_release():
            self.b1_high = False

        @b2.handler
        def b2_press():
            self.b2_high = True

        @b2.handler_falling
        def b2_release():
            self.b2_high = False

        @din.handler
        def din_rise():
            self.din_high = True

        @din.handler_falling
        def din_rise():
            self.din_high = False

    def parse_commands(self, jstring):
        """Process the JSON-encoded data from the client and return it as an array of commands

        @param jstring  The raw JSON string from the client
        @return  An array of commands to execute
        """
        commands = []
        try:
            jdict = json.loads(jstring)

            for cmd_dict in jdict:
                if cmd_dict['type'] == Command.TYPE_CLEAR_SCREEN:
                    cmd = Command(cmd_type=cmd_dict['type'])
                elif cmd_dict['type'] == Command.TYPE_SET_TEXT:
                    cmd = Command(cmd_type=cmd_dict['type'], data=cmd_dict['data'])
                elif cmd_dict['type'] == Command.TYPE_SET_CV:
                    cmd = Command(cmd_type=cmd_dict['type'], data=cmd_dict['data'], cv=cvs[cmd_dict['cv']])

                commands.append(cmd)
        except ValueError:
            # invalid JSON
            commands = []
        except KeyError:
            # missing key; just skip the command
            pass
        return commands

    def main(self):
        while True:
            # Read from the serial port
            # If there are any service calls, they'll be encoded here
            external_cmd_json = input()

            commands = self.parse_commands(external_cmd_json)
            for cmd in commands:
                cmd.process()

            ain_percent = ain.percent()
            ain_volts = ain_percent * europi_config.MAX_INPUT_VOLTAGE
            k1_percent = k1.percent()
            k2_percent = k2.percent()

            cv1_volts = cv1.voltage()
            cv1_percent = cv1_volts / europi_config.MAX_OUTPUT_VOLTAGE

            cv2_volts = cv2.voltage()
            cv2_percent = cv2_volts / europi_config.MAX_OUTPUT_VOLTAGE

            cv3_volts = cv3.voltage()
            cv3_percent = cv3_volts / europi_config.MAX_OUTPUT_VOLTAGE

            cv4_volts = cv4.voltage()
            cv4_percent = cv4_volts / europi_config.MAX_OUTPUT_VOLTAGE

            cv5_volts = cv5.voltage()
            cv5_percent = cv5_volts / europi_config.MAX_OUTPUT_VOLTAGE

            cv6_volts = cv6.voltage()
            cv6_percent = cv6_volts / europi_config.MAX_OUTPUT_VOLTAGE

            state = [
                # Digital inputs first
                self.din_high,
                self.b1_high,
                self.b2_high,

                # Analogue inputs in volts/percent pairs
                # Knobs are always 0V and only have a percentage
                ain_volts,
                ain_percent,
                0.0,
                k1_percent,
                0.0,
                k2_percent,

                # Analogue outputs in volts/percent pairs
                cv1_volts,
                cv1_percent,
                cv2_volts,
                cv2_percent,
                cv3_volts,
                cv3_percent,
                cv4_volts,
                cv4_percent,
                cv5_volts,
                cv5_percent,
                cv6_volts,
                cv6_percent,
            ]

            # Dump the state back to serial port
            state = json.dumps(state)
            print(state)  # automatically appends the expected newline

if __name__ == '__main__':
    Ros2SerialInterface().main()
