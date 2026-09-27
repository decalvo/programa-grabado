import numpy as np
import pytest
from PIL import Image

from grabado.retoque import (
    BORRAR,
    RECUPERAR,
    Retoque,
    aplicar_trazo,
    escala_en_pantalla,
    ubicar_imagen,
    widget_a_imagen,
)


def blanca(ancho=100, alto=80):
    return Image.new("L", (ancho, alto), 255)


def foto(ancho=100, alto=80):
    return Image.new("RGB", (ancho, alto), (120, 90, 60))


def pixeles(mascara):
    return np.asarray(mascara)


# --- Coordenadas ---------------------------------------------------------------------


def test_imagen_ancha_se_centra_en_vertical():
    # 400×200 en un widget de 800×600: escala 2, sobran 200 px de alto.
    assert ubicar_imagen((400, 200), (800, 600)) == (0, 100, 800, 400)
    assert escala_en_pantalla((400, 200), (800, 600)) == 2


def test_imagen_alta_se_centra_en_horizontal():
    assert ubicar_imagen((200, 400), (800, 600)) == (250, 0, 300, 600)


def test_widget_a_imagen():
    tamano, widget = (400, 200), (800, 600)
    assert widget_a_imagen((0, 100), tamano, widget) == (0, 0)
    assert widget_a_imagen((800, 500), tamano, widget) == (400, 200)
    assert widget_a_imagen((401, 301), tamano, widget) == (200.5, 100.5)
    # Fuera de la imagen (franja vacía) da coordenadas fuera de la foto.
    assert widget_a_imagen((10, 20), tamano, widget)[1] < 0


# --- Trazos --------------------------------------------------------------------------


def test_borrar_pinta_fondo_solo_dentro_del_pincel():
    mascara = blanca()
    caja = aplicar_trazo(mascara, [(50.5, 40.5)], 5, BORRAR)
    datos = pixeles(mascara)
    assert datos[40, 50] == 0
    assert datos[40, 54] == 0
    assert datos[40, 57] == 255
    assert datos[0, 0] == 255
    izquierda, arriba, derecha, abajo = caja
    assert not (datos[:arriba] == 0).any() and not (datos[abajo:] == 0).any()
    assert not (datos[:, :izquierda] == 0).any() and not (datos[:, derecha:] == 0).any()


def test_recuperar_vuelve_a_sujeto():
    mascara = Image.new("L", (100, 80), 0)
    aplicar_trazo(mascara, [(20.5, 20.5)], 3, RECUPERAR)
    assert pixeles(mascara)[20, 20] == 255
    assert pixeles(mascara)[60, 60] == 0


def test_el_trazo_une_los_puntos():
    mascara = blanca()
    aplicar_trazo(mascara, [(10.5, 40.5), (90.5, 40.5)], 2, BORRAR)
    fila = pixeles(mascara)[40]
    assert (fila[10:91] == 0).all()
    assert (pixeles(mascara)[45] == 255).all()


def test_pincel_mas_grande_pinta_mas():
    chico, grande = blanca(), blanca()
    aplicar_trazo(chico, [(50, 40)], 3, BORRAR)
    aplicar_trazo(grande, [(50, 40)], 10, BORRAR)
    area_chica = (pixeles(chico) == 0).sum()
    area_grande = (pixeles(grande) == 0).sum()
    assert area_chica == pytest.approx(np.pi * 9, rel=0.4)
    assert area_grande == pytest.approx(np.pi * 100, rel=0.2)


def test_pincel_diminuto_pinta_al_menos_un_pixel():
    mascara = blanca()
    aplicar_trazo(mascara, [(30.2, 20.9)], 0.1, BORRAR)
    assert pixeles(mascara)[20, 30] == 0


def test_trazo_fuera_de_la_foto_no_cambia_nada():
    mascara = blanca()
    assert aplicar_trazo(mascara, [(-50, -50)], 5, BORRAR) is None
    assert (pixeles(mascara) == 255).all()


def test_modo_desconocido():
    with pytest.raises(ValueError):
        aplicar_trazo(blanca(), [(1, 1)], 1, "pintar")


# --- Retoque y deshacer --------------------------------------------------------------


def test_trazar_no_modifica_la_mascara_anterior():
    retoque = Retoque()
    original = blanca()
    nueva = retoque.trazar(foto(), original, [(50, 40)], 5, BORRAR)
    assert nueva is not original
    assert (pixeles(original) == 255).all()
    assert pixeles(nueva)[40, 50] == 0


def test_sin_mascara_parte_de_todo_sujeto():
    retoque = Retoque()
    nueva = retoque.trazar(foto(), None, [(50, 40)], 5, BORRAR)
    datos = pixeles(nueva)
    assert nueva.size == (100, 80)
    assert datos[40, 50] == 0 and datos[0, 0] == 255
    # Deshacer vuelve a "sin máscara".
    assert retoque.deshacer(nueva) is None
    assert not retoque.puede_deshacer(None)


def test_sin_mascara_respeta_la_transparencia_de_la_foto():
    imagen = foto().convert("RGBA")
    alfa = np.zeros((80, 100), np.uint8)
    alfa[:, 50:] = 255
    imagen.putalpha(Image.fromarray(alfa, "L"))
    nueva = Retoque().trazar(imagen, None, [(10, 10)], 2, RECUPERAR)
    datos = pixeles(nueva)
    assert datos[10, 10] == 255 and datos[70, 10] == 0 and datos[70, 90] == 255


def test_deshacer_varios_trazos_en_orden():
    retoque = Retoque()
    m0 = blanca()
    m1 = retoque.trazar(foto(), m0, [(20, 20)], 4, BORRAR)
    m2 = retoque.trazar(foto(), m1, [(70, 50), (80, 60)], 4, BORRAR)
    m3 = retoque.trazar(foto(), m2, [(20, 20)], 6, RECUPERAR)
    assert retoque.puede_deshacer(m3)
    d2 = retoque.deshacer(m3)
    assert (pixeles(d2) == pixeles(m2)).all()
    d1 = retoque.deshacer(d2)
    assert (pixeles(d1) == pixeles(m1)).all()
    d0 = retoque.deshacer(d1)
    assert (pixeles(d0) == pixeles(m0)).all()
    assert not retoque.puede_deshacer(d0)


def test_si_la_mascara_cambia_por_fuera_se_olvida_lo_anterior():
    retoque = Retoque()
    m1 = retoque.trazar(foto(), blanca(), [(20, 20)], 4, BORRAR)
    otra = blanca()  # por ejemplo, se eliminó el fondo de nuevo
    assert not retoque.puede_deshacer(otra)
    m2 = retoque.trazar(foto(), otra, [(50, 50)], 4, BORRAR)
    assert retoque.puede_deshacer(m2)
    assert (pixeles(retoque.deshacer(m2)) == 255).all()
    assert not retoque.puede_deshacer(m1)


def test_limite_de_deshacer():
    retoque = Retoque(limite=2)
    mascara = blanca()
    for x in (10, 30, 50):
        mascara = retoque.trazar(foto(), mascara, [(x, 10)], 2, BORRAR)
    mascara = retoque.deshacer(mascara)
    mascara = retoque.deshacer(mascara)
    assert not retoque.puede_deshacer(mascara)
    assert pixeles(mascara)[10, 10] == 0  # el primer trazo ya no se puede deshacer
