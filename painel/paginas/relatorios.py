"""Página: Relatórios (sob demanda, semanal e resumo diário)."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from litmonitor import banco, fontes, relatorios
from painel import componentes as c
from painel import estilo


def _baixar(relatorio: dict, chave: str) -> None:
    b1, b2, _ = st.columns([0.22, 0.22, 0.56])
    pdf = relatorios.caminho_arquivo(relatorio, "pdf")
    xlsx = relatorios.caminho_arquivo(relatorio, "xlsx")
    if pdf.exists():
        b1.download_button("Baixar relatório PDF", pdf.read_bytes(), pdf.name, "application/pdf", key=f"pdf-{chave}")
    if xlsx.exists():
        b2.download_button("Baixar planilha Excel", xlsx.read_bytes(), xlsx.name,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"xlsx-{chave}")


def renderizar() -> None:
    c.cabecalho("Relatórios", "Processos que exigem atenção, em PDF e Excel — sob demanda, toda semana pelo n8n "
                "e em resumo diário no Teams.")
    c.mensagem_pendente()

    estilo.secao("Relatório / 05", "Gerar relatório agora",
                 "Inclui os processos que exigem atenção, as movimentações detectadas no período e a carteira completa.")
    with st.container(border=True, key="cartao-gerar"):
        estilo.titulo_cartao("01", "Período")
        col1, col2 = st.columns([0.35, 0.65], gap="large")
        dias = col1.selectbox("Movimentações detectadas nos últimos", [7, 15, 30], format_func=lambda d: f"{d} dias")
        col2.markdown("")
        if st.button("Gerar relatório", type="primary"):
            with st.spinner("Gerando PDF e Excel…"):
                gerado = relatorios.gerar("sob_demanda", origem="painel", dias=dias)
            st.session_state["relatorio_recente"] = gerado["relatorio"]["id"]
            c.avisar("success", "Relatório gerado.")
            st.rerun()
        recente_id = st.session_state.get("relatorio_recente")
        recente = banco.obter_relatorio(recente_id) if recente_id else None
        if recente:
            estilo.html(f'<div class="lm-muted" style="margin:6px 0 10px">Gerado em {c.data_hora(recente["criado_em"])} · '
                        f'{recente["processos_atencao"]} processo(s) exigem atenção.</div>')
            _baixar(recente, "recente")

    st.write("")
    estilo.secao("Prévia / 06", "Processos que exigem atenção", "O mesmo conteúdo da primeira página do relatório.")
    tabelas = relatorios.dados_relatorio(*_periodo(7))
    if tabelas["Exigem atenção"].empty:
        st.caption("Nenhum processo exige atenção no momento.")
    else:
        st.dataframe(tabelas["Exigem atenção"], hide_index=True, use_container_width=True)

    st.write("")
    estilo.secao("Teams / 07", "Resumo diário", "Prévia do cartão que o n8n envia ao Teams toda manhã, às 7h30.")
    resumo = relatorios.resumo_diario()
    corpo = resumo["payload"]["attachments"][0]["content"]["body"]
    fatos = next((b["facts"] for b in corpo if b.get("type") == "FactSet"), [])
    with st.container(border=True, key="cartao-resumo-diario"):
        estilo.titulo_cartao(None, corpo[1]["text"])
        if fatos:
            estilo.html('<ul class="lm-arquivos">' + "".join(
                f'<li><span class="n">{i}</span><div><div>{escape(f["title"])}</div><div class="det">{escape(f["value"])}</div></div></li>'
                for i, f in enumerate(fatos, start=1)) + "</ul>")
        else:
            estilo.html('<div class="lm-muted">Nenhum processo exige atenção hoje.</div>')

    st.write("")
    estilo.secao("Arquivo / 08", "Relatórios gerados")
    historico = banco.listar_relatorios()
    if not historico:
        st.caption("Nenhum relatório gerado ainda.")
    for r in historico[:10]:
        with st.container(border=True, key=f"cartao-rel-{r['id']}"):
            estilo.html(f"""<div class="lm-item-cab"><div class="lm-item-titulo">{escape(relatorios.TIPOS.get(r['tipo'], r['tipo']))}
              · {c.data_hora(r['criado_em'])}</div><div>{estilo.badge(r['origem'], 'neutro')}{estilo.badge(f"{r['processos_atencao']} exigem atenção", 'ambar')}</div></div>
              <div class="lm-item-meta" style="margin-bottom:12px">Período de {relatorios.formatar_data(r['periodo_inicio'])} a {relatorios.formatar_data(r['periodo_fim'])}</div>""")
            _baixar(r, f"hist-{r['id']}")

    st.write("")
    estilo.secao("Consultas / 09", "Histórico de consultas à fonte")
    consultas = banco.listar_consultas(30)
    if consultas:
        st.dataframe(pd.DataFrame([{
            "Início": c.data_hora(q["iniciada_em"]), "Fonte": fontes.FONTES.get(q["fonte"], q["fonte"]),
            "Origem": q["origem"], "Processos": q["processos"], "Consultados": q["sucesso"],
            "Não localizados": q["nao_localizados"], "Falhas": q["erros"], "Novas": q["novas"], "Relevantes": q["relevantes"],
        } for q in consultas]), hide_index=True, use_container_width=True)
    else:
        st.caption("Nenhuma consulta realizada ainda.")


def _periodo(dias: int):
    from datetime import timedelta

    from litmonitor import monitor

    fim = monitor.hoje()
    return fim - timedelta(days=dias - 1), fim
