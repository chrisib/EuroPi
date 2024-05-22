# Five Circles

Five Cicles is a chaotic sequencer that generates quantized patterns based on the motion of 5 connected circles.

This work was inspired by two Marc Evanstein videos:
- https://www.youtube.com/watch?v=wn3td88w19E
- https://www.youtube.com/watch?v=fxzrpfezezE


## I/O Mapping

Inputs:
- `ain`: not used
- `din`: not used
- `b1`: not used
- `b2`: not used
- `k1`: Sample speed
- `k2`: not used

Outputs:
- `cv1`: A quantized circle-of-fifths note derived from the positions of the circles
- `cv2`: The root note of the scale of `cv1`
- `cv3`: not used
- `cv4`: not used
- `cv5`: Outputs a 10ms trigger every time `cv2` changes
- `cv6`: Outputs a 10ms trigger every time `cv1`'s value is updated
