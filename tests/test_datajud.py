import json

import httpx
import pytest

from litmonitor import fontes

RESPOSTA = {
    "_shards": {"total": 3, "successful": 3, "failed": 0},
    "hits": {"hits": [
        {"_source": {
            "numeroProcesso": "07042526220268070021", "grau": "G1", "tribunal": "TJDFT",
            "dataAjuizamento": "20260727092110", "dataHoraUltimaAtualizacao": "2026-10-11T09:19:16.090000Z",
            "classe": {"codigo": 12154, "nome": "Execução de Título Extrajudicial"},
            "assuntos": [{"codigo": 7691, "nome": "Inadimplemento"}],
            "orgaoJulgador": {"codigo": 81523, "nome": "Vara Cível do Itapoã"}, "sistema": {"nome": "PJe"},
            "movimentos": [
                {"codigo": 26, "nome": "Distribuição", "dataHora": "2026-07-27T09:21:10.000Z",
                 "complementosTabelados": [{"codigo": 2, "descricao": "tipo_de_distribuicao_redistribuicao", "valor": 2, "nome": "sorteio"}]},
                {"codigo": 1061, "nome": "Disponibilização no Diário da Justiça Eletrônico", "dataHora": "2026-08-29T02:20:00.000Z"},
            ]}},
        {"_source": {
            "numeroProcesso": "07042526220268070021", "grau": "G2", "dataHoraUltimaAtualizacao": "2026-09-01T00:00:00Z",
            "movimentos": [{"codigo": 239, "nome": "Não-Provimento", "dataHora": "2026-08-20T10:00:00.000Z"}]}},
    ]},
}


def test_interpreta_resposta_e_junta_graus():
    r = fontes.interpretar_resposta_datajud(RESPOSTA)
    assert r.capa["classe"] == "Execução de Título Extrajudicial"
    assert r.capa["data_ajuizamento"] == "2026-07-27" and r.capa["graus"] == "G1, G2"
    assert {m["grau"] for m in r.movimentos} == {"G1", "G2"}
    assert r.movimentos[0]["complementos"][0]["nome"] == "sorteio"


def test_resposta_vazia_e_processo_nao_encontrado():
    with pytest.raises(fontes.ProcessoNaoEncontrado):
        fontes.interpretar_resposta_datajud({"hits": {"hits": []}})


def _fonte(respostas):
    chamadas = []

    def tratar(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        status, corpo = respostas[min(len(chamadas), len(respostas)) - 1]
        return httpx.Response(status, text=corpo if isinstance(corpo, str) else json.dumps(corpo))

    return fontes.FonteDataJud(httpx.Client(transport=httpx.MockTransport(tratar)), pausa=0), chamadas


def test_consulta_envia_numero_limpo_no_indice_do_tribunal(monkeypatch):
    monkeypatch.setenv("DATAJUD_API_KEY", "chave-teste")
    fonte, chamadas = _fonte([(200, RESPOSTA)])
    fonte.consultar({"numero": "0704252-62.2026.8.07.0021"})
    req = chamadas[0]
    assert req.url.path == "/api_publica_tjdft/_search"
    assert req.headers["Authorization"] == "APIKey chave-teste"
    assert json.loads(req.content)["query"]["match"]["numeroProcesso"] == "07042526220268070021"


def test_tenta_de_novo_em_sobrecarga_e_504():
    sobrecarga = {"_shards": {"total": 3, "successful": 2, "failed": 1}, "hits": {"hits": []}}
    fonte, chamadas = _fonte([(504, "<html>Gateway Time-out</html>"), (200, sobrecarga), (200, RESPOSTA)])
    r = fonte.consultar({"numero": "0704252-62.2026.8.07.0021"})
    assert len(chamadas) == 3 and r.movimentos


def test_desiste_apos_tentativas(monkeypatch):
    monkeypatch.setenv("DATAJUD_TENTATIVAS", "2")
    fonte, chamadas = _fonte([(504, "x")])
    with pytest.raises(fontes.ErroFonte, match="HTTP 504"):
        fonte.consultar({"numero": "0704252-62.2026.8.07.0021"})
    assert len(chamadas) == 2


def test_chave_recusada():
    fonte, _ = _fonte([(401, "{}")])
    with pytest.raises(fontes.ErroFonte, match="DATAJUD_API_KEY"):
        fonte.consultar({"numero": "0704252-62.2026.8.07.0021"})
