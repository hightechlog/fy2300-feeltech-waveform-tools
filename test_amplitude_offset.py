from fy2300_serial import FY2300
import time

with FY2300(port="COM4", debug=True) as gen:
    gen.set_wave_builtin("sin")
    gen.set_frequency_hz(1000.0)
    gen.set_output(True)

    for amp in [0.5, 1.0, 2.0, 5.0]:
        print(f"Amplitud: {amp} Vpp")
        gen.set_amplitude_vpp(amp)
        time.sleep(1.5)

    for off in [-1.0, 0.0, 1.1, 2.0]:
        print(f"Offset: {off} V")
        gen.set_offset_v(off)
        time.sleep(1.5)