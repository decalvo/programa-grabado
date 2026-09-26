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
2. En el panel **Cortes tonales**, mueve los deslizadores Negro/Oscuro, Oscuro/Medio y Medio/Claro mirando la pestaña **Vista previa**, que simula el tramado de cada capa en tonos de café sobre madera (el fondo se ve en gris). Parten del reparto automático; **Automático** vuelve a él.
3. En el panel **Exportar**, escribe el ancho final en mm y la resolución (254 DPI = intervalo de 0,1 mm).
4. **Exportar capas…** y elige una carpeta. Se crean `*_1_negro.bmp`, `*_2_oscuro.bmp`, `*_3_medio.bmp` y `*_medidas.txt` con las medidas y los pasos para RDWorks.

## Pruebas

```
.venv\Scripts\python -m pytest
```
