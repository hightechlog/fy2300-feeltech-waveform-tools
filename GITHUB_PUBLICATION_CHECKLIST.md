# Checklist de publicación del repo GitHub

## Nombre del repositorio
- `fy2300-feeltech-waveform-tools`

## Visibilidad
- Public

## Descripción sugerida
- Python tools and a simple GUI for the FeelTech FY2300 20M, including arbitrary waveform upload from real oscilloscope CSV data.

## Archivos mínimos a subir
- README.md
- LICENSE
- requirements.txt
- .gitignore
- fy2300_serial.py
- fy2300_gui_simple_v3.py
- EMISION_SintReal_fy2300_RUIDO.py

## Archivos opcionales recomendados
- BLOG_POST_HIGHTECHLOG.md
- imágenes/capturas de la GUI
- notas de validación con hardware

## Archivos que NO conviene subir
- CSV grandes de prueba si contienen datos internos
- builds locales
- entornos virtuales
- archivos temporales del IDE

## Primer release sugerido
- tag: `v0.1.0`
- mensaje: `Initial public release: FY2300 serial library, GUI, and arbitrary waveform example`

## Pendientes después de publicar
- agregar capturas de pantalla de la GUI
- documentar caso de uso con CSV real
- documentar limitación actual de CH2
- añadir ejemplos de seno, cuadrada y arb2
