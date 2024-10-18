# ROS 2 For EuroPi

This is a highly-experimental script that uses the Raspberry Pi Pico's USB interface as a serial I/O channel
for communicating with a ROS 2 (Robot Operating System) node running on an external computer.

To make use of this program you will need
- a breakout cable for the Raspberry Pi Pico's USB connector
- a computer with ROS 2 Jazzy (or Humble) installed on it
- a USB cable long enough to connect your EuroPi's Raspberry Pi Pico to your computer

## What is ROS?

ROS, the Robot Operating System, is an open-source framework for developing robotics applications. It is designed
to allow processes ("nodes") to run on multiple computers simultaneously, providing:
- topics (a sub/pub model, using pre-defined message formats)
- services (requests to a node to perform some process & return a result)
- actions (requests to a node to perform an ongoing process, provide feedback, and the result when the process is
  complete)

This particular implementation does not run any ROS-specific code on the Raspberry Pi Pico itself, instead using
the Pico as a simple serial device. A ROS node running on the computer connected to the Pico's USB port provides
the ROS topics and services needed to control the module.

## ROS Interface

The `europi_ros` node provides the following topics:
- `cv1`-`cv6` (`europi_ros_msgs/msg/AnaloguePin`) -- the current state of all six CV outputs
- `k1`, `k2` (`europi_ros_msgs/msg/AnaloguePin`) -- the current state of the two knobs
- `ain` (`europi_ros_msgs/msg/AnaloguePin`) -- the current state of the analogue CV input
- `b1`, `b2` (`europi_ros_msgs/msg/DigitalPin`) -- the current state of the two buttons
- `din` (`europi_ros_msgs/msg/DigitalPin`) -- the current state of the digital CV in

Pin states are published at a fixed-rate and should be considered best-effort.

The following services are avaiable to control the module:
- `set_cv` (`europi_ros_msgs/srv/SetOutput`) -- set the desired voltage on one or more of the CV outputs
- `clear_screen` (`std_srvs/srv/Trigger`) -- clear the display
- `set_text` (`europi_ros_msgs/srv/SetText`) -- put up to 3 lines of text on the screen

## Building the local ROS packages

The `europi_ros` and `europi_ros_msgs` packages, located in the [`ros2`](./ros2/) directory should be copied into a
Colcon workspace.  These packages have been developed & tested for ROS 2 Jazzy (running on Ubuntu 24.04), but should
be compatible with ROS 2 Humble and Iron as well.

To build the packages you will need to [install ROS](https://docs.ros.org/en/jazzy/Installation.html), including
the necessary [development packages](https://docs.ros.org/en/jazzy/Installation/Alternatives/Ubuntu-Development-Setup.html#install-development-tools)

To build the packages, run the following commands:

```bash
git clone https://https://github.com/Allen-Synthesis/EuroPi.git europi
mkdir -p colcon_ws/src
mv europi/software/contrib/ros2/* colcon_ws/src
cd colcon_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build
```

## Running the ROS Node

Start the `ros2` script on your EuroPi module first, and connect the Raspberry Pi Pico's USB port to your computer.
Then run
```bash
source colcon_ws/install/setup.bash
ros2 launch europi_ros europi_ros_node.launch.py tty:=/dev/ttyACM0
```
(replacing `/dev/ttyACM0` with the TTY USB device corresponding to your EuroPi's Raspberry Pi Pico)

## Thonny and Serial I/O Over USB

While the script running on the Raspberry Pi Pico will work while Thonny is running, it will not allow you to
control the module in any meaningful way. This is because Thonny's terminal interface will clobber the serial
connection needed for communication between the Pico and the ROS node running on the computer.

It is best to make sure Thonny is closed while using this script.

The actual serial I/O implemented by the script running on the Raspberry Pi Pico is fairly primitive, and can
be used to implement other arbitrary external controls if desired. Data sent from the Pico is JSON encoded
and `print`ed. The module then waits for the serial client to acknowledge receipt by sending a message ending in a
`\n` (newline) character. JSON-encoded commands can be sent prior to the newline.

Any commands received from the serial client are processed, and the results are included in the next message sent
from the Pico to the serial client.

This back-and-forth passing of JSON-encoded text continues indefinitely.

Upon connection, the serial client shall send a newline-terminated string to initiate communication with the Pico.

## Encoding Commands for Serial I/O

ROS 2 services are encoded as simplified JSON objects with the following fields:
- `type`: an integer indicating the command type (see below)
- `cv`: 0-5 indicating which CV output is to be set by the `set_cv` command
- `data`: the data required by the command
    - text to display for the `set_text` command
    - voltage to apply to the CV output for the `set_cv` command

| Service        | Type integer | Example
|----------------|--------------|--------------------------------------|
| `clear_screen` | 0            | `{"type": 0}`                        |
| `set_text`     | 1            | `{"type": 1, "data": "Hello World"}` |
| `set_cv`       | 2            | `{"type": 2, "data": 5.0, "cv": 0}`   |

Multiple commands may be sent in a JSON array. If a single command is to be sent, it must be wrapped in an array.

Valid examples:
```json
[{"type": 0}]
[{"type": 1, "data": "HLH"}, {"type": 2, "data": 5.0, "cv": 0}, {"type": 2, "data": 0.0, "cv": 1}, {"type": 2, "data": 5.0, "cv": 2}]
```

Invalid examples:
```
# No array wrapping
{"type": 1, "data": "Hello World"}

# Invalid JSON keys (missing "")
[{type: 1, data: "Hello World"}]

# newlines included: this will cause synchronization problems and MUST be avoided!
{
    {"type": 1, "data": "HLH"},
    {"type": 2, "data": 5.0, "cv": 0},
    {"type": 2, "data": 0.0, "cv": 1},
    {"type": 2, "data": 5.0, "cv": 2}
}
```
