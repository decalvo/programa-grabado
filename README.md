# Programa grabado

Prepara fotos para grabado láser CO2 sobre madera: separa la foto en capas tonales tramadas y las exporta como BMP de 1 bit para asignar a cada una su potencia en RDWorks. El vocabulario del proyecto está en [CONTEXT.md](CONTEXT.md).

## Instalar

Requiere Python 3.12 o superior y el paquete Microsoft Visual C++ Redistributable.

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Usar

```
.venv\Scripts\python -m grabado
```

1. **Abrir foto…** en la barra superior.
2. En el panel **Exportar**, escribe el ancho final en mm y la resolución (254 DPI = intervalo de 0,1 mm).
3. **Exportar capas…** y elige una carpeta. Se crean `*_1_negro.bmp`, `*_2_oscuro.bmp`, `*_3_medio.bmp` y `*_medidas.txt` con las medidas y los pasos para RDWorks.

### Plantilla de calibración

Antes de grabar una foto en una madera nueva, graba la plantilla para elegir la potencia de cada capa tonal:

1. Elige la resolución (y el tramado) en el panel **Exportar**; no hace falta abrir una foto.
2. **Plantilla de calibración…** en la barra superior y elige una carpeta. Se crean `calibracion_1.bmp` … `calibracion_8.bmp` (un cuadro tramado de 15 × 15 mm con su número, todos en el mismo lienzo) y `calibracion_potencias.txt` con la potencia sugerida de cada cuadro (del 10 % al 80 %) y los pasos para RDWorks.
3. En RDWorks importa los 8 BMP en la misma posición X/Y, asigna a cada uno su color y su potencia, y graba.
4. Mira qué cuadro da el café que quieres para Negro, Oscuro y Medio y usa esas potencias.

## Pruebas

```
.venv\Scripts\python -m pytest
```
