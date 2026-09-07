# Copyright 2026 Allen Synthesis
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Enables managing the bluetooth connection on the Pico W and Pico 2 W

Bluetooth settings are saved in ``config/ExperimentalConfig.json``

See https://docs.micropython.org/en/v1.29.0/ for details on bluetooth
implementation
"""

from micropython import const
import ubluetooth

from europi_log import *


# See https://docs.micropython.org/en/v1.29.0/
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTS_READ_REQUEST = const(4)
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_DESCRIPTOR_RESULT = const(13)
_IRQ_GATTC_DESCRIPTOR_DONE = const(14)
_IRQ_GATTC_READ_RESULT = const(15)
_IRQ_GATTC_READ_DONE = const(16)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)
_IRQ_GATTC_INDICATE = const(19)
_IRQ_GATTS_INDICATE_DONE = const(20)
_IRQ_MTU_EXCHANGED = const(21)
_IRQ_L2CAP_ACCEPT = const(22)
_IRQ_L2CAP_CONNECT = const(23)
_IRQ_L2CAP_DISCONNECT = const(24)
_IRQ_L2CAP_RECV = const(25)
_IRQ_L2CAP_SEND_READY = const(26)
_IRQ_CONNECTION_UPDATE = const(27)
_IRQ_ENCRYPTION_UPDATE = const(28)
_IRQ_GET_SECRET = const(29)
_IRQ_SET_SECRET = const(30)

_GATTS_NO_ERROR = const(0x00)
_GATTS_ERROR_READ_NOT_PERMITTED = const(0x02)
_GATTS_ERROR_WRITE_NOT_PERMITTED = const(0x03)
_GATTS_ERROR_INSUFFICIENT_AUTHENTICATION = const(0x05)
_GATTS_ERROR_INSUFFICIENT_AUTHORIZATION = const(0x08)
_GATTS_ERROR_INSUFFICIENT_ENCRYPTION = const(0x0f)

_PASSKEY_ACTION_NONE = const(0)
_PASSKEY_ACTION_INPUT = const(2)
_PASSKEY_ACTION_DISPLAY = const(3)
_PASSKEY_ACTION_NUMERIC_COMPARISON = const(4)

_IO_CAPABILITY_DISPLAY_ONLY = const(0)
_IO_CAPABILITY_DISPLAY_YESNO = const(1)
_IO_CAPABILITY_KEYBOARD_ONLY = const(2)
_IO_CAPABILITY_NO_INPUT_OUTPUT = const(3)
_IO_CAPABILITY_KEYBOARD_DISPLAY = const(4)


from experimental.experimental_config import load_experimental_config

class BluetoothConnection:
    """
    Wrapper class for managing bluetooth connections.

    Use self.ble to access the underlying bluetooth object to e.g. get/set parameters, query
    active status, etc...
    """
    def __init__(self):
        self.client_irq = lambda event, data : None
        self.ble = ubluetooth.BLE()

        ex_cfg = load_experimental_config()
        self.device_name = ex_cfg.BT_DEVICE_NAME

        log_info("Activating bluetooth...", "bt")
        self.ble.active(True)

        log_info("Bluetooth ({}) active\n  MAC: {}\n  mtu: {}\n  name: {}".format(
                    self.device_name,
                    self.ble.config("mac"),
                    self.ble.config("mtu"),
                    self.ble.config("gap_name")))

        self.ble.irq(self.irq)

    def handler(self, irq_handler):
        """
        Connect a handler function to the bluetooth IRQ.

        :param irq_handler: A function that will be called whenever the underlying bluetooth
                            object receives an event. The handler must accept 2 arguments:
                            event (integer code) and data (event-specific tuple of values)
        """
        log_info("Custom IRQ handler set", "bt")
        self.client_irq = irq_handler

    def irq(self, event, data):
        """
        The internal IRQ handler.

        This will call the client IRQ handler, if it has been assigned.

        :param event: The IRQ event code (integer).
        :param data:  The event-specific data (tuple).
        """
        if event == _IRQ_CENTRAL_CONNECT:
            log_info("Connection request {}".format(data))
        elif event == _IRQ_CENTRAL_DISCONNECT:
            log_info("Disconnected {}".format(data))
        elif event == _IRQ_GATTS_READ_REQUEST:
            log_info("Read request {}", data)
        else:
            log_debug("Received event {}: {}".format(event, data), "bt")

        self.client_irq(event, data)

    def advertise(self, interval_us):
        """
        Begin advertising.

        :param interval_us: The advertise interval in us.
        """
        name = bytes(self.device_name, "UTF-8")
        self.ble.gap_advertise(interval_us,
                               adv_data = b'\x02\x01\x05' + bytearray((len(name) + 1, 0x09)) + name,
                               resp_data = b'\x11\x07\x00\xC7\xC4\x4E\xE3\x6C\x51\xA7\x33\x4B\xE8\xEd\x5A\x0E\xB8\x03')
