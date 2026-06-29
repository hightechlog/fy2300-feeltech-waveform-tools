import time
from typing import Optional
import numpy as np

class FY2300Error(Exception):
    pass


class FY2300:
    """
    Control serie del FeelTech FY2300.

    Base confirmada:
    - baudrate 9600
    - comandos ASCII terminados en '\\n'
    - enfoque orientado a escritura confiable
    - lecturas best-effort, porque algunos firmwares responden vacío
    """

    # -------------------------
    # Constantes de uso común
    # -------------------------
    GATE_TIME_1S = 0
    GATE_TIME_10S = 1
    GATE_TIME_100S = 2

    COUPLING_DC = 0
    COUPLING_AC = 1

    ATTEN_0DB = 0
    ATTEN_20DB = 1

    TRIG_OFF = 0
    TRIG_CH2 = 1
    TRIG_EXT = 2
    TRIG_MANUAL = 3

    SWEEP_OBJ_FREQUENCY = 0
    SWEEP_OBJ_AMPLITUDE = 1
    SWEEP_OBJ_OFFSET = 2
    SWEEP_OBJ_DUTY = 3

    SWEEP_LINEAR = 0
    SWEEP_LOG = 1

    SYNC_WAVE = 0
    SYNC_FREQ = 1
    SYNC_AMPLITUDE = 2
    SYNC_OFFSET = 3
    SYNC_DUTY = 4

    # WMWxx según el protocolo FY2300
    WAVE_CODES = {
        "sin": 0,
        "sine": 0,
        "square": 1,
        "triangle": 2,
        "ramp_up": 3,
        "ramp_down": 4,
        "step_triangle": 5,
        "positive_step": 6,
        "inverse_step": 7,
        "positive_exponent": 8,
        "inverse_exponent": 9,
        "positive_lorentz": 10,
        "inverse_lorentz": 11,
        "positive_multitone": 12,
        "inverse_multitone": 13,
        "positive_noise": 14,
        "inverse_noise": 15,
        "ecg": 16,
        "trapezoid_1": 17,
        "sinc": 18,
        "narrow_pulse": 19,
        "gaussian_white_noise": 27,
        "am": 28,
        "fm": 29,
        "linear_fm": 30,
        "arb1": 31,
        "arb2": 32,
        "arb3": 33,
        "arb4": 34,
        "arb5": 35,
        "arb6": 36,
        "arb7": 37,
        "arb8": 38,
        "arb9": 39,
        "arb10": 40,
        "arb11": 41,
        "arb12": 42,
        "arb13": 43,
        "arb14": 44,
        "arb15": 45,
        "arb16": 46,
    }

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        timeout: float = 0.5,
        write_timeout: float = 20.0,
        write_delay_s: float = 0.05,
        read_delay_s: float = 0.05,
        command_retries: int = 3,
        debug: bool = False,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.write_delay_s = write_delay_s
        self.read_delay_s = read_delay_s
        self.command_retries = command_retries
        self.debug = debug
        self.ser = None

    # -------------------------
    # Gestión del puerto
    # -------------------------
    def open(self) -> None:
        if self.ser is not None and self.ser.is_open:
            return

        import serial  # import local para no forzar dependencia al importar el módulo

        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=self.write_timeout,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )

        time.sleep(0.2)

        # Secuencia de wake-up similar a fygen
        time.sleep(0.2)
        self.flush_buffers()

    def close(self) -> None:
        if self.ser is not None:
            try:
                if self.ser.is_open:
                    self.ser.close()
            finally:
                self.ser = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _ensure_open(self) -> None:
        if self.ser is None or not self.ser.is_open:
            raise FY2300Error("El puerto serie no está abierto.")

    def flush_buffers(self) -> None:
        self._ensure_open()
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    # -------------------------
    # Bajo nivel
    # -------------------------
    def _write_ascii_once(self, cmd: str) -> None:
        self._ensure_open()
        full_cmd = cmd + "\n"

        if self.debug:
            print(f"TX: {cmd}")

        self.ser.write(full_cmd.encode("ascii"))
        self.ser.flush()
        time.sleep(self.write_delay_s)

    def _read_ascii_available(self) -> str:
        self._ensure_open()
        time.sleep(self.read_delay_s)
        raw = self.ser.read_all()
        text = raw.decode("ascii", errors="ignore").strip()

        if self.debug:
            print(f"RX: {text!r}")

        return text
    
    def _read_ack(self, wait_s: float = 1.0, expected: str | None = None) -> str:
        self._ensure_open()
        deadline = time.time() + wait_s
        data = bytearray()
        last_text = ""

        while time.time() < deadline:
            chunk = self.ser.read_all()
            if chunk:
                data.extend(chunk)
                text = data.decode("ascii", errors="ignore").strip()
                last_text = text

                if self.debug:
                    print(f"RX_ACK_PROGRESS: {text!r}")

                if expected is None:
                    if text:
                        return text
                else:
                    if expected in text:
                        if self.debug:
                            print(f"RX_ACK_MATCH: {text!r}")
                        return text

            time.sleep(0.02)

        if self.debug:
            print(f"RX_ACK_TIMEOUT: {last_text!r}")
        return last_text

    def write_only(self, cmd: str) -> None:
        last_exc = None
        for _ in range(self.command_retries):
            try:
                self._write_ascii_once(cmd)
                return
            except Exception as exc:
                last_exc = exc
                time.sleep(0.1)
        raise FY2300Error(f"No se pudo enviar {cmd!r}: {last_exc}")

    def query_best_effort(self, cmd: str) -> str:
        self._write_ascii_once(cmd)
        return self._read_ascii_available()

    def send_raw(self, cmd: str, read: bool = False) -> str:
        """
        Envío libre por si quieres probar comandos nuevos sin tocar la clase.
        """
        if read:
            return self.query_best_effort(cmd)
        self.write_only(cmd)
        return ""

    # -------------------------
    # Canal principal CH1
    # -------------------------
    def set_wave_builtin(self, wave_name: str) -> None:
        wave_name = wave_name.lower().strip()
        if wave_name not in self.WAVE_CODES:
            valid = ", ".join(sorted(self.WAVE_CODES.keys()))
            raise ValueError(f"Forma no soportada: {wave_name!r}. Válidas: {valid}")
        code = self.WAVE_CODES[wave_name]
        self.write_only(f"WMW{code:02d}")

    def set_arb_slot(self, arb_index: int) -> None:
        """
        arb1..arb16 según la tabla visible del protocolo.
        WMW31 = Arbitrary1, WMW32 = Arbitrary2, etc.
        """
        if not (1 <= arb_index <= 16):
            raise ValueError("arb_index debe estar entre 1 y 16")
        code = 30 + arb_index
        self.write_only(f"WMW{code:02d}")

    def set_frequency_hz(self, freq_hz: float) -> None:
        """
        WMF usa 14 dígitos y unidad fija en uHz.
        """
        if freq_hz <= 0:
            raise ValueError("freq_hz debe ser > 0")

        freq_uHz = int(round(freq_hz * 1_000_000.0))

        # En el protocolo FY2300 los ejemplos se envían sin padding a la izquierda:
        # 100 Hz -> WMF1000000000
        self.write_only(f"WMF{freq_uHz}")

    def set_amplitude_vpp(self, amplitude_vpp: float) -> None:
        if amplitude_vpp < 0:
            raise ValueError("amplitude_vpp debe ser >= 0")
        self.write_only(f"WMA{amplitude_vpp:.2f}")

    def set_offset_v(self, offset_v: float) -> None:
        self.write_only(f"WMO{offset_v:.2f}")

    def set_duty_percent(self, duty_percent: float) -> None:
        if not (0.1 <= duty_percent <= 99.9):
            raise ValueError("duty_percent debe estar entre 0.1 y 99.9")
        self.write_only(f"WMD{duty_percent:.1f}")

    def set_phase_deg(self, phase_deg: int) -> None:
        if not (0 <= phase_deg <= 359):
            raise ValueError("phase_deg debe estar entre 0 y 359")
        self.write_only(f"WMP{phase_deg:d}")

    def set_attenuation(self, atten_mode: int) -> None:
        if atten_mode not in (self.ATTEN_0DB, self.ATTEN_20DB):
            raise ValueError("atten_mode inválido")
        self.write_only(f"WMT{atten_mode}")

    def set_trigger_mode(self, trig_mode: int) -> None:
        """
        0=off, 1=CH2 trigger, 2=EXT trigger, 3=manual trigger
        """
        if trig_mode not in (0, 1, 2, 3):
            raise ValueError("trig_mode inválido")
        self.write_only(f"WPM{trig_mode}")

    def set_trigger_cycles(self, ncycles: int) -> None:
        if not (1 <= ncycles <= 1048575):
            raise ValueError("ncycles debe estar entre 1 y 1048575")
        self.write_only(f"WPN{ncycles:d}")

    def trigger_once_manual(self) -> None:
        """
        Según el protocolo, WPM3 configura trigger manual y cada envío dispara una vez.
        """
        self.write_only("WPM3")

    def set_output(self, enabled: bool) -> None:
        self.write_only(f"WMN{1 if enabled else 0}")

    def apply_basic_output(
        self,
        wave_name: str,
        frequency_hz: float,
        amplitude_vpp: float,
        offset_v: float,
        output_on: bool = True,
    ) -> None:
        self.set_wave_builtin(wave_name)
        self.set_frequency_hz(frequency_hz)
        self.set_amplitude_vpp(amplitude_vpp)
        self.set_offset_v(offset_v)
        self.set_output(output_on)

    # -------------------------
    # Lecturas CH1 (best-effort)
    # -------------------------
    def get_wave_raw(self) -> str:
        return self.query_best_effort("RMW")

    def get_frequency_raw(self) -> str:
        return self.query_best_effort("RMF")

    def get_amplitude_raw(self) -> str:
        return self.query_best_effort("RMA")

    def get_offset_raw(self) -> str:
        return self.query_best_effort("RMO")

    def get_duty_raw(self) -> str:
        return self.query_best_effort("RMD")

    def get_phase_raw(self) -> str:
        return self.query_best_effort("RMP")

    def get_attenuation_raw(self) -> str:
        return self.query_best_effort("RMT")

    def get_output_raw(self) -> str:
        return self.query_best_effort("RMN")

    # -------------------------
    # Measurement / Counter
    # -------------------------
    def get_meas_frequency_raw(self) -> str:
        return self.query_best_effort("RCF")

    def get_meas_count_raw(self) -> str:
        return self.query_best_effort("RCC")

    def clear_counter(self) -> None:
        self.write_only("WCZ0")

    def pause_counter(self) -> None:
        self.write_only("WCP0")

    def get_meas_period_ns_raw(self) -> str:
        return self.query_best_effort("RCT")

    def get_meas_positive_pulse_ns_raw(self) -> str:
        return self.query_best_effort("RC+")

    def get_meas_negative_pulse_ns_raw(self) -> str:
        return self.query_best_effort("RC-")

    def get_meas_duty_permille_raw(self) -> str:
        return self.query_best_effort("RCD")

    def set_measurement_gate_time(self, gate_mode: int) -> None:
        if gate_mode not in (self.GATE_TIME_1S, self.GATE_TIME_10S, self.GATE_TIME_100S):
            raise ValueError("gate_mode inválido")
        self.write_only(f"WCG{gate_mode}")

    def get_measurement_gate_time_raw(self) -> str:
        return self.query_best_effort("RCG")

    def set_measurement_coupling(self, coupling_mode: int) -> None:
        """
        Protocolo FY2300:
        WCC0 = DC coupling
        WCC1 = AC coupling
        """
        if coupling_mode not in (self.COUPLING_DC, self.COUPLING_AC):
            raise ValueError("coupling_mode inválido")
        self.write_only(f"WCC{coupling_mode}")

    # -------------------------
    # Sweep
    # -------------------------
    def set_sweep_object(self, obj_mode: int) -> None:
        if obj_mode not in (
            self.SWEEP_OBJ_FREQUENCY,
            self.SWEEP_OBJ_AMPLITUDE,
            self.SWEEP_OBJ_OFFSET,
            self.SWEEP_OBJ_DUTY,
        ):
            raise ValueError("obj_mode inválido")
        self.write_only(f"SOB{obj_mode}")

    def set_sweep_start(self, value: float, obj_mode: int) -> None:
        if obj_mode == self.SWEEP_OBJ_FREQUENCY:
            self.write_only(f"SST{value:.2f}")
        elif obj_mode in (self.SWEEP_OBJ_AMPLITUDE, self.SWEEP_OBJ_OFFSET):
            self.write_only(f"SST{value:.2f}")
        elif obj_mode == self.SWEEP_OBJ_DUTY:
            self.write_only(f"SST{value:.1f}")
        else:
            raise ValueError("obj_mode inválido")

    def set_sweep_end(self, value: float, obj_mode: int) -> None:
        if obj_mode == self.SWEEP_OBJ_FREQUENCY:
            self.write_only(f"SEN{value:.2f}")
        elif obj_mode in (self.SWEEP_OBJ_AMPLITUDE, self.SWEEP_OBJ_OFFSET):
            self.write_only(f"SEN{value:.2f}")
        elif obj_mode == self.SWEEP_OBJ_DUTY:
            self.write_only(f"SEN{value:.1f}")
        else:
            raise ValueError("obj_mode inválido")

    def set_sweep_time_s(self, sweep_time_s: float) -> None:
        if not (0.01 <= sweep_time_s <= 999.99):
            raise ValueError("sweep_time_s debe estar entre 0.01 y 999.99")
        self.write_only(f"STI{sweep_time_s:.2f}")

    def set_sweep_mode(self, mode: int) -> None:
        if mode not in (self.SWEEP_LINEAR, self.SWEEP_LOG):
            raise ValueError("mode inválido")
        self.write_only(f"SMO{mode}")

    def set_sweep_enabled(self, enabled: bool) -> None:
        self.write_only(f"SBE{1 if enabled else 0}")

    # -------------------------
    # Save / Load / Sync
    # -------------------------
    def save_to_slot(self, slot: int) -> None:
        if not (1 <= slot <= 20):
            raise ValueError("slot debe estar entre 1 y 20")
        self.write_only(f"USN{slot:02d}")

    def load_from_slot(self, slot: int) -> None:
        if not (1 <= slot <= 20):
            raise ValueError("slot debe estar entre 1 y 20")
        self.write_only(f"ULN{slot:02d}")

    def enable_sync(self, sync_mode: int) -> None:
        if sync_mode not in (0, 1, 2, 3, 4):
            raise ValueError("sync_mode inválido")
        self.write_only(f"USA{sync_mode}")

    def disable_sync(self, sync_mode: int) -> None:
        if sync_mode not in (0, 1, 2, 3, 4):
            raise ValueError("sync_mode inválido")
        self.write_only(f"USD{sync_mode}")

    # -------------------------
    # Arbitraria:
    # -------------------------   
    def _pack_raw14_split(self, raw_values):
        data = bytearray()
        for v in raw_values:
            iv = int(v) & 0x3FFF
            data.append(iv & 0xFF)
            data.append((iv >> 8) & 0x3F)
        return data

    def _pack_u16_le(self, raw_values):
        data = bytearray()
        for v in raw_values:
            iv = int(v) & 0xFFFF
            data.append(iv & 0xFF)
            data.append((iv >> 8) & 0xFF)
        return data

    def _pack_u16_be(self, raw_values):
        data = bytearray()
        for v in raw_values:
            iv = int(v) & 0xFFFF
            data.append((iv >> 8) & 0xFF)
            data.append(iv & 0xFF)
        return data

    def _pack_u8(self, raw_values):
        data = bytearray()
        for v in raw_values:
            iv = int(round((int(v) & 0x0FFF) * 255.0 / 4095.0)) & 0xFF
            data.append(iv)
        return data

    def _convert_values_to_raw12(
        self,
        values,
        min_value=-1.0,
        max_value=1.0,
        value_count=2048,
    ):
        """
        Convierte una waveform float a códigos crudos de 12 bits [0..4095].

        Para la serie FY2300, el manual indica:
        - 16 posiciones de user-defined waveform
        - longitud de cada waveform = 2048 puntos
        - resolución vertical = 12 bits
        """
        arr = np.asarray(values, dtype=np.float64)

        if arr.ndim != 1:
            raise ValueError("La waveform debe ser un vector 1D.")

        if len(arr) != value_count:
            raise ValueError(
                f"La waveform debe tener exactamente {value_count} puntos, no {len(arr)}."
            )

        if np.isclose(max_value, min_value):
            raise ValueError("Rango inválido para normalización.")

        norm = (arr - min_value) / (max_value - min_value)
        norm = np.clip(norm, 0.0, 1.0)

        raw = np.round(norm * 4095.0).astype(np.uint16)
        return raw
    
    def _convert_values_to_raw12_signed(
        self,
        values,
        min_value=-1.0,
        max_value=1.0,
        value_count=2048,
    ):
        """
        Convierte una waveform float a enteros signed de 12 bits en rango [-2048, 2047].
        Luego se almacenarán en complemento a dos dentro de un uint16.
        """
        arr = np.asarray(values, dtype=np.float64)

        if arr.ndim != 1:
            raise ValueError("La waveform debe ser un vector 1D.")

        if len(arr) != value_count:
            raise ValueError(
                f"La waveform debe tener exactamente {value_count} puntos, no {len(arr)}."
            )

        if np.isclose(max_value, min_value):
            raise ValueError("Rango inválido para normalización.")

        # Normalizar a [-1, 1]
        mid = 0.5 * (max_value + min_value)
        half = 0.5 * (max_value - min_value)
        norm = (arr - mid) / half
        norm = np.clip(norm, -1.0, 1.0)

        # Mapear a signed 12-bit
        raw_signed = np.round(norm * 2047.0).astype(np.int16)
        raw_signed = np.clip(raw_signed, -2048, 2047)

        return raw_signed


    def _pack_raw12_u16_le(self, raw_values):
        """
        Empaca cada muestra de 12 bits en 16 bits little-endian.

        Se almacenan los 12 bits útiles en un uint16:
        - byte bajo
        - byte alto
        """
        data = bytearray()

        for v in raw_values:
            iv = int(v) & 0x0FFF
            data.append(iv & 0xFF)         # byte bajo
            data.append((iv >> 8) & 0xFF)  # byte alto

        return data
    
    def _pack_raw12_u16_be(self, raw_values):
        """
        Empaca cada muestra de 12 bits en 16 bits big-endian.
        """
        data = bytearray()

        for v in raw_values:
            iv = int(v) & 0x0FFF
            data.append((iv >> 8) & 0xFF)  # byte alto
            data.append(iv & 0xFF)         # byte bajo

        return data


    def _pack_raw12_packed_le(self, raw_values):
        """
        Empaca muestras de 12 bits contiguas:
        cada 2 muestras -> 3 bytes

        Convención inicial:
        a = muestra 0..4095
        b = muestra 0..4095

        byte0 = a[7:0]
        byte1 = a[11:8] | b[3:0] << 4
        byte2 = b[11:4]
        """
        data = bytearray()

        if len(raw_values) % 2 != 0:
            raise ValueError("raw_values debe tener cantidad par de muestras")

        for i in range(0, len(raw_values), 2):
            a = int(raw_values[i]) & 0x0FFF
            b = int(raw_values[i + 1]) & 0x0FFF

            byte0 = a & 0xFF
            byte1 = ((a >> 8) & 0x0F) | ((b & 0x0F) << 4)
            byte2 = (b >> 4) & 0xFF

            data.append(byte0)
            data.append(byte1)
            data.append(byte2)

        return data
    
    def _pack_raw12_packed_le_alt(self, raw_values):
        """
        Variante alternativa de packing 12-bit contiguo:
        byte0 = a[11:4]
        byte1 = a[3:0] << 4 | b[11:8]
        byte2 = b[7:0]
        """
        data = bytearray()

        if len(raw_values) % 2 != 0:
            raise ValueError("raw_values debe tener cantidad par de muestras")

        for i in range(0, len(raw_values), 2):
            a = int(raw_values[i]) & 0x0FFF
            b = int(raw_values[i + 1]) & 0x0FFF

            byte0 = (a >> 4) & 0xFF
            byte1 = ((a & 0x0F) << 4) | ((b >> 8) & 0x0F)
            byte2 = b & 0xFF

            data.append(byte0)
            data.append(byte1)
            data.append(byte2)

        return data


    def _pack_raw12_signed_u16_le(self, raw_values):
        """
        Empaca signed 12-bit two's complement en 16 bits little-endian.
        """
        data = bytearray()

        for v in raw_values:
            iv = int(v)
            if iv < 0:
                iv = (1 << 12) + iv   # complemento a dos de 12 bits

            iv &= 0x0FFF
            data.append(iv & 0xFF)         # byte bajo
            data.append((iv >> 8) & 0xFF)  # byte alto

        return data
    
    def upload_waveform(
        self,
        waveform_index: int,
        values,
        min_value: float = -1.0,
        max_value: float = 1.0,
        value_count: int = 2048,
        pack_mode: str = "raw12_u16_be",
    ):
        if not (1 <= waveform_index <= 16):
            raise ValueError("waveform_index debe estar entre 1 y 16.")

        if pack_mode == "raw12_u16_le":
            raw = self._convert_values_to_raw12(
                values,
                min_value=min_value,
                max_value=max_value,
                value_count=value_count,
            )
            payload = self._pack_raw12_u16_le(raw)
        elif pack_mode == "raw12_u16_be":
            raw = self._convert_values_to_raw12(
                values,
                min_value=min_value,
                max_value=max_value,
                value_count=value_count,
            )
            payload = self._pack_raw12_u16_be(raw)
        elif pack_mode == "raw12_signed_u16_le":
            raw = self._convert_values_to_raw12_signed(
                values,
                min_value=min_value,
                max_value=max_value,
                value_count=value_count,
            )
            payload = self._pack_raw12_signed_u16_le(raw)

        elif pack_mode == "raw12_packed_le":
            raw = self._convert_values_to_raw12(
                values,
                min_value=min_value,
                max_value=max_value,
                value_count=value_count,
            )
            payload = self._pack_raw12_packed_le(raw)

        elif pack_mode == "raw12_packed_le_alt":
            raw = self._convert_values_to_raw12(
                values,
                min_value=min_value,
                max_value=max_value,
                value_count=value_count,
            )
            payload = self._pack_raw12_packed_le_alt(raw)

        elif pack_mode == "u16_le":
            raw = self._convert_values_to_raw12(
                values,
                min_value=min_value,
                max_value=max_value,
                value_count=value_count,
            )
            payload = self._pack_u16_le(raw)

        elif pack_mode == "u16_be":
            raw = self._convert_values_to_raw12(
                values,
                min_value=min_value,
                max_value=max_value,
                value_count=value_count,
            )
            payload = self._pack_u16_be(raw)

        elif pack_mode == "u8":
            raw = self._convert_values_to_raw12(
                values,
                min_value=min_value,
                max_value=max_value,
                value_count=value_count,
            )
            payload = self._pack_u8(raw)

        elif pack_mode == "raw14_split":
            raw = self._convert_values_to_raw12(
                values,
                min_value=min_value,
                max_value=max_value,
                value_count=value_count,
            )
            payload = self._pack_raw14_split(raw)

        else:
            raise ValueError(f"pack_mode no soportado: {pack_mode}")

        self.set_output(False)
        self.set_wave_builtin("sin")
        time.sleep(0.1)

        cmd = f"DDS_WAVE{waveform_index}"
        self._write_ascii_once(cmd)

        ack1 = self._read_ack(wait_s=1.2, expected="W")
        if self.debug:
            print(f"ACK1 DDS_WAVE = {ack1!r}")

        if ack1 != "W":
            raise FY2300Error(
                f"DDS_WAVE{waveform_index} no fue reconocido por el equipo. "
                f"ACK recibido: {ack1!r}"
            )

        self.ser.write(payload)
        self.ser.flush()

        ack2 = self._read_ack(wait_s=2.0, expected="HN")
        if self.debug:
            print(f"ACK2 DATA = {ack2!r}")

        if "HN" not in ack2:
            raise FY2300Error(
                f"La data arbitraria no fue aceptada. ACK final: {ack2!r}"
            )

        return {
            "waveform_index": waveform_index,
            "points": len(raw),
            "payload_bytes": len(payload),
            "pack_mode": pack_mode,
            "min_code": int(raw.min()),
            "max_code": int(raw.max()),
            "ack_start": ack1,
            "ack_end": ack2,
        }
    


    def configure_echo_mode_main_channel(
        self,
        frequency_hz: float,
        amplitude_vpp: float,
        offset_v: float,
        arb_index: int = 1,
        output_on: bool = True,
    ):
        """
        Configura el canal principal para reproducir la arbitraria cargada.
        """
        self.set_arb_slot(arb_index)
        self.set_frequency_hz(frequency_hz)
        self.set_amplitude_vpp(amplitude_vpp)
        self.set_offset_v(offset_v)
        self.set_output(output_on)