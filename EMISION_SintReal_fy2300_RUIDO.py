# Adaptación mínima de EMISION_1_0v_ECHO_1_0_V_fy2300.py
# En lugar de sintetizar la señal con ecuaciones, extrae un segmento medido desde SDS00004.csv.
# Se usa un bloque contiguo de 2048 muestras para evitar interpolación.
# Segmento elegido: desde 0.554000 s hasta 0.574470 s (2048 puntos exactos con dt = 10 us).
# Además, se añade una pequeña cantidad de ruido blanco al segmento antes de cargarlo al FY2300.

import numpy as np
import matplotlib.pyplot as plt
import time
from pathlib import Path

from fy2300_serial import FY2300

SERIAL_PORT = "COM4"
CSV_FILE = "SDS00004.csv"
T0_SEG = 0.554  # s, inicio del segmento tomado del CSV
NUM_POINTS_FY = 2048
NOISE_STD_FRAC = 0.01  # desviación estándar del ruido = 1% del rango pico a pico del segmento
RNG_SEED = 12345


def leer_csv_siglent(nombre_archivo=CSV_FILE):
    ruta_script = Path(__file__).resolve().parent
    archivo_csv = ruta_script / nombre_archivo

    if not archivo_csv.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {archivo_csv}")

    lineas = archivo_csv.read_text(encoding="utf-8", errors="ignore").splitlines()

    inicio_datos = None
    for i, linea in enumerate(lineas):
        if linea.strip().startswith("Second,Volt"):
            inicio_datos = i + 1
            break

    if inicio_datos is None:
        raise ValueError("No se encontró la cabecera 'Second,Volt' en el CSV.")

    tiempo = []
    voltaje = []

    for linea in lineas[inicio_datos:]:
        linea = linea.strip()
        if not linea:
            continue

        partes = linea.split(",")
        if len(partes) < 2:
            continue

        try:
            t = float(partes[0])
            v = float(partes[1])
            tiempo.append(t)
            voltaje.append(v)
        except ValueError:
            continue

    if len(tiempo) == 0:
        raise ValueError("No se encontraron datos numéricos válidos en el CSV.")

    return np.column_stack((np.array(tiempo), np.array(voltaje)))


# ============================================================
# Lectura de la señal medida desde CSV
# ============================================================
data1 = leer_csv_siglent(CSV_FILE)

a = data1[:, 0]
b = data1[:, 1] + 0.5  # misma corrección usada en Pruebas1.py

# dt real del CSV
if len(a) < 2:
    raise ValueError("El CSV no tiene suficientes muestras.")

tm_csv = a[1] - a[0]
fs_csv = 1.0 / tm_csv

# Buscar el índice inicial más cercano a T0_SEG
idx0 = int(np.argmin(np.abs(a - T0_SEG)))

if idx0 + NUM_POINTS_FY > len(a):
    raise ValueError(
        f"No hay suficientes muestras desde t={T0_SEG:.6f} s para tomar {NUM_POINTS_FY} puntos."
    )

# Tomar exactamente 2048 puntos contiguos para evitar interpolación
segmento_t_abs = a[idx0:idx0 + NUM_POINTS_FY]
segmento_v = b[idx0:idx0 + NUM_POINTS_FY]

num_points = len(segmento_v)
if num_points != NUM_POINTS_FY:
    raise ValueError(f"Se extrajeron {num_points} puntos, pero se requieren {NUM_POINTS_FY}.")

# Tiempo local para la síntesis del FY2300
periodo_total = num_points * tm_csv
frecuencia_fy = 1.0 / periodo_total
tm = tm_csv
fs = fs_csv
# Tiempo local arrancando en cero, equivalente al periodo sintetizado en el FY2300
# (la señal cargada conserva la forma del segmento absoluto extraído del CSV)
t = np.arange(num_points) * tm

waveform = segmento_v.copy()

# ============================================================
# Ruido blanco añadido al segmento medido
# ============================================================
rango_pp = float(np.max(waveform) - np.min(waveform))
sigma_noise = NOISE_STD_FRAC * rango_pp
rng = np.random.default_rng(RNG_SEED)
noise = sigma_noise * rng.standard_normal(len(waveform))
waveform_noisy = waveform + noise

print(f"CSV dt                    = {tm_csv:.9e} s")
print(f"CSV fs                    = {fs_csv:.3f} Hz")
print(f"Tiempo inicial extraído   = {segmento_t_abs[0]:.9f} s")
print(f"Tiempo final extraído     = {segmento_t_abs[-1]:.9f} s")
print(f"Número de puntos          = {num_points}")
print(f"Periodo total FY2300      = {periodo_total:.9e} s")
print(f"Frecuencia equivalente FY = {frecuencia_fy:.6f} Hz")
print(f"Rango pico a pico         = {rango_pp:.6f}")
print(f"Sigma ruido blanco        = {sigma_noise:.6f}")
print(f"Valor mínimo waveform     = {np.min(waveform_noisy):.6f}")
print(f"Valor máximo waveform     = {np.max(waveform_noisy):.6f}")

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

    # Cargar arb2 con la señal extraída del CSV + ruido blanco leve
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

    # Reproducción de arb2
    gen.set_output(False)
    time.sleep(2.0)
    gen.set_wave_builtin("arb2")
    time.sleep(2.0)
    gen.set_frequency_hz(frecuencia_fy)
    time.sleep(2.0)
    gen.set_amplitude_vpp(0.5)
    time.sleep(2.0)
    gen.set_offset_v(0.25)
    time.sleep(2.0)
    gen.set_measurement_coupling(FY2300.COUPLING_DC)
    time.sleep(2.0)
    gen.set_output(True)
    time.sleep(2.0)
    gen.set_trigger_mode(FY2300.TRIG_EXT)
    time.sleep(2.0)

    print("arb2 cargada y configurada desde segmento de SDS00004.csv con ruido blanco.")

# ============================================================
# Gráfica local de referencia
# ============================================================
plt.figure(figsize=(10, 6))
plt.plot(segmento_t_abs, waveform, label="Segmento CSV usado")
plt.plot(segmento_t_abs, waveform_noisy, "--", label="Segmento CSV + ruido blanco")
plt.grid(True)
plt.xlabel("Tiempo absoluto del CSV [s]")
plt.ylabel("Voltaje corregido [V]")
plt.legend()
plt.tight_layout()
plt.show()
