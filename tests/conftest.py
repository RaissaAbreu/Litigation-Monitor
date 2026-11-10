import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    """Cada teste usa um SQLite e uma pasta de relatórios próprios."""
    monkeypatch.setenv("LM_DADOS", str(tmp_path))
    for var in ("GMAIL_USUARIO", "EMAIL_ALERTAS", "LM_PLANILHA", "LM_FONTE", "LM_RELEVANCIA_ALERTA", "LM_DIAS_ALERTA"):
        monkeypatch.delenv(var, raising=False)
    from litmonitor import banco

    banco.inicializar()
    yield tmp_path
