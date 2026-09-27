import numpy as np

from grabado.tonal import FONDO, Capa, cortes_automaticos, separar


def degradado(alto=40, ancho=256):
    return np.tile(np.arange(ancho, dtype=np.float32), (alto, 1))


def test_cortes_automaticos_reparten_por_cantidad():
    gris = degradado()
    cortes = cortes_automaticos(gris)
    etiquetas = separar(gris, cortes)
    for capa in Capa:
        assert abs((etiquetas == capa).mean() - 0.25) < 0.01


def test_foto_oscura_usa_las_cuatro_capas():
    gris = degradado() * 0.3  # todo entre 0 y 77
    etiquetas = separar(gris, cortes_automaticos(gris))
    assert all((etiquetas == capa).any() for capa in Capa)


def test_cortes_solo_miran_el_sujeto():
    gris = degradado()
    mascara = gris < 128
    c1, c2, c3 = cortes_automaticos(gris, mascara)
    assert c3 < 128


def test_cada_pixel_en_una_sola_capa_y_fondo_aparte():
    gris = degradado()
    mascara = np.zeros(gris.shape, bool)
    mascara[:, 50:200] = True
    etiquetas = separar(gris, cortes_automaticos(gris, mascara), mascara)
    assert (etiquetas[~mascara] == FONDO).all()
    assert set(np.unique(etiquetas[mascara])) <= {int(c) for c in Capa}


def test_capas_ordenadas_de_oscuro_a_claro():
    gris = degradado()
    etiquetas = separar(gris, (60, 120, 180))
    assert etiquetas[0, 10] == Capa.NEGRO
    assert etiquetas[0, 100] == Capa.OSCURO
    assert etiquetas[0, 150] == Capa.MEDIO
    assert etiquetas[0, 250] == Capa.CLARO
