from datetime import date, datetime, timedelta

from litmonitor import banco, fontes, monitor, planilha, seed


def _carteira():
    monitor.importar(planilha.ler_arquivo(seed.PLANILHA_EXEMPLO))
    return {p["numero"]: p for p in banco.listar_processos()}


def test_importacao_inclui_atualiza_e_desativa():
    r = monitor.importar(planilha.ler_arquivo(seed.PLANILHA_EXEMPLO))
    assert (r.incluidos, len(r.invalidos)) == (8, 1)
    csv = "Número do processo;Cliente\n1012345-98.2025.8.26.0100;Novo Nome Ltda.\n".encode()
    r2 = monitor.importar(planilha.ler(csv, "a.csv"), desativar_ausentes=True)
    assert (r2.incluidos, r2.atualizados, r2.desativados) == (0, 1, 7)
    assert len(banco.listar_processos(apenas_ativos=True)) == 1


def test_primeira_consulta_e_historico_e_segunda_traz_novidades():
    _carteira()
    primeira = monitor.sincronizar(fonte=fontes.FonteDemo())
    assert primeira.sucesso == 7 and primeira.nao_localizados == 1
    assert primeira.relevantes == 0                  # histórico antigo não gera alerta
    assert monitor.alertas_pendentes() == []

    segunda = monitor.sincronizar(fonte=fontes.FonteDemo())
    assert segunda.novas > 0 and segunda.relevantes >= 6
    tipos = {a["tipo"] for a in monitor.alertas_pendentes()}
    assert "movimentacao_relevante" in tipos

    # consultar de novo sem novidades na fonte não duplica nada
    total = len(banco.listar_movimentacoes())
    terceira = monitor.sincronizar(fonte=fontes.FonteDemo())
    quarta = monitor.sincronizar(fonte=fontes.FonteDemo())
    assert quarta.novas == 0 and len(banco.listar_movimentacoes()) == total + terceira.novas


def test_primeira_consulta_traz_como_novas_as_relevantes_recentes():
    _carteira()
    p = banco.obter_processo_por_numero("10123459820258260100")
    fonte = fontes.FonteDemo()
    original = fonte.consultar
    # A fonte já tem a sentença de 3 dias atrás, mas é a primeira vez que o processo é consultado.
    fonte.consultar = lambda proc: original({**proc, "consultas_realizadas": 1})
    novas, relevantes = monitor.sincronizar_processo(p, fonte)
    assert (novas, relevantes) == (1, 1)   # só a sentença recente; o resto entra como histórico


def test_nivel_de_atencao_e_indicadores():
    seed.carregar_demo()
    processos = {p["numero"]: p for p in monitor.painel_processos()}
    niveis = {n: p["nivel"] for n, p in processos.items()}
    # a intimação vence no próximo dia útil: Crítica se for em até 2 dias (ex.: numa sexta, segunda = 3 dias)
    dias = monitor.dias_ate(processos["1023456-45.2026.8.26.0100"]["proximo_prazo"]["prazo"])
    assert niveis["1023456-45.2026.8.26.0100"] == ("Crítica" if dias <= 2 else "Alta")
    assert niveis["1012345-98.2025.8.26.0100"] == "Alta"      # sentença
    assert niveis["0005678-55.2025.5.01.0005"] == "Verificar"  # não localizado
    assert niveis["5012345-27.2025.8.13.0024"] == "Em dia"     # só expediente
    ind = monitor.indicadores()
    assert ind["processos"] == 8 and ind["exigem_atencao"] == 7
    assert ind["vencem_breve"] == (1 if dias <= 3 else 0)


def test_analista_confirma_prazo_e_conclui():
    seed.carregar_demo()
    mov = next(m for m in banco.listar_movimentacoes(apenas_abertas=True) if m["categoria"] == "audiencia")
    assert monitor.situacao_prazo(mov) == "a_confirmar"
    data = monitor.hoje() + timedelta(days=20)
    monitor.atualizar_movimentacao(mov["id"], "Em andamento", "Pauta conferida", data, prazo_alterado=True)
    atual = banco.obter_movimentacao(mov["id"])
    assert atual["prazo"] == data.isoformat() and atual["prazo_situacao"] == "confirmado"
    assert monitor.situacao_prazo(atual) == "no_prazo"

    # prazo confirmado não é recalculado em nova consulta
    monitor.sincronizar(fonte=fontes.FonteDemo())
    assert banco.obter_movimentacao(mov["id"])["prazo"] == data.isoformat()

    monitor.atualizar_movimentacao(mov["id"], "Concluída")
    assert banco.obter_movimentacao(mov["id"])["status"] == "Concluída"
    assert any("Audiência" in h["evento"] for h in banco.listar_historico(mov["processo_id"]))


def test_alertas_de_prazo_nao_repetem_mas_vencido_repete_em_24h():
    seed.carregar_demo()
    for a in monitor.alertas_pendentes():
        monitor.registrar_notificacao(a["tipo"], "enviada", a["movimentacao_id"])
    assert monitor.alertas_pendentes() == []

    mov = next(m for m in banco.listar_movimentacoes(apenas_abertas=True) if m["prazo"])
    ontem = (date.today() - timedelta(days=1)).isoformat()
    banco.atualizar_movimentacao(mov["id"], {"prazo": ontem, "prazo_definido_em": banco.agora_iso()})
    vencidos = [a for a in monitor.alertas_pendentes() if a["tipo"] == "prazo_vencido"]
    assert len(vencidos) == 1
    monitor.registrar_notificacao("prazo_vencido", "sem_canal", mov["id"])
    assert not [a for a in monitor.alertas_pendentes() if a["tipo"] == "prazo_vencido"]
    amanha = datetime.now() + timedelta(hours=25)
    assert [a for a in monitor.alertas_pendentes(amanha) if a["tipo"] == "prazo_vencido"]


def test_relevancia_minima_configuravel(monkeypatch):
    seed.carregar_demo()
    monkeypatch.setenv("LM_RELEVANCIA_ALERTA", "Alta")
    relevantes = [a for a in monitor.alertas_pendentes() if a["tipo"] == "movimentacao_relevante"]
    assert relevantes and all(banco.obter_movimentacao(a["movimentacao_id"])["relevancia"] == "Alta" for a in relevantes)


def test_fonte_com_erro_marca_processo():
    _carteira()

    class Fora:
        nome = "datajud"

        def consultar(self, processo):
            raise fontes.ErroFonte("DataJud indisponível: HTTP 504.")

    r = monitor.sincronizar(fonte=Fora())
    assert r.erros == 8
    p = banco.obter_processo_por_numero("10123459820258260100")
    assert p["situacao_consulta"] == "erro" and "504" in p["erro_consulta"]


def test_cartao_teams_tem_link_para_o_processo(monkeypatch):
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://exemplo.invalid/webhook")
    seed.carregar_demo()
    alerta = monitor.alertas_pendentes()[0]
    assert alerta["webhook_url"] == "https://exemplo.invalid/webhook"
    cartao = alerta["payload"]["attachments"][0]["content"]
    assert cartao["type"] == "AdaptiveCard"
    assert "?processo=" in cartao["actions"][0]["url"]
