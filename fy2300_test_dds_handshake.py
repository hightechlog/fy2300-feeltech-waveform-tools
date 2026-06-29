import math
import time
from fy2300_serial import FY2300

SERIAL_PORT = "COM4"

PACK_MODES = [
    "raw12_u16_be",
]

def play(gen, secs=6):
    gen.set_trigger_mode(FY2300.TRIG_OFF)
    gen.set_output(False)
    gen.set_wave_builtin("arb1")
    time.sleep(0.2)
    gen.set_frequency_hz(1000.0)
    gen.set_amplitude_vpp(1.0)
    gen.set_offset_v(0.0)
    time.sleep(0.2)
    gen.set_output(True)
    time.sleep(secs)
    gen.set_output(False)
    time.sleep(1.0)

with FY2300(
    port=SERIAL_PORT,
    baudrate=9600,
    timeout=0.5,
    write_timeout=20.0,
    debug=True,
) as gen:

    n = 2048

    # 1) constante media
    wave_mid = [0.0] * n
    for mode in PACK_MODES:
        print(f"\n=== MID | {mode} ===")
        result = gen.upload_waveform(
            waveform_index=1,
            values=wave_mid,
            min_value=-1.0,
            max_value=1.0,
            value_count=n,
            pack_mode=mode,
        )
        print(result)
        play(gen, secs=5)

    # 2) senoide
    wave_sin = [math.sin(2.0 * math.pi * t / n) for t in range(n)]
    for mode in PACK_MODES:
        print(f"\n=== SINE | {mode} ===")
        result = gen.upload_waveform(
            waveform_index=1,
            values=wave_sin,
            min_value=-1.0,
            max_value=1.0,
            value_count=n,
            pack_mode=mode,
        )
        print(result)
        play(gen, secs=5)