import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from grabado.ui.documento import Documento  # noqa: E402
from grabado.ui.panel_contorno import PanelContorno  # noqa: E402

app = QApplication.instance() or QApplication([])


def documento_con_recorte():
    documento = Documento()
    documento.foto = Image.new("RGB", (100, 80), "gray")
    mascara = Image.new("L", (100, 80), 0)
    mascara.paste(255, (20, 20, 80, 60))
    documento.cambiar_mascara(mascara)
    return documento


def test_sin_recorte_esta_desactivado_con_aviso():
    panel = PanelContorno(Documento())
    assert not panel.activar.isEnabled()
    assert not panel.activar.isChecked()
    assert not panel.aviso.isHidden()


def test_con_recorte_se_activa_y_cambia_los_ajustes():
    documento = documento_con_recorte()
    panel = PanelContorno(documento)
    assert panel.activar.isEnabled()
    assert panel.aviso.isHidden()
    assert panel.grosor.value() == 1.0
    assert not panel.grosor.isEnabled()

    panel.activar.setChecked(True)
    assert documento.ajustes.contorno is True
    assert panel.grosor.isEnabled()
    panel.grosor.setValue(2.5)
    assert documento.ajustes.grosor_contorno_mm == 2.5
    assert documento.procesar().contorno is not None
