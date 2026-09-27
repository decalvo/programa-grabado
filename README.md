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
2. **Eliminar fondo** (opcional): la IA local recorta al sujeto (personas o mascota) y el fondo se ve como un damero gris; el fondo queda blanco (sin grabar) en todos los BMP. Tarda unos 20 s por foto. La primera vez descarga el modelo (224 MB) a `%LOCALAPPDATA%\ProgramaGrabado\modelos`; después funciona sin internet. Usa la GPU (DirectML) si puede y si no la CPU.
3. En el panel **Ajustes previos** (opcional), realza el sujeto antes de separarlo en capas: **Auto-mejorar** estira sus tonos a casi toda la gama y le da un poco de nitidez, y deja los deslizadores **Brillo**, **Contraste** y **Nitidez** en esos valores para afinarlos; **Neutro** los vuelve a 0. Con los cortes automáticos, que siempre reparten el sujeto en cuatro partes iguales, el brillo y el contraste se notan sobre todo en lo denso de la capa Negro; con cortes elegidos a mano mueven píxeles de una capa a otra.
4. En el panel **Cortes tonales**, mueve los deslizadores Negro/Oscuro, Oscuro/Medio y Medio/Claro mirando la pestaña **Vista previa**, que simula el tramado de cada capa en tonos de café sobre madera (el fondo se ve en gris). Parten del reparto automático; **Automático** vuelve a él.
5. En el panel **Tramado**, elige el tipo: Jarvis (por defecto), Floyd-Steinberg, Stucki o Semitono (puntos agrupados en una cuadrícula a 45°, pensada para 254 DPI: un punto cada 0,57 mm).
6. En el panel **Exportar**, escribe el ancho final en mm y la resolución (254 DPI = intervalo de 0,1 mm).
7. **Exportar capas…** y elige una carpeta. Se crean `*_1_negro.bmp`, `*_2_oscuro.bmp`, `*_3_medio.bmp` y `*_medidas.txt` con las medidas y los pasos para RDWorks.

### Plantilla de calibración

Antes de grabar una foto en una madera nueva, graba la plantilla para elegir la potencia de cada capa tonal:

1. Elige la resolución en el panel **Exportar** y el tipo en el panel **Tramado**; no hace falta abrir una foto.
2. **Plantilla de calibración…** en la barra superior y elige una carpeta. Se crean `calibracion_1.bmp` … `calibracion_8.bmp` (un cuadro tramado de 15 × 15 mm con su número, todos en el mismo lienzo) y `calibracion_potencias.txt` con la potencia sugerida de cada cuadro (del 10 % al 80 %) y los pasos para RDWorks.
3. En RDWorks importa los 8 BMP en la misma posición X/Y, asigna a cada uno su color y su potencia, y graba.
4. Mira qué cuadro da el café que quieres para Negro, Oscuro y Medio y usa esas potencias.

## Pruebas

```
.venv\Scripts\python -m pytest
```

La prueba con el modelo de IA real es lenta y se salta por defecto; para correrla (con el modelo ya descargado): `$env:GRABADO_PRUEBAS_LENTAS="1"` antes de `pytest`.
