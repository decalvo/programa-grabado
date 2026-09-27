import numpy as np
from PIL import Image

from grabado.proceso import Ajustes, procesar, tamano_final_px
from grabado.simulacion import COLOR_FONDO, MADERA, PALETA, dpi_para_caja, simular
from grabado.tonal import Capa


def foto_degradado(ancho=256, alto=60):
    return Image.fromarray(np.tile(np.arange(ancho, dtype=np.uint8), (alto, 1)), "L")


def colores(imagen):
    return {tuple(c) for c in np.asarray(imagen).reshape(-1, 3)}


def test_cada_punto_grabado_tiene_el_cafe_de_su_capa():
    resultado = procesar(foto_degradado(), Ajustes(ancho_mm=256 / 10, dpi=254))
    pixeles = np.asarray(simular(resultado))
    for capa, puntos in resultado.capas.items():
        assert puntos.any()
        assert (pixeles[puntos] == PALETA[capa]).all()


def test_claro_y_huecos_del_tramado_quedan_como_madera():
    resultado = procesar(foto_degradado(), Ajustes(ancho_mm=256 / 10, dpi=254))
    pixeles = np.asarray(simular(resultado))
    sin_grabar = ~np.logical_or.reduce(list(resultado.capas.values()))
    assert (pixeles[sin_grabar] == MADERA).all()
    assert (pixeles[resultado.etiquetas == Capa.CLARO] == MADERA).all()
    # El tramado deja huecos dentro de las capas grabadas, no solo en Claro.
    assert (sin_grabar & (resultado.etiquetas == Capa.MEDIO)).any()


def test_el_fondo_se_distingue_de_la_madera():
    foto = foto_degradado()
    mascara = Image.new("L", foto.size, 0)
    mascara.paste(255, (40, 0, 200, foto.height))
    resultado = procesar(foto, Ajustes(ancho_mm=256 / 10, dpi=254), mascara)
    pixeles = np.asarray(simular(resultado))
    assert (pixeles[~resultado.mascara] == COLOR_FONDO).all()
    assert colores(simular(resultado)) == {COLOR_FONDO, MADERA, *PALETA.values()}


def test_sin_mascara_no_aparece_el_fondo():
    resultado = procesar(foto_degradado(), Ajustes(ancho_mm=256 / 10, dpi=254))
    assert COLOR_FONDO not in colores(simular(resultado))


def test_la_imagen_tiene_el_tamano_del_resultado():
    resultado = procesar(foto_degradado(), Ajustes(ancho_mm=20, dpi=100))
    alto, ancho = resultado.gris.shape
    assert simular(resultado).size == (ancho, alto)


def test_dpi_para_caja_cabe_en_la_caja_y_no_pasa_del_de_exportacion():
    origen = (3000, 4000)  # foto vertical
    dpi = dpi_para_caja(origen, 100, 254, (800, 600))
    ancho, alto = tamano_final_px(origen, 100, dpi)
    assert ancho <= 800 and alto <= 600
    assert alto > 550  # usa casi toda la caja
    assert dpi_para_caja(origen, 100, 254, (5000, 5000)) == 254


def test_cortes_automaticos_casi_no_dependen_de_la_resolucion():
    rng = np.random.default_rng(0)
    base = rng.normal(120, 50, (300, 400)).clip(0, 255).astype(np.uint8)
    foto = Image.fromarray(base, "L").resize((1600, 1200), Image.Resampling.BICUBIC)
    completo = procesar(foto, Ajustes(ancho_mm=100, dpi=254)).cortes
    reducido = procesar(foto, Ajustes(ancho_mm=100, dpi=dpi_para_caja(foto.size, 100, 254, (500, 500)))).cortes
    assert np.allclose(completo, reducido, atol=2)
