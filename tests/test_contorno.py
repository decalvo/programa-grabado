import numpy as np
import pytest
from PIL import Image
from scipy import ndimage

from grabado import contorno
from grabado.exportar import exportar
from grabado.proceso import Ajustes, procesar
from grabado.simulacion import COLOR_CONTORNO, simular


def circulo(lado=400, radio=120):
    y, x = np.mgrid[:lado, :lado]
    return (x - lado / 2) ** 2 + (y - lado / 2) ** 2 <= radio**2


def foto_con_mascara(ancho=300, alto=200):
    fila = np.linspace(0, 255, ancho).astype(np.uint8)
    foto = Image.fromarray(np.tile(fila, (alto, 1)), "L").convert("RGB")
    mascara = Image.new("L", foto.size, 0)
    mascara.paste(255, (60, 40, 240, 160))
    return foto, mascara


@pytest.mark.parametrize(("mm", "dpi", "px"), [(1.0, 254, 10), (1.0, 100, 4), (2.5, 254, 25), (0.05, 100, 1)])
def test_grosor_en_pixeles_es_mm_por_dpi(mm, dpi, px):
    assert contorno.grosor_px(mm, dpi) == px


@pytest.mark.parametrize("grosor", [1, 4, 10])
def test_la_linea_tiene_el_grosor_pedido(grosor):
    mascara = circulo()
    linea, _ = contorno.calcular(mascara, grosor)
    # En la fila del centro la lÃ­nea cruza el cÃ­rculo dos veces, cada una de `grosor` pÃ­xeles.
    fila = linea[200]
    assert fila.sum() == 2 * grosor
    columna = linea[:, 200]
    assert columna.sum() == 2 * grosor


def test_la_linea_va_por_dentro_y_solo_cerca_del_borde():
    mascara = circulo()
    grosor = 10
    linea, _ = contorno.calcular(mascara, grosor)
    assert linea.any()
    # Distancia de cada pÃ­xel al borde del sujeto (por dentro o por fuera).
    al_borde = np.minimum(ndimage.distance_transform_edt(mascara), ndimage.distance_transform_edt(~mascara))
    assert al_borde[linea].max() <= grosor + 1
    # Por dentro: casi nada fuera del sujeto (solo lo que mueve el suavizado del borde).
    assert (linea & ~mascara).sum() <= 0.01 * linea.sum()
    # El interior del sujeto queda libre.
    assert not linea[ndimage.distance_transform_edt(mascara) > grosor + 2].any()


def test_el_borde_dentado_se_suaviza():
    # Una escalera de dientes de 2 px a lo largo de un borde recto.
    mascara = np.zeros((200, 200), bool)
    mascara[:, :100] = True
    mascara[::4, 100:102] = True
    mascara[1::4, 100:102] = True
    linea, _ = contorno.calcular(mascara, 10)
    extremo = [np.flatnonzero(fila).max() for fila in linea[20:180]]
    assert max(extremo) - min(extremo) <= 1


def test_el_interior_queda_dentro_de_la_linea():
    # Un pelito de 1 px sale del sujeto: el suavizado lo borra y no queda ni en la línea ni en el interior.
    mascara = circulo()
    mascara[200, 320:380] = True
    linea, interior = contorno.calcular(mascara, 6)
    assert not (linea & interior).any()
    assert not (linea | interior)[200, 330:].any()
    # Lo que queda dentro está rodeado por la línea.
    assert not interior[ndimage.distance_transform_edt(mascara) <= 3].any()
    assert interior[200, 200]


def test_sin_linea_en_el_borde_del_lienzo():
    mascara = np.zeros((100, 100), bool)
    mascara[40:, :] = True  # el sujeto llega a los bordes izquierdo, derecho e inferior
    linea, _ = contorno.calcular(mascara, 5)
    assert linea[38:47].any()
    assert not linea[50:].any()
    assert not contorno.calcular(np.ones((50, 50), bool), 5)[0].any()
    assert not contorno.calcular(np.zeros((50, 50), bool), 5)[0].any()


def test_desactivado_por_defecto_y_sin_cambios():
    foto, mascara = foto_con_mascara()
    assert Ajustes().contorno is False
    assert Ajustes().grosor_contorno_mm == 1.0
    assert procesar(foto, Ajustes(ancho_mm=30, dpi=254), mascara).contorno is None


def test_sin_recorte_no_hay_contorno():
    foto, _ = foto_con_mascara()
    assert procesar(foto, Ajustes(ancho_mm=30, dpi=254, contorno=True)).contorno is None


def test_las_capas_no_tienen_puntos_bajo_el_contorno():
    foto, mascara = foto_con_mascara()
    sin = procesar(foto, Ajustes(ancho_mm=30, dpi=254), mascara)
    con = procesar(foto, Ajustes(ancho_mm=30, dpi=254, contorno=True), mascara)
    linea = con.contorno
    assert linea.any()
    for capa, puntos in con.capas.items():
        assert not (puntos & linea).any()
        # Dentro del contorno las capas no cambian.
        dentro = ndimage.distance_transform_edt(con.mascara) > 12
        assert (puntos[dentro] == sin.capas[capa][dentro]).all()


def test_el_contorno_sigue_la_mascara_a_la_resolucion_final():
    foto, mascara = foto_con_mascara()
    resultado = procesar(foto, Ajustes(ancho_mm=30, dpi=254, contorno=True, grosor_contorno_mm=1.0), mascara)
    alto, ancho = resultado.gris.shape
    assert resultado.contorno.shape == (alto, ancho)
    # El rectÃ¡ngulo del sujeto ocupa de x=60 a 240 de 300; a la resoluciÃ³n final, un 60 % del ancho.
    fila = resultado.contorno[alto // 2]
    assert fila.sum() == 2 * 10
    assert abs(np.flatnonzero(fila).min() - 0.2 * ancho) <= 2


def test_exporta_el_bmp_del_contorno_solo_si_esta_activado(tmp_path):
    foto, mascara = foto_con_mascara()
    sin = exportar(procesar(foto, Ajustes(ancho_mm=30, dpi=254), mascara), tmp_path / "desactivado", "foto")
    assert not any("contorno" in a.name for a in sin)
    assert "contorno" not in (tmp_path / "desactivado" / "foto_medidas.txt").read_text(encoding="utf-8")

    resultado = procesar(foto, Ajustes(ancho_mm=30, dpi=254, contorno=True), mascara)
    archivos = exportar(resultado, tmp_path / "activado", "foto")
    bmps = [a for a in archivos if a.suffix == ".bmp"]
    assert bmps[-1].name == "foto_4_contorno.bmp"
    tamanos = set()
    for ruta in bmps:
        with Image.open(ruta) as imagen:
            assert imagen.mode == "1"
            assert round(imagen.info["dpi"][0]) == 254
            tamanos.add(imagen.size)
    assert len(tamanos) == 1
    with Image.open(bmps[-1]) as imagen:
        assert ((np.asarray(imagen.convert("L")) == 0) == resultado.contorno).all()
    assert "foto_4_contorno.bmp" in (tmp_path / "activado" / "foto_medidas.txt").read_text(encoding="utf-8")


def test_la_vista_previa_muestra_el_contorno():
    foto, mascara = foto_con_mascara()
    resultado = procesar(foto, Ajustes(ancho_mm=30, dpi=254, contorno=True), mascara)
    pixeles = np.asarray(simular(resultado))
    assert (pixeles[resultado.contorno] == COLOR_CONTORNO).all()
    assert not (pixeles[~resultado.contorno] == COLOR_CONTORNO).all(axis=-1).any()


def test_en_la_vista_previa_el_grosor_se_escala_con_el_dpi():
    foto, mascara = foto_con_mascara()
    reducido = procesar(foto, Ajustes(ancho_mm=30, dpi=127, contorno=True, grosor_contorno_mm=2.0), mascara)
    alto = reducido.gris.shape[0]
    assert reducido.contorno[alto // 2].sum() == 2 * 10
