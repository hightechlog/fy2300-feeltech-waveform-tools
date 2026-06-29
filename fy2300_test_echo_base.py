from fy2300_serial import FY2300

SERIAL_PORT = "COM4"

Frecuencia_fy = 1.0 / 24e-3   # 41.666667 Hz

with FY2300(
    port=SERIAL_PORT,
    baudrate=115200,
    timeout=0.2,
    write_delay_s=0.05,
    command_retries=3,
    debug=True,
) as gen:

    gen.apply_basic_output(
        wave_name="sin",
        frequency_hz=Frecuencia_fy,
        amplitude_vpp=2.0,
        offset_v=1.1,
        output_on=True,
    )

    print("Configuración base similar a la del Tek enviada.")