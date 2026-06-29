from fy2300_serial import FY2300
import time

with FY2300(port="COM4", debug=True) as gen:
    gen.set_wave_builtin("sin")
    time.sleep(0.5)

    gen.set_frequency_hz(1000.0)
    time.sleep(2)

    gen.set_frequency_hz(2000.0)
    time.sleep(2)

    gen.set_frequency_hz(500.0)
    time.sleep(2)