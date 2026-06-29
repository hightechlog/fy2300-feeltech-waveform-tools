
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from fy2300_serial import FY2300


DEFAULT_SERIAL_PORT = "COM4"
DEFAULT_BAUDRATE = 9600
DEFAULT_CSV_FILE = "SDS00004.csv"
DEFAULT_T0_SEG = 0.554
DEFAULT_NUM_POINTS = 2048
DEFAULT_NOISE_STD_FRAC = 0.01
DEFAULT_RNG_SEED = 12345


def leer_csv_siglent(nombre_archivo):
    archivo_csv = Path(nombre_archivo).resolve()

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

    if len(tiempo) < 2:
        raise ValueError("No se encontraron suficientes datos numéricos válidos en el CSV.")

    return np.column_stack((np.array(tiempo), np.array(voltaje)))


def extraer_segmento_csv(
    csv_path,
    t0_seg=DEFAULT_T0_SEG,
    num_points=DEFAULT_NUM_POINTS,
    noise_std_frac=DEFAULT_NOISE_STD_FRAC,
    rng_seed=DEFAULT_RNG_SEED,
):
    data1 = leer_csv_siglent(csv_path)

    a = data1[:, 0]
    b = data1[:, 1] + 0.5  # misma corrección de Pruebas1.py

    tm_csv = float(a[1] - a[0])
    fs_csv = 1.0 / tm_csv

    idx0 = int(np.argmin(np.abs(a - t0_seg)))
    if idx0 + num_points > len(a):
        raise ValueError(
            f"No hay suficientes muestras desde t={t0_seg:.6f} s para tomar {num_points} puntos."
        )

    segmento_t_abs = a[idx0:idx0 + num_points]
    segmento_v = b[idx0:idx0 + num_points]

    if len(segmento_v) != num_points:
        raise ValueError(f"Se extrajeron {len(segmento_v)} puntos, pero se requieren {num_points}.")

    periodo_total = num_points * tm_csv
    frecuencia_fy = 1.0 / periodo_total
    t_local = np.arange(num_points) * tm_csv

    waveform = segmento_v.copy()

    rango_pp = float(np.max(waveform) - np.min(waveform))
    sigma_noise = float(noise_std_frac) * rango_pp

    rng = np.random.default_rng(int(rng_seed))
    noise = sigma_noise * rng.standard_normal(len(waveform))
    waveform_noisy = waveform + noise

    return {
        "segmento_t_abs": segmento_t_abs,
        "waveform": waveform,
        "waveform_noisy": waveform_noisy,
        "t_local": t_local,
        "tm_csv": tm_csv,
        "fs_csv": fs_csv,
        "periodo_total": periodo_total,
        "frecuencia_fy": frecuencia_fy,
        "rango_pp": rango_pp,
        "sigma_noise": sigma_noise,
        "num_points": num_points,
        "t0_real": float(segmento_t_abs[0]),
        "tf_real": float(segmento_t_abs[-1]),
    }


def generar_builtin_preview(wave_name, freq_hz, amplitude_vpp, offset_v, n=2000):
    freq_hz = max(float(freq_hz), 1e-9)
    amplitude_vpp = float(amplitude_vpp)
    offset_v = float(offset_v)

    ciclos = 3.0
    t = np.linspace(0.0, ciclos / freq_hz, n, endpoint=False)
    a = amplitude_vpp / 2.0
    phase = (t * freq_hz) % 1.0

    wave_name = str(wave_name).strip().lower()

    if wave_name == "sin":
        y = offset_v + a * np.sin(2.0 * np.pi * freq_hz * t)
    elif wave_name == "square":
        y = offset_v + a * np.where(np.sin(2.0 * np.pi * freq_hz * t) >= 0.0, 1.0, -1.0)
    elif wave_name == "tri":
        y = offset_v + a * (4.0 * np.abs(phase - 0.5) - 1.0)
    elif wave_name == "ramp":
        y = offset_v + a * (2.0 * phase - 1.0)
    elif wave_name == "gauss":
        rng = np.random.default_rng(12345)
        y = offset_v + 0.2 * a * rng.standard_normal(len(t))
    else:
        y = offset_v + a * np.sin(2.0 * np.pi * freq_hz * t)

    return t, y


class FY2300Controller:
    """
    Envoltorio mínimo para usar tu librería actual.
    Soporta dos estrategias:
    1) API tipo "set(...)" si existe en la clase.
    2) API de métodos separados observada en tu script actual.
    """

    def __init__(self, port, baudrate=DEFAULT_BAUDRATE, debug=True):
        self.port = port
        self.baudrate = baudrate
        self.debug = debug

    def _open(self):
        return FY2300(
            port=self.port,
            baudrate=self.baudrate,
            timeout=0.5,
            write_timeout=20.0,
            debug=self.debug,
        )

    def test_connection(self):
        with self._open() as gen:
            info = {
                "port": self.port,
                "baudrate": self.baudrate,
                "has_set": hasattr(gen, "set"),
                "has_upload_waveform": hasattr(gen, "upload_waveform"),
                "has_set_wave_builtin": hasattr(gen, "set_wave_builtin"),
            }
            return info

    def apply_builtin_wave(
        self,
        wave_name,
        freq_hz,
        amplitude_vpp,
        offset_v,
        channel=0,
        enable_output=True,
    ):
        with self._open() as gen:
            # Camino 1: estilo fygen / set()
            if hasattr(gen, "set"):
                kwargs = {
                    "channel": int(channel),
                    "wave": str(wave_name),
                    "freq_hz": float(freq_hz),
                    "enable": bool(enable_output),
                }

                # Algunos wrappers usan 'volts', otros podrían usar 'amplitude_vpp'
                try:
                    kwargs["volts"] = float(amplitude_vpp)
                    kwargs["offset_volts"] = float(offset_v)
                    gen.set(**kwargs)
                except TypeError:
                    kwargs.pop("volts", None)
                    kwargs.pop("offset_volts", None)
                    kwargs["amplitude_vpp"] = float(amplitude_vpp)
                    kwargs["offset_v"] = float(offset_v)
                    gen.set(**kwargs)

                return f"Onda '{wave_name}' aplicada con API set() en CH{int(channel)+1}."

            # Camino 2: tu API actual
            if hasattr(gen, "set_output"):
                gen.set_output(False)
                time.sleep(0.2)

            if hasattr(gen, "set_wave_builtin"):
                gen.set_wave_builtin(str(wave_name))
                time.sleep(0.2)
            else:
                raise RuntimeError("La librería actual no expone set_wave_builtin().")

            if hasattr(gen, "set_frequency_hz"):
                gen.set_frequency_hz(float(freq_hz))
                time.sleep(0.2)

            if hasattr(gen, "set_amplitude_vpp"):
                gen.set_amplitude_vpp(float(amplitude_vpp))
                time.sleep(0.2)

            if hasattr(gen, "set_offset_v"):
                gen.set_offset_v(float(offset_v))
                time.sleep(0.2)

            if hasattr(gen, "set_measurement_coupling") and hasattr(FY2300, "COUPLING_DC"):
                gen.set_measurement_coupling(FY2300.COUPLING_DC)
                time.sleep(0.2)

            if hasattr(gen, "set_output"):
                gen.set_output(bool(enable_output))
                time.sleep(0.2)

            return (
                f"Onda '{wave_name}' aplicada con API simple. "
                f"Nota: CH{int(channel)+1} se ignoró porque esta API no expone selección de canal."
            )

    def set_output(self, enabled):
        with self._open() as gen:
            if not hasattr(gen, "set_output"):
                raise RuntimeError("La librería actual no expone set_output().")
            gen.set_output(bool(enabled))
            return f"Salida {'ON' if enabled else 'OFF'}."

    def upload_csv_segment_as_arb2(
        self,
        csv_path,
        t0_seg,
        num_points,
        noise_std_frac,
        amplitude_vpp,
        offset_v,
        channel=0,
        enable_output=True,
        rng_seed=DEFAULT_RNG_SEED,
    ):
        info = extraer_segmento_csv(
            csv_path=csv_path,
            t0_seg=t0_seg,
            num_points=num_points,
            noise_std_frac=noise_std_frac,
            rng_seed=rng_seed,
        )

        waveform_noisy = info["waveform_noisy"]
        frecuencia_fy = info["frecuencia_fy"]

        with self._open() as gen:
            if not hasattr(gen, "upload_waveform"):
                raise RuntimeError("La librería actual no expone upload_waveform().")

            result = gen.upload_waveform(
                waveform_index=2,
                values=waveform_noisy,
                min_value=float(np.min(waveform_noisy)),
                max_value=float(np.max(waveform_noisy)),
                value_count=int(num_points),
                pack_mode="raw12_u16_be",
            )
            time.sleep(0.5)

            # Si la librería tiene API set(), intentamos usarla con canal
            if hasattr(gen, "set"):
                kwargs = {
                    "channel": int(channel),
                    "wave": "arb2",
                    "freq_hz": float(frecuencia_fy),
                    "enable": bool(enable_output),
                }
                try:
                    kwargs["volts"] = float(amplitude_vpp)
                    kwargs["offset_volts"] = float(offset_v)
                    gen.set(**kwargs)
                except TypeError:
                    kwargs.pop("volts", None)
                    kwargs.pop("offset_volts", None)
                    kwargs["amplitude_vpp"] = float(amplitude_vpp)
                    kwargs["offset_v"] = float(offset_v)
                    gen.set(**kwargs)

                info["result"] = result
                info["message"] = f"arb2 cargada con segmento CSV en CH{int(channel)+1}."
                return info

            # API simple: igual que tu script actual
            if hasattr(gen, "set_output"):
                gen.set_output(False)
                time.sleep(0.2)

            if hasattr(gen, "set_wave_builtin"):
                gen.set_wave_builtin("arb2")
                time.sleep(0.2)
            else:
                raise RuntimeError("La librería actual no expone set_wave_builtin().")

            if hasattr(gen, "set_frequency_hz"):
                gen.set_frequency_hz(float(frecuencia_fy))
                time.sleep(0.2)

            if hasattr(gen, "set_amplitude_vpp"):
                gen.set_amplitude_vpp(float(amplitude_vpp))
                time.sleep(0.2)

            if hasattr(gen, "set_offset_v"):
                gen.set_offset_v(float(offset_v))
                time.sleep(0.2)

            if hasattr(gen, "set_measurement_coupling") and hasattr(FY2300, "COUPLING_DC"):
                gen.set_measurement_coupling(FY2300.COUPLING_DC)
                time.sleep(0.2)

            if hasattr(gen, "set_output"):
                gen.set_output(bool(enable_output))
                time.sleep(0.2)

            if hasattr(gen, "set_trigger_mode") and hasattr(FY2300, "TRIG_EXT"):
                gen.set_trigger_mode(FY2300.TRIG_EXT)
                time.sleep(0.2)

            info["result"] = result
            info["message"] = (
                f"arb2 cargada desde CSV. "
                f"Nota: CH{int(channel)+1} se ignoró porque esta API no expone selección de canal."
            )
            return info


class FY2300GuiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FY2300 GUI simple")
        self.root.geometry("1200x760")

        self.current_csv_info = None
        self.is_busy = False

        self.port_var = tk.StringVar(value=DEFAULT_SERIAL_PORT)
        self.baudrate_var = tk.StringVar(value=str(DEFAULT_BAUDRATE))
        self.channel_var = tk.StringVar(value="0")
        self.wave_var = tk.StringVar(value="sin")
        self.freq_var = tk.StringVar(value="1000")
        self.amplitude_var = tk.StringVar(value="0.5")
        self.offset_var = tk.StringVar(value="0.25")

        default_csv = Path(__file__).resolve().parent / DEFAULT_CSV_FILE
        self.csv_path_var = tk.StringVar(value=str(default_csv))
        self.t0_var = tk.StringVar(value=str(DEFAULT_T0_SEG))
        self.num_points_var = tk.StringVar(value=str(DEFAULT_NUM_POINTS))
        self.noise_var = tk.StringVar(value=str(DEFAULT_NOISE_STD_FRAC))
        self.status_var = tk.StringVar(value="Listo.")

        self._build_ui()
        self._plot_builtin_preview()

    def _build_ui(self):
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left = ttk.Frame(self.root, padding=10)
        left.grid(row=0, column=0, sticky="nsw")
        right = ttk.Frame(self.root, padding=10)
        right.grid(row=0, column=1, sticky="nsew")

        for i in range(20):
            left.rowconfigure(i, weight=0)
        left.columnconfigure(1, weight=1)

        # Conexión
        grp_conn = ttk.LabelFrame(left, text="Conexión", padding=10)
        grp_conn.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(grp_conn, text="Puerto COM").grid(row=0, column=0, sticky="w")
        ttk.Entry(grp_conn, textvariable=self.port_var, width=18).grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(grp_conn, text="Baudrate").grid(row=1, column=0, sticky="w")
        ttk.Entry(grp_conn, textvariable=self.baudrate_var, width=18).grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Button(grp_conn, text="Probar conexión", command=self.on_test_connection).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

        # Onda estándar
        grp_std = ttk.LabelFrame(left, text="Ondas comunes", padding=10)
        grp_std.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(grp_std, text="Canal").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            grp_std,
            textvariable=self.channel_var,
            values=["0", "1"],
            state="readonly",
            width=10,
        ).grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(grp_std, text="Forma").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            grp_std,
            textvariable=self.wave_var,
            values=["sin", "square", "tri", "ramp", "gauss", "arb2"],
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Label(grp_std, text="Frecuencia [Hz]").grid(row=2, column=0, sticky="w")
        ttk.Entry(grp_std, textvariable=self.freq_var).grid(row=2, column=1, sticky="ew", padx=5)

        ttk.Label(grp_std, text="Amplitud Vpp").grid(row=3, column=0, sticky="w")
        ttk.Entry(grp_std, textvariable=self.amplitude_var).grid(row=3, column=1, sticky="ew", padx=5)

        ttk.Label(grp_std, text="Offset [V]").grid(row=4, column=0, sticky="w")
        ttk.Entry(grp_std, textvariable=self.offset_var).grid(row=4, column=1, sticky="ew", padx=5)

        ttk.Button(grp_std, text="Previsualizar onda", command=self._plot_builtin_preview).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=(8, 2)
        )
        ttk.Button(grp_std, text="Aplicar al FY2300", command=self.on_apply_builtin).grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=2
        )
        ttk.Button(grp_std, text="Salida ON", command=lambda: self.on_set_output(True)).grid(
            row=7, column=0, sticky="ew", pady=(4, 0)
        )
        ttk.Button(grp_std, text="Salida OFF", command=lambda: self.on_set_output(False)).grid(
            row=7, column=1, sticky="ew", pady=(4, 0)
        )

        # Arbitraria desde CSV
        grp_csv = ttk.LabelFrame(left, text="Arbitraria desde CSV", padding=10)
        grp_csv.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(grp_csv, text="CSV").grid(row=0, column=0, sticky="w")
        ttk.Entry(grp_csv, textvariable=self.csv_path_var, width=28).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(grp_csv, text="Buscar...", command=self.on_browse_csv).grid(row=0, column=2, padx=(4, 0))

        ttk.Label(grp_csv, text="t0 [s]").grid(row=1, column=0, sticky="w")
        ttk.Entry(grp_csv, textvariable=self.t0_var).grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Label(grp_csv, text="Puntos").grid(row=2, column=0, sticky="w")
        ttk.Entry(grp_csv, textvariable=self.num_points_var).grid(row=2, column=1, sticky="ew", padx=5)

        ttk.Label(grp_csv, text="Ruido frac").grid(row=3, column=0, sticky="w")
        ttk.Entry(grp_csv, textvariable=self.noise_var).grid(row=3, column=1, sticky="ew", padx=5)

        ttk.Button(grp_csv, text="Previsualizar segmento CSV", command=self.on_preview_csv).grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=(8, 2)
        )
        ttk.Button(grp_csv, text="Cargar como arb2 al FY2300", command=self.on_upload_csv_as_arb2).grid(
            row=5, column=0, columnspan=3, sticky="ew", pady=2
        )

        # Estado
        grp_status = ttk.LabelFrame(left, text="Estado", padding=10)
        grp_status.grid(row=3, column=0, sticky="nsew")
        left.rowconfigure(3, weight=1)

        self.status_text = tk.Text(grp_status, width=42, height=22, wrap="word")
        self.status_text.pack(fill="both", expand=True)
        self._log("Aplicación iniciada.")

        # Área derecha con gráfica
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.ax.grid(True)
        self.ax.set_title("Previsualización")
        self.ax.set_xlabel("Tiempo [s]")
        self.ax.set_ylabel("Voltaje [V]")

        self.canvas = FigureCanvasTkAgg(self.figure, master=right)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

    def _controller(self):
        port = self.port_var.get().strip()
        baudrate = int(self.baudrate_var.get().strip())
        return FY2300Controller(port=port, baudrate=baudrate, debug=True)

    def _log(self, text):
        self.status_text.insert("end", text + "\n")
        self.status_text.see("end")
        self.status_var.set(text)

    def _set_busy(self, busy, msg=None):
        self.is_busy = busy
        if msg:
            self.status_var.set(msg)
        self.root.config(cursor="watch" if busy else "")
        self.root.update_idletasks()

    def _run_in_thread(self, worker, success_msg=None):
        if self.is_busy:
            return

        def _job():
            try:
                result = worker()
                self.root.after(0, lambda: self._on_worker_success(result, success_msg))
            except Exception as exc:
                self.root.after(0, lambda: self._on_worker_error(exc))

        self._set_busy(True, "Ejecutando...")
        threading.Thread(target=_job, daemon=True).start()

    def _on_worker_success(self, result, success_msg=None):
        self._set_busy(False)
        if success_msg:
            self._log(success_msg)
        elif result is not None:
            self._log(str(result))

    def _on_worker_error(self, exc):
        self._set_busy(False)
        self._log(f"ERROR: {exc}")
        messagebox.showerror("Error", str(exc))

    def _clear_axes(self):
        self.ax.clear()
        self.ax.grid(True)
        self.ax.set_xlabel("Tiempo [s]")
        self.ax.set_ylabel("Voltaje [V]")

    def _plot_builtin_preview(self):
        try:
            wave_name = self.wave_var.get().strip()
            freq_hz = float(self.freq_var.get())
            amplitude_vpp = float(self.amplitude_var.get())
            offset_v = float(self.offset_var.get())

            t, y = generar_builtin_preview(wave_name, freq_hz, amplitude_vpp, offset_v)

            self._clear_axes()
            self.ax.plot(t, y, label=f"{wave_name}")
            self.ax.set_title(f"Vista previa: {wave_name}")
            self.ax.legend()
            self.canvas.draw()
            self._log(f"Previsualización actualizada para '{wave_name}'.")
        except Exception as exc:
            self._on_worker_error(exc)

    def on_browse_csv(self):
        filename = filedialog.askopenfilename(
            title="Seleccionar CSV Siglent",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if filename:
            self.csv_path_var.set(filename)

    def on_test_connection(self):
        def worker():
            info = self._controller().test_connection()
            return (
                f"Conexión OK. Port={info['port']} baud={info['baudrate']} "
                f"set={info['has_set']} upload_waveform={info['has_upload_waveform']} "
                f"set_wave_builtin={info['has_set_wave_builtin']}"
            )

        self._run_in_thread(worker)

    def on_apply_builtin(self):
        def worker():
            channel = int(self.channel_var.get())
            wave_name = self.wave_var.get().strip()
            freq_hz = float(self.freq_var.get())
            amplitude_vpp = float(self.amplitude_var.get())
            offset_v = float(self.offset_var.get())

            return self._controller().apply_builtin_wave(
                wave_name=wave_name,
                freq_hz=freq_hz,
                amplitude_vpp=amplitude_vpp,
                offset_v=offset_v,
                channel=channel,
                enable_output=True,
            )

        self._run_in_thread(worker)

    def on_set_output(self, enabled):
        def worker():
            return self._controller().set_output(enabled)

        self._run_in_thread(worker)

    def on_preview_csv(self):
        try:
            csv_path = self.csv_path_var.get().strip()
            t0_seg = float(self.t0_var.get())
            num_points = int(self.num_points_var.get())
            noise_std_frac = float(self.noise_var.get())

            info = extraer_segmento_csv(
                csv_path=csv_path,
                t0_seg=t0_seg,
                num_points=num_points,
                noise_std_frac=noise_std_frac,
                rng_seed=DEFAULT_RNG_SEED,
            )
            self.current_csv_info = info

            self._clear_axes()
            self.ax.plot(info["segmento_t_abs"], info["waveform"], label="Segmento CSV usado")
            self.ax.plot(info["segmento_t_abs"], info["waveform_noisy"], "--", label="Segmento CSV + ruido")
            self.ax.set_title("Vista previa segmento CSV")
            self.ax.set_xlabel("Tiempo absoluto del CSV [s]")
            self.ax.set_ylabel("Voltaje corregido [V]")
            self.ax.legend()
            self.canvas.draw()

            self._log(
                "Segmento CSV listo: "
                f"t0={info['t0_real']:.9f} s, tf={info['tf_real']:.9f} s, "
                f"N={info['num_points']}, f_FY={info['frecuencia_fy']:.6f} Hz, "
                f"sigma_ruido={info['sigma_noise']:.6f}"
            )
        except Exception as exc:
            self._on_worker_error(exc)

    def on_upload_csv_as_arb2(self):
        def worker():
            csv_path = self.csv_path_var.get().strip()
            t0_seg = float(self.t0_var.get())
            num_points = int(self.num_points_var.get())
            noise_std_frac = float(self.noise_var.get())
            amplitude_vpp = float(self.amplitude_var.get())
            offset_v = float(self.offset_var.get())
            channel = int(self.channel_var.get())

            info = self._controller().upload_csv_segment_as_arb2(
                csv_path=csv_path,
                t0_seg=t0_seg,
                num_points=num_points,
                noise_std_frac=noise_std_frac,
                amplitude_vpp=amplitude_vpp,
                offset_v=offset_v,
                channel=channel,
                enable_output=True,
                rng_seed=DEFAULT_RNG_SEED,
            )

            return (
                f"{info['message']} "
                f"f_FY={info['frecuencia_fy']:.6f} Hz, "
                f"t0={info['t0_real']:.9f} s, tf={info['tf_real']:.9f} s, "
                f"sigma_ruido={info['sigma_noise']:.6f}"
            )

        self._run_in_thread(worker)


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    app = FY2300GuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
