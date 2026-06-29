from fy2300_serial import FY2300
import time

freqs = [10.0, 41.666667, 1000.0, 10000.0, 100000.0]

with FY2300(port="COM4", debug=True) as gen:
    gen.set_wave_builtin("sin")
    gen.set_amplitude_vpp(1.0)
    gen.set_offset_v(0.0)
    gen.set_output(True)

    for f in freqs:
        print(f"Probando frecuencia: {f} Hz")
        gen.set_frequency_hz(f)
        time.sleep(2)