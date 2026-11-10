"""Componentes reutilizados entre as páginas do painel."""

from __future__ import annotations

import json
from datetime import date, datetime
from html import escape
from typing import Any

import streamlit as st

from litmonitor import banco, fontes, monitor
from litmonitor.monitor import formatar_data
from painel import estilo

PAGINAS = ["Visão geral", "Carteira de processos", "Movimentações", "Alertas e prazos", "Relatórios", "Como funciona"]
EYEBROW_PADRAO = "Contencioso / Litigation Monitor"
SELO_FONTE = {"demo": "Modo demonstração", "datajud": "DataJud · CNJ"}


def ir_para(pagina: str, processo_id: int | None = None) -> None:
    """Callback de navegação (usar em on_click)."""
    st.session_state["pagina"] = pagina
    if processo_id is not None:
        # chave fora de widget: o Streamlit descarta o estado de widgets de páginas não exibidas
        st.session_state["processo_alvo"] = processo_id


def data_hora(valor: str | None) -> str:
    if not valor:
        return "—"
    return datetime.fromisoformat(valor).strftime("%d/%m/%Y %H:%M")


def cabecalho(titulo: str, subtitulo: str, eyebrow: str = EYEBROW_PADRAO) -> None:
    estilo.cabecalho(eyebrow, titulo, subtitulo, SELO_FONTE.get(monitor.fonte_ativa()))


def mensagem_pendente() -> None:
    """Mostra a mensagem guardada por uma ação (sobrevive ao st.rerun)."""
    if msg := st.session_state.pop("mensagem", None):
        tipo, texto = msg
        getattr(st, tipo)(texto)


def avisar(tipo: str, texto: str) -> None:
    st.session_state["mensagem"] = (tipo, texto)


def texto_resumo_consulta(r: monitor.ResumoConsulta) -> str:
    partes = [f"{r.processos} processo(s) consultado(s)", f"{r.novas} nova(s) movimentação(ões)",
              f"{r.relevantes} relevante(s)"]
    if r.nao_localizados:
        partes.append(f"{r.nao_localizados} não localizado(s)")
    if r.erros:
        partes.append(f"{r.erros} com falha")
    return " · ".join(partes) + "."


def consultar_agora(processo_ids: list[int] | None = None) -> None:
    nome = fontes.FONTES[monitor.fonte_ativa()]
    with st.spinner(f"Consultando {nome}… (no DataJud cada processo pode levar até 1 minuto)"):
        resumo = monitor.sincronizar(origem="painel", processo_ids=processo_ids)
    avisar("warning" if resumo.erros else "success", "Consulta concluída: " + texto_resumo_consulta(resumo))


def ultima_consulta() -> str:
    consultas = banco.listar_consultas(1)
    if not consultas:
        return "Nenhuma consulta realizada ainda."
    c = consultas[0]
    return (f"Última consulta: {data_hora(c['finalizada_em'] or c['iniciada_em'])} · "
            f"{fontes.FONTES.get(c['fonte'], c['fonte'])} · origem: {c['origem']}")


def badge_prazo(mov: dict[str, Any]) -> str:
    situacao = monitor.situacao_prazo(mov)
    if not situacao:
        return ""
    rotulo, tom = estilo.TOM_SITUACAO_PRAZO[situacao]
    return estilo.badge(rotulo, tom)


def badges_movimentacao(mov: dict[str, Any]) -> str:
    return (badge_prazo(mov)
            + estilo.badge(f"Relevância {mov['relevancia'].lower()}", estilo.TOM_RELEVANCIA[mov["relevancia"]])
            + estilo.badge(mov["status"], estilo.TOM_STATUS.get(mov["status"], "neutro")))


def linha_processo_html(p: dict[str, Any]) -> str:
    """Linha compacta: nível, número/cliente e a pendência mais urgente."""
    if p["proximo_prazo"]:
        pend = p["proximo_prazo"]
        destaque = f"{pend['rotulo']} · {monitor.texto_prazo(pend)}"
    elif p["pendencias"]:
        pend = p["pendencias"][0]
        destaque = f"{pend['rotulo']} · {monitor.texto_prazo(pend)}"
    elif p["problema_consulta"]:
        destaque = monitor.SITUACOES_CONSULTA[p["situacao_consulta"]]
    else:
        destaque = "Sem pendências"
    badges = estilo.badge(p["tribunal"], "neutro")
    if p["qtd_pendencias"]:
        badges += estilo.badge(f"{p['qtd_pendencias']} pendência(s)", "ambar")
    if p["problema_consulta"]:
        badges += estilo.badge(monitor.SITUACOES_CONSULTA[p["situacao_consulta"]], estilo.TOM_CONSULTA[p["situacao_consulta"]])
    return (f'<div class="lm-proc"><div class="nivel {estilo.classe_nivel(p["nivel"])}">{escape(p["nivel"])}</div>'
            f'<div><div class="t">{escape(p["numero"])} · {escape(p["cliente"] or "Sem cliente")}</div>'
            f'<div class="d">{escape(destaque)} · Responsável: {escape(p["responsavel"] or "—")}</div></div>'
            f'<div class="dir">{badges}</div></div>')


def cartao_pendencia(mov: dict[str, Any], chave: str, editavel: bool = True, mostrar_processo: bool = True) -> None:
    """Cartão no estilo da 'Central de revisão': evento, providência sugerida e registro da decisão do analista."""
    with st.container(border=True, key=f"cartao-mov-{chave}-{mov['id']}"):
        titulo = f"{escape(mov['numero'])} · {escape(mov['rotulo'])}" if mostrar_processo else escape(mov["rotulo"])
        meta = [f"Movimento em {formatar_data(mov['data_hora'])}", escape(mov["descricao"])]
        if mostrar_processo:
            meta.append(escape(mov.get("cliente") or "Sem cliente"))
            meta.append(f"Responsável: {escape(mov.get('responsavel') or '—')}")
        estilo.html(f"""<div class="lm-item-cab">
          <div class="lm-item-titulo">{titulo}</div><div>{badges_movimentacao(mov)}</div></div>
          <div class="lm-item-meta">{' · '.join(meta)}</div>""")
        prazo_txt = monitor.texto_prazo(mov)
        regra = f" — {mov['prazo_regra']}" if mov.get("prazo_regra") and mov.get("prazo_situacao") != "confirmado" else ""
        estilo.recomendacao("Providência sugerida", mov["providencia"])
        estilo.html(f'<div class="lm-muted" style="margin:-6px 0 14px">Prazo: <b>{escape(prazo_txt)}</b>{escape(regra)}</div>')

        if editavel:
            with st.form(key=f"form-{chave}-{mov['id']}", border=False):
                c1, c2, c3 = st.columns([0.3, 0.25, 0.45], gap="medium")
                with c1:
                    opcoes = ["Pendente", "Em andamento", "Concluída", "Sem providência"]
                    status = st.selectbox("Situação", opcoes, index=opcoes.index(mov["status"]) if mov["status"] in opcoes else 0)
                with c2:
                    atual = date.fromisoformat(mov["prazo"]) if mov.get("prazo") else None
                    rotulo_prazo = "Data da audiência" if mov["categoria"] == "audiencia" else "Prazo final"
                    prazo = st.date_input(rotulo_prazo, value=atual, format="DD/MM/YYYY")
                    confirmar = st.checkbox("Confirmar esta data", value=False,
                                            help="Marca o prazo como confirmado pelo analista; ele deixa de ser recalculado.")
                with c3:
                    obs = st.text_area("Observações", value=mov.get("observacoes") or "", height=96)
                if st.form_submit_button("Registrar decisão", type="primary"):
                    alterou = confirmar or (prazo != atual)
                    monitor.atualizar_movimentacao(mov["id"], status, obs, prazo, prazo_alterado=alterou)
                    avisar("success", f"{mov['rotulo']} de {mov['numero']} atualizada.")
                    st.rerun()
        if mostrar_processo:
            st.button("Abrir movimentações do processo", key=f"abrir-{chave}-{mov['id']}",
                      on_click=ir_para, args=("Movimentações", mov["processo_id"]))


def json_processo(processo: dict[str, Any]) -> str:
    dados = {k: v for k, v in processo.items() if k not in ("pendencias", "proximo_prazo")}
    dados["movimentacoes"] = banco.listar_movimentacoes(processo_id=processo["id"])
    dados["historico"] = banco.listar_historico(processo["id"])
    return json.dumps(dados, ensure_ascii=False, indent=2, default=str)


def estado_vazio(texto: str, chave: str) -> None:
    with st.container(border=True, key=f"cartao-vazio-{chave}"):
        estilo.titulo_cartao(None, "Nenhum processo monitorado")
        estilo.html(f'<div class="lm-muted" style="margin-bottom:14px">{escape(texto)}</div>')
        c1, c2, _ = st.columns([0.3, 0.3, 0.4])
        if c1.button("Carregar carteira demonstrativa", key=f"demo-{chave}", type="primary"):
            from litmonitor import seed

            with st.spinner("Carregando carteira fictícia e simulando consultas…"):
                resumo = seed.carregar_demo()
            avisar("success", "Carteira demonstrativa carregada: " + texto_resumo_consulta(resumo))
            st.rerun()
        c2.button("Importar planilha", key=f"ir-carteira-{chave}", on_click=ir_para, args=("Carteira de processos",))
