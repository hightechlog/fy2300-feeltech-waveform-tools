from fy2300_serial import FY2300
import time

with FY2300(port="COM4", debug=True) as gen:
    gen.set_wave_builtin("sin")
    gen.set_frequency_hz(1000.0)
    gen.set_amplitude_vpp(1.0)
    gen.set_offset_v(0.0)

    gen.set_output(True)
    print("Salida ON")
    time.sleep(2)

    gen.set_output(False)
    print("Salida OFF")
    time.sleep(2)

    gen.set_output(True)
    print("Salida ON otra vez")
    time.sleep(2)