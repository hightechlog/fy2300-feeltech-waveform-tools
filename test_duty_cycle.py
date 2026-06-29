from fy2300_serial import FY2300
import time

with FY2300(port="COM4", debug=True) as gen:
    gen.set_wave_builtin("square")
    gen.set_frequency_hz(1000.0)
    gen.set_amplitude_vpp(1.0)
    gen.set_offset_v(0.0)
    gen.set_output(True)

    for duty in [10.0, 25.0, 50.0, 75.0, 90.0]:
        print(f"Duty: {duty}%")
        gen.set_duty_percent(duty)
        time.sleep(2)