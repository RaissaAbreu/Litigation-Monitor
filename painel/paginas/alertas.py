"""Página: Alertas e prazos (central de pendências do analista)."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from litmonitor import banco, config, monitor
from painel import componentes as c
from painel import estilo

FILTROS = {
    "Todas as pendências": lambda m: True,
    "Prazos vencidos ou próximos": lambda m: monitor.situacao_prazo(m) in ("vencido", "hoje", "proximo"),
    "Datas a confirmar": lambda m: monitor.situacao_prazo(m) == "a_confirmar",
    "Relevância alta": lambda m: m["relevancia"] == "Alta",
}


def _urgencia(m: dict) -> tuple:
    ordem = {"vencido": 0, "hoje": 1, "proximo": 2, "a_confirmar": 3, "no_prazo": 4, None: 5}
    return (ordem[monitor.situacao_prazo(m)], -{"Alta": 3, "Média": 2, "Baixa": 1}[m["relevancia"]],
            m.get("prazo") or "9999", m["data_hora"])


def renderizar() -> None:
    c.cabecalho("Alertas e prazos", "Registre a providência de cada movimentação relevante. "
                "O n8n avisa por e-mail sobre eventos novos e prazos próximos ou vencidos.")
    c.mensagem_pendente()

    abertas = banco.listar_movimentacoes(apenas_abertas=True)
    situacoes = [monitor.situacao_prazo(m) for m in abertas]
    estilo.secao("Controle / 04", "Central de prazos",
                 "Prazos estimados contam dias úteis e feriados nacionais — confirme a data no processo.")
    estilo.metricas([
        ("Aguardando providência", len(abertas), False),
        ("Prazos vencidos", situacoes.count("vencido"), True),
        (f"Vencem em até {config.dias_alerta_prazo()} dias", situacoes.count("hoje") + situacoes.count("proximo"), True),
        ("Datas a confirmar", situacoes.count("a_confirmar"), False),
    ])

    f1, f2 = st.columns([0.4, 0.6])
    filtro = f1.selectbox("Mostrar", list(FILTROS))
    incluir_concluidas = f2.checkbox("Mostrar também movimentações já tratadas (últimos 30 dias)")
    lista = [m for m in abertas if FILTROS[filtro](m)]
    lista.sort(key=_urgencia)
    if incluir_concluidas:
        from datetime import datetime, timedelta

        desde = (datetime.now() - timedelta(days=30)).isoformat()
        tratadas = [m for m in banco.listar_movimentacoes(desde=desde, apenas_novas=True)
                    if m["status"] in ("Concluída", "Sem providência")]
        lista += tratadas

    if not lista:
        st.success("Nenhuma pendência neste filtro.")
    for m in lista:
        c.cartao_pendencia(m, "central", editavel=m["status"] in monitor.STATUS_ABERTOS or incluir_concluidas)

    st.write("")
    estilo.secao("Notificações / 05", "Próximo envio do n8n",
                 "Alertas ainda não enviados. O fluxo “Consulta diária” envia esta lista por e-mail logo após consultar a fonte.")
    pendentes = monitor.alertas_pendentes()
    with st.container(border=True, key="cartao-pendentes"):
        if not pendentes:
            estilo.html('<div class="lm-muted">Nenhum alerta pendente de envio.</div>')
        else:
            canal = estilo.badge("Gmail configurado", "verde") if config.email_remetente() else \
                estilo.badge("Gmail não configurado", "ambar")
            estilo.html('<ul class="lm-arquivos">' + "".join(
                f'<li><span class="n">{i}</span><div><div>{escape(a["numero"])} · {escape(a["tipo_descricao"])}</div>'
                f'<div class="det">{escape(a["email"]["assunto"])}</div></div><span class="dir">{canal}</span></li>'
                for i, a in enumerate(pendentes, start=1)) + "</ul>")

    st.write("")
    estilo.secao("Notificações / 06", "Alertas registrados", "Mensagens enviadas (ou tentadas) pelo n8n.")
    notificacoes = banco.listar_notificacoes()
    if not notificacoes:
        st.caption("Nenhuma notificação registrada ainda.")
        return
    situacao = {"enviada": "Enviada", "sem_canal": "E-mail não configurado", "falha": "Falha no envio"}
    st.dataframe(pd.DataFrame([{
        "Quando": c.data_hora(n["criado_em"]), "Tipo": monitor.TIPOS_NOTIFICACAO.get(n["tipo"], n["tipo"]),
        "Processo": n["numero"] or "—", "Movimentação": n["rotulo"] or "—",
        "Situação": situacao.get(n["situacao"], n["situacao"]),
    } for n in notificacoes]), hide_index=True, width="stretch")
