# El FY2300 puede sintetizar máximo 12048 puntos por slot, con 16 slots de 12 bits de resolucion vertical
# la tasa de muestreo interna es de un sampling rate máximo de 200 MSa/s
# sin emabrgo el FY2300-20 MHz, puede sintetizar ondas seno de hasta 20 MHZ
# posiblemente la arbitraria no más allá de 6 MHz
# la frecuencia mínima es quizás 1 uHz

import numpy as np
import matplotlib.pyplot as plt
import time

from fy2300_serial import FY2300

SERIAL_PORT = "COM4"

# ============================================================
# Parámetros de la waveform para FY2300
# ============================================================
num_points = 2048
periodo_total = 48e-3
frecuencia_fy = 1.0 / periodo_total
tm = periodo_total / num_points
fs = 1.0 / tm
t = np.arange(num_points) * tm

print(f"Tiempo de muestreo: {tm:.9e} s")
print(f"Frecuencia equivalente: {frecuencia_fy:.6f} Hz")
print(f"Frecuencia interna equivalente: {fs:.3f} Hz")

# ============================================================
# Ecos simulados (misma lógica que tu Tektronix)
# ============================================================
A1, t01, sigma1 = 1.0, 1.5e-3, 0.325e-3
A2, t02, sigma2 = 1.0, 10.5e-3, 0.435e-3

pulse1 = A1 * np.exp(-0.5 * ((t - t01) / sigma1) ** 2)
pulse1 = np.minimum(pulse1, 1.0)
pulse2 = A2 * np.exp(-0.5 * ((t - t02) / sigma2) ** 2)

waveform = pulse1 + pulse2

# ============================================================
# Ventana local del segundo eco
# ============================================================
k_sigma = 3.0
mask2 = (t >= (t02 - k_sigma * sigma2)) & (t <= (t02 + k_sigma * sigma2))

# ============================================================
# SNR objetivo
# ============================================================
snr_db_target = 20.0

Ps2 = np.mean(pulse2[mask2] ** 2)
Pn = Ps2 / (10 ** (snr_db_target / 10.0))
sigma_n = np.sqrt(Pn)

rng = np.random.default_rng(12345)
noise = sigma_n * rng.standard_normal(len(t))

waveform_noisy = waveform + noise

Pn_measured = np.mean(noise[mask2] ** 2)
snr_db_measured = 10 * np.log10(Ps2 / Pn_measured)

print(f"Ps2               = {Ps2:.6e}")
print(f"Pn objetivo       = {Pn:.6e}")
print(f"Pn medido         = {Pn_measured:.6e}")
print(f"SNR objetivo (dB) = {snr_db_target:.3f}")
print(f"SNR medido  (dB)  = {snr_db_measured:.3f}")

# ============================================================
# Carga al FY2300
# ============================================================
with FY2300(
    port=SERIAL_PORT,
    baudrate=9600,
    timeout=0.5,
    write_timeout=20.0,
    debug=True,
) as gen:

    # Cargar arb1 con la señal de ecos
    result = gen.upload_waveform(
        waveform_index=2,
        values=waveform_noisy,
        min_value=float(np.min(waveform_noisy)),
        max_value=float(np.max(waveform_noisy)),
        value_count=2048,
        pack_mode="raw12_u16_be",
    )
    time.sleep(2.0)
    print("Carga:", result)
    # Reproducción de arb1
    gen.set_output(False)
    time.sleep(2.0)
    gen.set_wave_builtin("arb2")
    time.sleep(2.0)
    gen.set_frequency_hz(frecuencia_fy)
    time.sleep(2.0)
    gen.set_amplitude_vpp(3.3)
    time.sleep(2.0)
    gen.set_offset_v(1.65)
    time.sleep(2.0)
    # Coupling DC como pediste
    gen.set_measurement_coupling(FY2300.COUPLING_DC)
    time.sleep(2.0)
    gen.set_output(True)
    time.sleep(2.0)
    gen.set_trigger_mode(FY2300.TRIG_EXT)
    time.sleep(2.0)

    print("arb1 cargada y configurada.")

# ============================================================
# Gráfica local de referencia
# ============================================================
plt.plot(t, waveform, label="Señal ideal")
plt.plot(t, waveform_noisy, label="Señal con ruido")
plt.grid(True)
plt.legend()
plt.show()