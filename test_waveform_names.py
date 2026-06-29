from fy2300_serial import FY2300
import time

waves = ["sin", "square", "triangle"]

with FY2300(port="COM4", debug=True) as gen:
    gen.set_frequency_hz(1000.0)
    gen.set_amplitude_vpp(1.0)
    gen.set_offset_v(0.0)
    gen.set_output(True)

    for w in waves:
        print(f"Forma: {w}")
        gen.set_wave_builtin(w)
        time.sleep(2)