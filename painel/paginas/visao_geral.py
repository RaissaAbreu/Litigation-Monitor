"""Página: Visão geral (indicadores e processos que exigem atenção)."""

from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st

from litmonitor import banco, config, monitor
from litmonitor.classificacao import CATEGORIAS
from painel import componentes as c
from painel import estilo


def renderizar() -> None:
    c.cabecalho("Visão geral", "Movimentações novas, prazos e processos que exigem atenção na carteira monitorada.")
    c.mensagem_pendente()

    processos = monitor.painel_processos()
    if not processos:
        c.estado_vazio("Importe uma planilha com os números dos processos ou carregue a carteira fictícia "
                       "para conhecer o painel.", "visao")
        return

    ind = monitor.indicadores()
    estilo.secao("Panorama / 01", "Situação da carteira", c.ultima_consulta())
    estilo.metricas([
        ("Processos monitorados", ind["processos"], False),
        ("Exigem atenção", ind["exigem_atencao"], False),
        ("Prazos vencidos", ind["vencidos"], True),
        (f"Vencem em até {config.dias_alerta_prazo()} dias", ind["vencem_breve"], True),
        ("Novas em 7 dias", ind["novas_7_dias"], False),
    ])
    st.button("Consultar agora", type="primary", on_click=c.consultar_agora, key="consultar-visao")

    st.write("")
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        with st.container(border=True, key="cartao-niveis"):
            estilo.titulo_cartao("01", "Processos por nível de atenção")
            estilo.barras(ind["por_nivel"])
    with col2:
        with st.container(border=True, key="cartao-categorias"):
            estilo.titulo_cartao("02", "Movimentações novas em 7 dias")
            desde = (datetime.now() - timedelta(days=7)).isoformat()
            novas = banco.listar_movimentacoes(desde=desde, apenas_novas=True)
            contagem = {CATEGORIAS[k].rotulo: 0 for k in CATEGORIAS if k != "expediente"}
            for m in novas:
                if m["categoria"] != "expediente":
                    contagem[CATEGORIAS[m["categoria"]].rotulo] += 1
            contagem["Expediente / outras"] = sum(m["categoria"] == "expediente" for m in novas)
            estilo.barras({k: v for k, v in contagem.items() if v} or {"Nenhuma": 0})

    st.write("")
    atencao = [p for p in processos if p["exige_atencao"]]
    estilo.secao("Prioridades / 02", "Exigem atenção",
                 "Ordenados pelo nível: prazos vencidos ou em até 2 dias, eventos de alta relevância, "
                 "pendências e falhas de consulta.")
    if not atencao:
        st.success("Nenhum processo exige atenção agora.")
        return
    for p in atencao:
        with st.container(border=True, key=f"cartao-atencao-{p['id']}"):
            estilo.html(c.linha_processo_html(p))
            if p["proximo_prazo"] or p["pendencias"]:
                pend = p["proximo_prazo"] or p["pendencias"][0]
                estilo.recomendacao("Providência sugerida", pend["providencia"])
            elif p["problema_consulta"]:
                estilo.recomendacao("Verificar", p["erro_consulta"] or "Conferir o número e a fonte de dados.")
            st.button("Abrir movimentações", key=f"abrir-atencao-{p['id']}",
                      on_click=c.ir_para, args=("Movimentações", p["id"]))
