"""Painel de acompanhamento — LITIGATION MONITOR.

Executar a partir da raiz do projeto:  streamlit run painel/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from litmonitor import VERSAO, banco, cnj, config, fontes, monitor  # noqa: E402
from painel import componentes as c  # noqa: E402
from painel import estilo  # noqa: E402
from painel.paginas import alertas, carteira, como_funciona, movimentacoes, relatorios, visao_geral  # noqa: E402

st.set_page_config(page_title="Litigation Monitor", page_icon="⚖️", layout="wide", initial_sidebar_state="expanded")
estilo.aplicar()
banco.inicializar()

# Link vindo do Teams: ?processo=0000000-00.0000.0.00.0000 abre direto as movimentações.
if (numero := st.query_params.get("processo")) and not st.session_state.get("link_consumido"):
    st.session_state["link_consumido"] = True
    try:
        processo = banco.obter_processo_por_numero(cnj.interpretar(numero).limpo)
    except cnj.NumeroInvalido:
        processo = None
    if processo:
        c.ir_para("Movimentações", processo["id"])

ROTAS = {
    "Visão geral": visao_geral.renderizar,
    "Carteira de processos": carteira.renderizar,
    "Movimentações": movimentacoes.renderizar,
    "Alertas e prazos": alertas.renderizar,
    "Relatórios": relatorios.renderizar,
    "Como funciona": como_funciona.renderizar,
}


def _trocar_fonte() -> None:
    monitor.definir_fonte(st.session_state["fonte_escolhida"])


with st.sidebar:
    estilo.html('<div class="lm-marca"><div class="nome">LITIGATION<br>MONITOR</div>'
                '<div class="sub">MONITORAMENTO DE<br>PROCESSOS</div></div>')
    estilo.html('<div class="lm-rotulo-lateral">Área de trabalho</div>')
    st.radio("Navegação", c.PAGINAS, key="pagina", label_visibility="collapsed")

    estilo.html('<div class="lm-sep"></div><div class="lm-rotulo-lateral">Fonte de dados</div>')
    atual = monitor.fonte_ativa()
    st.session_state.setdefault("fonte_escolhida", atual)
    if st.session_state["fonte_escolhida"] != atual:
        st.session_state["fonte_escolhida"] = atual
    st.selectbox("Provedor", list(fontes.FONTES), format_func=fontes.FONTES.get, key="fonte_escolhida",
                 on_change=_trocar_fonte)
    nota = ("Dados fictícios, sem acesso à rede" if atual == "demo"
            else "API Pública oficial do CNJ · dados públicos")
    estilo.html(f'<div class="lm-nota-lateral"><span class="ponto"></span>{nota}</div>')

    teams_ok = bool(config.teams_webhook())
    estilo.html(f"""<div class="lm-sep"></div><div class="lm-rotulo-lateral">Integrações</div>
      <div class="lm-nota-lateral"><span class="ponto ok"></span>n8n: consulta diária, resumo e relatório semanal</div>
      <div class="lm-nota-lateral"><span class="ponto {'ok' if teams_ok else 'off'}"></span>Teams: {'canal configurado' if teams_ok else 'sem canal configurado'}</div>""")

    estilo.html(f"""<div class="lm-sep"></div><div class="lm-rotulo-lateral">Contencioso</div>
      <div class="lm-rodape-lateral"><div class="titulo">Monitoramento automatizado de processos.</div>
      <div class="meta">Versão {VERSAO} · Prazos são estimativas: confirme sempre no processo.</div></div>""")

ROTAS[st.session_state.get("pagina", c.PAGINAS[0])]()
