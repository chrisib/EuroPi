#!/usr/bin/env python3
"""
ROS 2 interface node for EuroPi

Communicates with the Raspberry Pi Pico via serial-over-USB in a JSON-based, synchronous fashion
"""

import rclpy
from rclpy.node import Node

import serial
from threading import Lock

from europi_ros_msgs.msg import *
from europi_ros_msgs.srv import *
from std_srvs.srv import Trigger


class Command:
    TYPE_NONE = -1

    TYPE_CLEAR_SCREEN = 0
    TYPE_SET_TEXT = 1

    TYPE_SET_CV = 2


CvOuts = {
    AnaloguePin.CV1: 0,
    AnaloguePin.CV2: 1,
    AnaloguePin.CV3: 2,
    AnaloguePin.CV4: 3,
    AnaloguePin.CV5: 4,
    AnaloguePin.CV6: 5,
}


class EuroPiRosNode(Node):
    def __init__(self):
        super().__init__('europi_ros_node')
        self.declare_parameter('tty', '/dev/ttyACM0')
        self.tty = serial.Serial(sef.get_parameter('tty'))

        self.command_lock = Lock()
        self.command_queue = []

        self.clear_srv = self.create_service(Trigger, 'clear_screen', self.clear_screen_cb)
        self.text_srv = self.create_service(SetText, 'set_text', self.set_text_cb)
        self.set_cv = self.create_service(SetCV, 'set_cv', self.set_cv_cb)
        self.sync_timer = self.create_timer(10, self.serial_sync)

        self.din_pub = self.create_publisher('din', DigitalPin, 1)
        self.b1_pub = self.create_publisher('b1', DigitalPin, 1)
        self.b2_pub = self.create_publisher('b2', DigitalPin, 1)

        self.ain_pub = self.create_publisher('ain', AnaloguePin, 1)
        self.k1_pub = self.create_publisher('k1', AnaloguePin, 1)
        self.k2_pub = self.create_publisher('k2', AnaloguePin, 1)
        self.cv1_pub = self.create_publisher('cv1', AnaloguePin, 1)
        self.cv2_pub = self.create_publisher('cv2', AnaloguePin, 1)
        self.cv3_pub = self.create_publisher('cv3', AnaloguePin, 1)
        self.cv4_pub = self.create_publisher('cv4', AnaloguePin, 1)
        self.cv5_pub = self.create_publisher('cv5', AnaloguePin, 1)
        self.cv6_pub = self.create_publisher('cv6', AnaloguePin, 1)

    def close_serial(self):
        self.tty.close()

    def clear_screen_cb(self, req, resp):
        """Callback for the clear-screen service"""
        cmd = {
            'cmd_type': Command.TYPE_CLEAR_SCREEN,
        }
        self.command_lock.acquire()
        self.command_queue.append(cmd)
        self.command_lock.release()
        return resp

    def set_text_cb(self, req, resp):
        """Callback for the set-text service"""
        cmd = {
            'cmd_type': Command.TYPE_SET_TEXT,
            'data': req.text,
        }
        self.command_lock.acquire()
        self.command_queue.append(cmd)
        self.command_lock.release()
        return resp

    def set_cv_cb(self, req, resp):
        """Callback for the set-cv service"""
        commands = []
        for pin_state in req.cv_states:
            if pin_state.name in CvOuts:
                cmd = {
                    'cmd_type': Command.TYPE_SET_CV,
                    'data': pin_state.voltage,
                    'cv': CvOuts[pin_state.name]
                }
                commands.append(cmd)
        self.command_lock.acquire()
        for cmd in commands:
            self.command_queue.append(cmd)
        self.command_lock.release()
        return resp

    def serial_sync(self):
        self.command_lock.acquire()
        if len(self.command_queue) > 0:
            cmd_json = json.dumps(self.command_queue)
        else:
            cmd_json = '[]'
        self.command_queue = []
        self.command_lock.release()

        # write to the serial port
        self.tty.write(f'{cmd_json.encode("UTF-8")}\n')

        # read the serial state back
        status_json = self.tty.readline()
        status = json.loads(status_json)

        # publish the output on our topics
        d = DigitalPin()
        a = AnaloguePin()

        d.name = 'din'
        d.high = status[0]
        self.din_pub.publish(d)

        d.name = 'b1'
        d.high = status[1]
        self.b1_pub.publish(d)

        d.name = 'b2'
        d.high = status[2]
        self.b2_pub.publish(d)

        a.name = 'ain'
        a.voltage = status[3]
        a.percent = status[4]
        self.ain_pub.publish(a)

        a.name = 'k1'
        a.voltage = status[5]
        a.percent = status[6]
        self.k1_pub.publish(a)

        a.name = 'k2'
        a.voltage = status[7]
        a.percent = status[8]
        self.k2_pub.publish(a)

        a.name = 'cv1'
        a.voltage = status[9]
        a.percent = status[10]
        self.cv1_pub.publish(a)

        a.name = 'cv2'
        a.voltage = status[11]
        a.percent = status[12]
        self.cv2_pub.publish(a)

        a.name = 'cv3'
        a.voltage = status[13]
        a.percent = status[14]
        self.cv3_pub.publish(a)

        a.name = 'cv4'
        a.voltage = status[15]
        a.percent = status[16]
        self.cv4_pub.publish(a)

        a.name = 'cv5'
        a.voltage = status[17]
        a.percent = status[18]
        self.cv5_pub.publish(a)

        a.name = 'cv6'
        a.voltage = status[19]
        a.percent = status[20]
        self.cv6_pub.publish(a)


def main(args=None):
    rclpy.init(args=args)
    node = EuroPiRosNode()
    rclpy.spin(node)
    node.close_serial()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
