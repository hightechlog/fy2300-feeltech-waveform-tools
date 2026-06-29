# FeelTech FY2300 20M Arbitrary Waveform Tools

Herramientas en Python para trabajar con el generador de funciones/arbitrario **FeelTech FY2300 20M**.

Este proyecto reúne dos piezas principales:

1. **`fy2300_serial.py`**  
   Biblioteca Python para controlar el FY2300 por puerto serie mediante comandos ASCII confirmados con hardware real.

2. **`fy2300_gui_simple_v3.py`**  
   Interfaz gráfica simple en Tkinter para:
   - configurar ondas comunes,
   - ajustar frecuencia, amplitud, offset y duty cycle,
   - seleccionar atenuación 0 dB / 20 dB,
   - cargar una forma arbitraria desde un CSV de osciloscopio,
   - enviar la forma al FY2300 usando `arb2`.

También incluye:

- **`EMISION_SintReal_fy2300_RUIDO.py`**: ejemplo funcional que toma un segmento real de `SDS00004.csv`, le añade ruido blanco controlado y lo carga como forma arbitraria.

---

## Motivación

Al trabajar con repositorios existentes para equipos FeelTech, detectamos que el envío de datos para formas arbitrarias no resolvía correctamente nuestro caso de uso para el **FY2300 20M**, especialmente al intentar reproducir una forma de onda real medida en osciloscopio.

Por ello se construyó una biblioteca específica orientada al flujo que sí funcionó en pruebas reales:

- carga de forma arbitraria con `upload_waveform(...)`,
- reproducción mediante `arb2`,
- control de frecuencia, amplitud, offset, duty y atenuación desde Python,
- y una GUI simple para que otros usuarios puedan reutilizar la herramienta sin editar código.

---

## Archivos incluidos

- `fy2300_serial.py`
- `fy2300_gui_simple_v3.py`
- `EMISION_SintReal_fy2300_RUIDO.py`

---

## Requisitos

- Python 3.10+
- `numpy`
- `matplotlib`
- `pyserial`

Instalación:

```bash
pip install -r requirements.txt
```

---

## Uso rápido

### 1) GUI

```bash
python fy2300_gui_simple_v3.py
```

La GUI permite:

- probar conexión con el puerto COM,
- configurar una onda común en el canal principal (CH1),
- cargar un segmento desde un archivo CSV Siglent/Tektronix compatible,
- enviarlo como `arb2`,
- y previsualizar localmente la señal antes de transmitir.

### 2) Ejemplo con waveform real

```bash
python EMISION_SintReal_fy2300_RUIDO.py
```

Este script:

- lee `SDS00004.csv`,
- extrae un segmento temporal,
- lo adapta a 2048 puntos,
- añade ruido blanco leve,
- y lo envía como forma arbitraria al FY2300.

---

## Notas importantes

- La implementación actual está enfocada en el **canal principal (CH1)**.
- La atenuación del equipo influye directamente en la amplitud observada.  
  Se recomienda verificar explícitamente si el generador está en **0 dB** o **20 dB**.
- La librería fue desarrollada para una ruta funcional específica validada en laboratorio, no como wrapper universal para todos los modelos FeelTech.

---

## Estructura sugerida para futuras mejoras

- soporte formal para CH2,
- presets guardables desde la GUI,
- lectura de parámetros actuales del equipo,
- empaquetado como módulo instalable,
- pruebas automatizadas con hardware en banco.

---

## Licencia

Se incluye una licencia MIT como punto de partida para publicación abierta.  
Si prefieres otra licencia para el repositorio público, cámbiala antes de publicar.
