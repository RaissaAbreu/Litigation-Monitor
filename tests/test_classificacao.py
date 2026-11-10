from datetime import date

import pytest

from litmonitor import classificacao as cl


def mov(codigo, nome, data="2026-11-03T10:00:00", grau="G1", comps=()):
    return {"codigo": codigo, "nome": nome, "data_hora": data, "grau": grau,
            "complementos": [{"descricao": d, "nome": n} for d, n in comps]}


@pytest.mark.parametrize("m,categoria,relevancia", [
    (mov(221, "Procedência em Parte"), "sentenca", "Alta"),
    (mov(221, "Procedência em Parte", grau="G2"), "acordao", "Alta"),
    (mov(239, "Não-Provimento", grau="G2"), "acordao", "Alta"),
    (mov(848, "Trânsito em julgado"), "transito", "Alta"),
    (mov(785, "Antecipação de tutela"), "tutela", "Alta"),
    (mov(12164, "Outras Decisões"), "decisao", "Média"),
    (mov(1061, "Disponibilização no Diário da Justiça Eletrônico"), "intimacao", "Média"),
    (mov(246, "Definitivo"), "arquivamento", "Média"),
    (mov(51, "Conclusão", comps=[("tipo_de_conclusao", "para julgamento")]), "expediente", "Baixa"),
    (mov(85, "Petição", comps=[("tipo_de_peticao", "Embargos de declaração")]), "expediente", "Baixa"),
    (mov(581, "Documento", comps=[("tipo_de_documento", "Acórdão")], grau="G2"), "acordao", "Alta"),
    (mov(60, "Expedição de documento", comps=[("tipo_de_documento", "Mandado de citação")]), "citacao", "Alta"),
    (mov(99999, "Audiência de conciliação"), "audiencia", "Alta"),
    (mov(99999, "Solicitação de informações"), "expediente", "Baixa"),  # 'solicitação' não é citação
])
def test_categorias(m, categoria, relevancia):
    r = cl.classificar(m)
    assert (r.categoria, r.relevancia) == (categoria, relevancia)


def test_remessa_com_motivo_acordao_nao_vira_acordao():
    m = mov(123, "Remessa", comps=[("motivo_da_remessa", "declaração de competência para Acórdão")])
    assert cl.classificar(m).categoria == "expediente"


def test_audiencia_designada_fica_a_confirmar_e_realizada_baixa_relevancia():
    designada = cl.classificar(mov(970, "Audiência", comps=[("situacao_da_audiencia", "designada")]))
    realizada = cl.classificar(mov(970, "Audiência", comps=[("situacao_da_audiencia", "realizada")]))
    assert designada.prazo_situacao == "a_confirmar" and designada.prazo is None
    assert realizada.relevancia == "Média" and realizada.prazo_situacao is None


def test_sentenca_no_juizado_usa_prazo_do_recurso_inominado():
    r = cl.classificar(mov(219, "Procedência", grau="JE"))
    assert "10 dias" in r.prazo_regra and r.prazo is not None


def test_intimacao_apos_sentenca_e_vinculada_e_prazo_conta_da_publicacao():
    lote = cl.classificar_lote([
        mov(221, "Procedência em Parte", "2026-11-03T18:00:00"),
        mov(1061, "Disponibilização no Diário da Justiça Eletrônico", "2026-11-05T02:20:00"),
        mov(92, "Publicação", "2026-11-06T02:19:00"),
    ])
    (_, sentenca), (_, dje), (_, publicacao) = lote
    assert sentenca.prazo == date(2026, 11, 30)          # DJe 05/11 → publicação 06/11 → conta de 09/11
    assert "publicação de 05/11/2026" in sentenca.prazo_regra
    assert dje.relevancia == "Baixa" and dje.vinculada_a.startswith("Sentença")
    assert publicacao.relevancia == "Baixa"


def test_intimacao_isolada_tem_prazo_proprio():
    (_, r), = cl.classificar_lote([mov(1061, "Disponibilização no Diário da Justiça Eletrônico", "2026-08-29T02:20:00")])
    assert r.categoria == "intimacao" and r.prazo == date(2026, 9, 22)


def test_baixa_e_arquivamento_apos_transito_sao_um_so_encerramento():
    lote = cl.classificar_lote([
        mov(848, "Trânsito em julgado", "2026-11-03T13:20:00"),
        mov(22, "Baixa Definitiva", "2026-11-04T13:25:00"),
        mov(246, "Definitivo", "2026-11-04T13:26:00"),
    ])
    assert [r.relevancia for _, r in lote] == ["Alta", "Baixa", "Baixa"]


def test_chave_estavel_e_sensivel_aos_complementos():
    a = mov(970, "Audiência", comps=[("situacao_da_audiencia", "designada")])
    b = mov(970, "Audiência", comps=[("situacao_da_audiencia", "realizada")])
    assert cl.chave_movimento(a) == cl.chave_movimento(dict(a))
    assert cl.chave_movimento(a) != cl.chave_movimento(b)
