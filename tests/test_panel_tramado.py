import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from grabado.tramado import METODOS  # noqa: E402
from grabado.ui.documento import Documento  # noqa: E402
from grabado.ui.panel_tramado import PanelTramado  # noqa: E402

app = QApplication.instance() or QApplication([])


def test_el_selector_ofrece_los_metodos_con_jarvis_elegido():
    panel = PanelTramado(Documento())
    opciones = [panel.metodo.itemData(i) for i in range(panel.metodo.count())]
    assert opciones == list(METODOS)
    assert panel.metodo.currentData() == "jarvis"


def test_elegir_un_metodo_cambia_los_ajustes_del_documento():
    documento = Documento()
    avisos = []
    documento.cambiado.connect(lambda: avisos.append(True))
    panel = PanelTramado(documento)
    panel.metodo.setCurrentIndex(panel.metodo.findData("semitono"))
    assert documento.ajustes.metodo_tramado == "semitono"
    assert avisos
