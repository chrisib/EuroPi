# Pam's "EuroPi" Workout

This program is an homage to ALM's Pamela's "NEW" Workout and Pamela's "PRO"
Workout modules, designed for the EuroPi.  It is intended to be used as a
main clock generator, euclidean rhythm generator, clocked LFO, clocked
random voltage source, etc... with optional quantization.

The module itself will generate the master clock signal with a configurable
BPM (1-300 BPM supported).  Each output has an independently controlled
clock multiplier or divider, chosen from the following:

```
[x8, x6, x4, x3, x2, x1, /2, /3, /4, /6, /8, /12, /16]
```

## I/O Mapping

| I/O           | Usage
|---------------|-------------------------------------------------------------------|
| `din`         | External start/stop input                                         |
| `ain`         | Routable CV input to control other parameters                     |
| `b1`          | Start/Stop input                                                  |
| `b2`          | Press to enter/exit edit mode. Long-press to enter/leave sub-menu |
| `k1`          | Scroll through the current menu                                   |
| `k2`          | Scroll through allowed values for the current menu item           |
| `cv1` - `cv6` | Output signals. Configuration is explained below                  |

## External CV Routing

The input signal to `ain` can be configured to control many parameters of the system.
A value of 0V is the equivalent of choosing the first item from the available menu
and 10V is the equivalent of choosing the last item in the menu.

There is no attenuation of the input signal available, so you will have to use an
external attenuator or VCA to control the signal coming into `ain`.

## Menu Navigation

Rotate `k1` to scroll through the current menu.  Pressing and holding `b2` for 0.5s will
enter a sub-menu.  Pressing and holding `b2` again will return to the parent menu.

On any given menu item, pressing `b2` (without holding) will enter edit mode for that
item.  Rotate `k2` to choose the desired value for the item, and press `b2` again
to apply it.

The menu layout is as follows:

```
|-- Clock
|   |-- BPM
|   |   |-- Reset
|-- CV1
|   |-- Mod.
|   |   |-- Wave Shape
|   |   |-- Wave Amplitude
|   |   |-- Skip Probability
|   |   |-- Euclidean Steps
|   |   |-- Euclidean Triggers
|   |   |-- Euclidean Rotatioj
|   |   |-- Quantization Scale
|-- CV2 to 6
|   |-- Same as CV1
|-- AIN
|   |-- Gain
|   |   |-- Destination Channel
|   |   |-- Destination Property
```

## Main Clock Options

The main clock menu has the following options:

- `BPM` -- the main BPM for the clock. Must be in the range `[TODO_LOW, TODO_HIGH]`.

The submenu for the main clock has the following options:

- `Reset` -- if true, all waves & euclidean patterns will reset when the clock starts.
  Otherwise they will continue from where they stopped

## CV Channel Options

Each of the 6 CV output channels has the following options:

- `Mod` -- the clock modifier.  See above for valid ranges.

The submenu for each CV output has the following options:

- `Wave` -- the wave shape to output. Square/Triangle/Sine/Random/Reset
- `Ampl.` -- the maximum amplitude of the output as a percentage of the 10V
  hardware maximum
- `Width` -- width of the resulting wave. See below
- `Skip%` -- the probability that a square pulse or euclidean trigger
  will be skipped
- `EStep` -- the number of steps in the euclidean rhythm. If zero, the
  euclidean generator is disabled
- `ETrig` -- the number of pulses in the euclidean rhythm
- `ERot` -- rotation of the euclidean rhythm
- `Quant` -- quantization scale

The Reset wave fires only when the clock is stopped and can be used to help synchronize
external modules (e.g. other sequencers, sequential switches, etc...)

Effects of width control on different wave shapes:
- Square: Duty cycle control. 0% is always off, 100% is always on
- Triangle: Symmetry control. 50% results in a symmetrical wave, 0% results in a saw wave,
  100% results in a ramp
- Sine: ignored
- Random: offset voltage as a percentage of the maximum output
- Reset: ignored

## AIN Routing Menu

The signal to `ain` can be routed to the master clock or any of the CV channels.

The following properties can be CV controlled:

- Master Clock:
    - BPM
- CV 1-6:
    - Clock modifier
    - Wave shape
    - Amplitude
    - Width
    - Skip
    - Euclidean steps
    - Euclidean pulses
    - Euclidean rotation
    - Quantizer

Because many LFOs, EGs, and other modulation sources output 5V maximum, but the maximum input
to EuroPi is 12V, the gain to `ain` can be increased by up to 300%.  This will artificially
increase the signal being applied to the desired property without the need for an external
amplifier.