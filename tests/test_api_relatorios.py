import base64

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from litmonitor import api, monitor, relatorios, seed


@pytest.fixture
def cliente():
    with TestClient(api.app) as c:
        yield c


def test_fluxo_do_n8n(cliente, monkeypatch):
    monkeypatch.setenv("LM_PLANILHA", str(seed.PLANILHA_EXEMPLO))
    assert cliente.get("/saude").json()["status"] == "ok"
    r1 = cliente.post("/consultas", json={}).json()
    assert r1["importacao"]["incluidos"] == 8 and r1["consulta"]["sucesso"] == 7
    assert cliente.get("/alertas/pendentes").json()["quantidade"] == 0     # 1ª consulta: só histórico

    r2 = cliente.post("/consultas", json={}).json()
    assert r2["importacao"]["incluidos"] == 0 and r2["consulta"]["relevantes"] >= 6
    alertas = cliente.get("/alertas/pendentes").json()["alertas"]
    assert alertas
    for a in alertas:
        resp = cliente.post("/notificacoes", json={"tipo": a["tipo"], "situacao": "sem_canal",
                                                   "movimentacao_id": a["movimentacao_id"]})
        assert resp.status_code == 201
    assert cliente.get("/alertas/pendentes").json()["quantidade"] == 0

    resumo = cliente.get("/relatorios/resumo-diario").json()
    assert resumo["quantidade"] == 7 and resumo["payload"]["type"] == "message"
    assert cliente.post("/notificacoes", json={"tipo": "resumo_diario", "situacao": "enviada"}).status_code == 201

    semanal = cliente.post("/relatorios/semanal").json()
    rid = semanal["relatorio"]["id"]
    assert semanal["payload"]["attachments"][0]["content"]["actions"][0]["url"].endswith(f"/relatorios/{rid}/pdf")
    pdf = cliente.get(f"/relatorios/{rid}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert cliente.get(f"/relatorios/{rid}/xlsx").status_code == 200
    assert cliente.get("/relatorios/999/pdf").status_code == 404


def test_importar_por_api(cliente):
    conteudo = base64.b64encode(seed.PLANILHA_EXEMPLO.read_bytes()).decode()
    r = cliente.post("/processos/importar", json={"nome_arquivo": "carteira.xlsx", "conteudo_base64": conteudo})
    assert r.json()["incluidos"] == 8
    assert cliente.post("/processos/importar", json={"nome_arquivo": "a.pdf",
                                                     "conteudo_base64": "eA=="}).status_code == 422
    assert len(cliente.get("/processos").json()) == 8


def test_notificacao_invalida(cliente):
    assert cliente.post("/notificacoes", json={"tipo": "x", "situacao": "enviada"}).status_code == 422
    assert cliente.post("/notificacoes", json={"tipo": "prazo_vencido", "situacao": "enviada",
                                               "movimentacao_id": 999}).status_code == 404


def test_relatorio_excel_tem_as_tres_abas():
    seed.carregar_demo()
    gerado = relatorios.gerar()
    caminho = relatorios.caminho_arquivo(gerado["relatorio"], "xlsx")
    livro = load_workbook(caminho)
    assert livro.sheetnames == ["Exigem atenção", "Movimentações do período", "Carteira"]
    assert livro["Exigem atenção"].max_row - 1 == monitor.indicadores()["pendencias"] + 1   # + linha "não localizado"
    assert relatorios.caminho_arquivo(gerado["relatorio"], "pdf").read_bytes().startswith(b"%PDF")
