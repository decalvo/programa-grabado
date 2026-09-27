import pytest

from grabado.tonal import mover_corte, ordenar_cortes


def test_mover_un_corte_no_toca_los_demas():
    assert mover_corte((60.0, 120.0, 180.0), 1, 100) == (60.0, 100.0, 180.0)


@pytest.mark.parametrize(
    "indice, valor, esperado",
    [
        (0, 200, (119.0, 120.0, 180.0)),  # Negro/Oscuro no pasa de Oscuro/Medio
        (1, 10, (60.0, 61.0, 180.0)),
        (1, 250, (60.0, 179.0, 180.0)),
        (2, 0, (60.0, 120.0, 121.0)),  # Medio/Claro no baja de Oscuro/Medio
        (0, -5, (0.0, 120.0, 180.0)),
        (2, 300, (60.0, 120.0, 255.0)),
    ],
)
def test_los_cortes_no_se_cruzan(indice, valor, esperado):
    assert mover_corte((60.0, 120.0, 180.0), indice, valor) == esperado


def test_cortes_automaticos_pegados_se_separan_para_poder_moverlos():
    # Una foto con mucho blanco puede dar dos percentiles iguales.
    assert ordenar_cortes((72.0, 255.0, 255.0)) == (72.0, 254.0, 255.0)
    assert ordenar_cortes((0.0, 0.0, 0.0)) == (0.0, 1.0, 2.0)
    assert ordenar_cortes((255.0, 255.0, 255.0)) == (253.0, 254.0, 255.0)
    c0, c1, c2 = mover_corte((72.0, 255.0, 255.0), 1, 200)
    assert c0 < c1 < c2 and c1 == 200
