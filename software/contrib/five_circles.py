#!/usr/bin/env python3
"""Five Circles

Quantized sequencer that generates outputs based on the motion of 5 connected circles.

@author   Chris Iverach-Brereton
@license  Apache v2.0
@year     2024
"""

from europi import *
from europi_script import EuroPiScript

from experimental.quantizer import CommonScales, NoteLetters, VOLTS_PER_OCTAVE, SEMITONE_LABELS

from math import cos, sin, atan2, pi, sqrt, degrees
import random
import time


# The semitone offsets equivalent to the root note of the circle of fifths
# See: https://en.wikipedia.org/wiki/Circle_of_fifths
circle_of_fifths = [
    NoteLetters.C,
    NoteLetters.G,
    NoteLetters.D,
    NoteLetters.A,
    NoteLetters.E,
    NoteLetters.B,
    NoteLetters.G_flat,
    NoteLetters.D_flat,
    NoteLetters.A_flat,
    NoteLetters.E_flat,
    NoteLetters.B_flat,
    NoteLetters.F
]

class Point:
    """A 2D point on the plane
    """

    def __init__(self, x=0, y=0):
        """Create a point at the position (x, y)

        @param x  The x coordinate (cartesean)
        @param y  The y coordinate (cartesean)
        """
        self.x = x
        self.y = y

    def distance_from(self, p):
        return sqrt((self.x - p.x)**2 + (self.y - p.y)**2)

class MovingCircle:
    """A circle rotating about its center
    """

    def __init__(self, center, radius, velocity, initial_angle):
        """Create a circle with the given center and radius

        @param center    A Point representing the center of this circle
        @param radius    The radius of the circle
        @param velocity  The angular velocity of the circle (rad/s)
        @param initial_angle  The initial angle of the circle (rad, [-pi, pi])
        """
        self.center = center
        self.radius = radius
        self.angle = initial_angle

        self.velocity = velocity

        # A point on the edge of the circle, used as the center of the next circle
        self.edge = Point(
            self.center.x + cos(initial_angle) * radius,
            self.center.y + sin(initial_angle) * radius
        )

    def tick(self, elapsed_us):
        """Update the circle's edge point according to the circle's angular velocity and the
        position of its center

        @param elapsed_us  The time elapsed since the last time we called tick(...)
        """
        seconds = elapsed_us / 1000000
        self.angle += self.velocity * seconds

        # restrict the angle to [-pi, pi]
        if self.angle > pi:
            self.angle = -pi + (self.angle - pi)
        elif self.angle < -pi:
            self.angle = pi - (self.angle + pi)

        self.edge.x = self.center.x + cos(self.angle) * self.radius
        self.edge.y = self.center.y + sin(self.angle) * self.radius


class FiveCircles(EuroPiScript):
    """The main class for this script
    """
    def __init__(self):
        super().__init__()

        # The radii of the circles from inner to outer
        radii = [5, 3, 2, 1, 1]

        # The speeds of the circles in Hz; we'll convert to rad/s later
        speeds = [0.1, 0.2, 0.4, 0.8, 1.6]

        self.max_distance = sum(radii)
        self.min_distance = radii[0] - sum(radii[1:])
        if self.min_distance < 0:
            self.min_distance = 0

        # Generate the 5 circles
        self.circles = []
        origin = Point(0, 0)
        for i in range(5):
            if i == 0:
                origin = Point(0, 0)
            else:
                origin = self.circles[i-1].edge

            theta = random.random() * 2 * pi - pi
            v = speeds[i] * 2 * pi
            c = MovingCircle(origin, radii[i], v, theta)
            self.circles.append(c)

        self.max_distance = sum(radii)

    def main(self):
        oled.fill(0)
        oled.show()

        origin = Point(0, 0)
        last_circle = self.circles[-1]

        quantizer = CommonScales.NatMajor

        last_tick_at = time.ticks_us()
        last_note_at = time.ticks_us()
        last_root_at = time.ticks_us()

        # Quantization variables
        scale = 0
        main_voltage = 0
        root_voltage = 0
        semitone = 0

        prev_note = 0
        prev_root = 0

        TRIGGER_DURATION = 10000      # 10ms
        MIN_SAMPLE_INTERVAL = 20000   # 20ms, 2x trigger duration
        MAX_SAMPLE_INTERVAL = 1000000 # 1s

        sample_interval = int((1-k1.percent()) * 100) / 100 * (MAX_SAMPLE_INTERVAL - MIN_SAMPLE_INTERVAL) + MIN_SAMPLE_INTERVAL
        last_sample_at = time.ticks_us()

        while True:
            now = time.ticks_us()

            sample_interval = int((1-k1.percent()) * 100) / 100 * (MAX_SAMPLE_INTERVAL - MIN_SAMPLE_INTERVAL) + MIN_SAMPLE_INTERVAL

            elapsed = time.ticks_diff(now, last_tick_at)
            for c in self.circles:
                c.tick(elapsed)

            if time.ticks_diff(now, last_sample_at) > sample_interval:
                pitch = origin.distance_from(last_circle.edge) / (self.max_distance - self.min_distance) + self.min_distance
                theta = atan2(last_circle.edge.y, last_circle.edge.x)
                sector = int(degrees(theta) + 180 ) // 30  # divide the circle into 12 equal sectors for the circle of fifths
                scale = circle_of_fifths[sector]
                (main_voltage, semitone) = quantizer.quantize(pitch * VOLTS_PER_OCTAVE, root=scale)
                (root_voltage, _) = quantizer.quantize(0, root=scale)
                last_sample_at = now

            if root_voltage != prev_root:
                last_root_at = now

            oled.centre_text(
f"""{SEMITONE_LABELS[scale]}:{semitone}
{1.0/(sample_interval / 1000000):0.2f}Hz
"""
            )

            # Set the outputs
            cv1.voltage(main_voltage)
            cv2.voltage(root_voltage)
            if time.ticks_diff(now, last_root_at) <= TRIGGER_DURATION:
                cv5.on()
            else:
                cv5.off()
            if time.ticks_diff(now, last_sample_at) <= TRIGGER_DURATION:
                cv6.on()
            else:
                cv6.off()

            last_tick_at = now
            prev_note = main_voltage
            prev_root = root_voltage


if __name__ == "__main__":
    FiveCircles().main()
