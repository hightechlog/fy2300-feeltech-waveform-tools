from fy2300_serial import FY2300
import time

with FY2300(port="COM4", debug=True) as gen:
    gen.set_amplitude_vpp(2.0)
    gen.set_offset_v(1.1)
    gen.set_frequency_hz(41.666667)
    gen.set_trigger_mode(FY2300.TRIG_EXT)
    gen.set_trigger_cycles(1)
    gen.set_measurement_coupling(FY2300.COUPLING_DC)
    gen.set_output(True)

    print("Seleccionando arb1...")
    gen.set_wave_builtin("arb1")
    time.sleep(5)

    print("Seleccionando seno...")
    gen.set_wave_builtin("sin")
    time.sleep(5)

    print("Seleccionando arb1 otra vez...")
    gen.set_wave_builtin("arb1")
    time.sleep(5)