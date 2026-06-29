# Control del generador FeelTech FY2300 20M con Python: librería propia, GUI simple y carga de formas arbitrarias reales

En este proyecto trabajamos con el generador **FeelTech FY2300 20M** y construimos un conjunto de herramientas en Python para resolver una necesidad muy concreta: **cargar y reproducir formas de onda arbitrarias reales medidas con osciloscopio**, además de exponer una interfaz simple para que cualquier usuario pueda reutilizar el flujo sin editar código manualmente.

## El problema

Existen repositorios públicos para controlar generadores FeelTech desde Python, y varios de ellos resultan útiles para funciones comunes. Sin embargo, en nuestro caso apareció un problema práctico al momento de **enviar datos al generador para reproducción arbitraria**.

La meta no era solamente activar una senoide o una cuadrada, sino lograr que el equipo reprodujera una forma medida experimentalmente, por ejemplo un segmento real tomado desde un archivo CSV del osciloscopio. Para ese flujo, los repositorios disponibles no resolvían correctamente nuestro escenario de trabajo con el **FY2300 20M**, así que desarrollamos una ruta propia orientada al comportamiento real del equipo en laboratorio.

## Qué construimos

El proyecto quedó formado por tres piezas principales:

- una biblioteca propia en Python para el FY2300,
- un script funcional para cargar formas arbitrarias reales,
- y una interfaz gráfica simple en Tkinter.

Con ello ya es posible:

- leer un CSV del osciloscopio,
- extraer un segmento temporal,
- ajustarlo al número de puntos aceptado por el generador,
- añadir ruido blanco opcional,
- cargarlo como forma arbitraria,
- y reproducirlo desde el equipo.

## La biblioteca `fy2300_serial.py`

La biblioteca propia expone funciones directas para trabajar con el generador:

- selección de formas integradas,
- frecuencia,
- amplitud,
- offset,
- duty cycle,
- atenuación,
- trigger,
- y carga de formas arbitrarias.

Esto permitió construir una solución enfocada específicamente al **FeelTech FY2300 20M**, usando el flujo que sí funcionó en pruebas reales.

## La GUI simple

Después de validar el flujo con scripts, el siguiente paso fue construir una GUI para simplificar el uso.

La interfaz permite:

- probar conexión con el puerto COM,
- configurar ondas comunes,
- ajustar frecuencia, amplitud, offset y duty cycle,
- seleccionar atenuación 0 dB / 20 dB,
- cargar un segmento desde un CSV,
- previsualizar localmente la señal,
- y enviarla al generador como `arb2`.

La idea es que cualquier usuario pueda aprovechar la herramienta sin tener que modificar el código base.

## Por qué puede ser útil

Este proyecto puede ser útil si trabajas con:

- instrumentación electrónica,
- generación de señales arbitrarias,
- automatización de laboratorio,
- síntesis de señales reales medidas,
- o pruebas con generadores FeelTech desde Python.

Especialmente si quieres ir más allá del uso básico de senoides y cuadradas, y reproducir una señal experimental real en el generador.

## Repositorio público

El proyecto fue preparado para publicarse como repositorio abierto en GitHub, incluyendo:

- la biblioteca,
- la GUI,
- el script funcional de ejemplo,
- documentación base,
- y dependencias mínimas.

La intención es que otros usuarios puedan reutilizarlo, adaptarlo y extenderlo.

## Cierre

No se trató de reemplazar todos los repositorios existentes, sino de resolver un caso específico que sí funcionara de manera reproducible con el **FeelTech FY2300 20M**, en particular para el envío de formas arbitrarias reales.

En siguientes entradas iré documentando con más detalle:

- la estructura interna de la biblioteca,
- el formato de la waveform,
- y pruebas prácticas con señales reales.
