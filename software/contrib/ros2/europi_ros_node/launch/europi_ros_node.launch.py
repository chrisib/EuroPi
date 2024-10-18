#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions.declare_launch_argument import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    tty = LaunchConfiguration('tty')

    arg_tty = DeclareLaunchArgument(
        'tty',
        default_value='/dev/ttyACM0'
    )

    europi_node = Node(
        package='europi_ros_node',
        executable='europi_ros_node',
        name='europi_ros_node',
        parameters=[
            {'tty': tty},
        ]
    )

    ld = LaunchDescription()
    ld.add_action(arg_tty)
    ld.add_action(pose_node)

    return ld
