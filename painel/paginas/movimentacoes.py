"""Página: Movimentações de um processo (nível de atenção, dados da capa, linha do tempo e pendências)."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from litmonitor import banco, fontes, monitor
from litmonitor.classificacao import CATEGORIAS
from painel import componentes as c
from painel import estilo


def _nota_nivel(p: dict) -> str:
    if p["proximo_prazo"]:
        return f"Próximo prazo: {monitor.texto_prazo(p['proximo_prazo'])}"
    if p["qtd_pendencias"]:
        return f"{p['qtd_pendencias']} pendência(s) sem prazo"
    if p["problema_consulta"]:
        return monitor.SITUACOES_CONSULTA[p["situacao_consulta"]]
    return "Nenhuma pendência aberta"


def _resumo(p: dict, movs: list[dict]) -> None:
    with st.container(border=True, key=f"cartao-resumo-{p['id']}"):
        esquerda, direita = st.columns([0.4, 0.6], gap="large")
        nivel = p["nivel"] if p["ativo"] else "Inativo"
        with esquerda:
            estilo.html(f"""<div class="lm-risco {estilo.classe_nivel(nivel)}">
              <div class="rotulo">Nível de atenção</div>
              <div class="valor">{escape(nivel if p['ativo'] else 'Pausado')}</div>
              <div class="nota">{escape(_nota_nivel(p))}</div></div>""")
        with direita:
            situacao = monitor.SITUACOES_CONSULTA.get(p["situacao_consulta"], p["situacao_consulta"])
            contagem = {}
            for m in movs:
                if m["nova"] or m["status"] in monitor.STATUS_ABERTOS:
                    contagem[m["relevancia"]] = contagem.get(m["relevancia"], 0) + 1
            fonte = fontes.FONTES.get(p["fonte"], "—") if p["fonte"] else "—"
            estilo.html(f"""
              <div class="lm-rotulo" style="margin-top:0">Situação do monitoramento</div>
              <div>{estilo.badge(situacao, estilo.TOM_CONSULTA.get(p['situacao_consulta'], 'neutro'))}{estilo.badge(p['tribunal'], 'azul')}{estilo.badge('Grau: ' + (p['graus'] or '—'), 'neutro')}</div>
              <div class="lm-rotulo">Dados principais</div>
              <ul class="lm-lista">
                <li>{escape(p['numero'])} · {escape(p['classe'] or 'classe não informada')}</li>
                <li>Assunto: {escape(p['assuntos'] or '—')}</li>
                <li>Órgão julgador: {escape(p['orgao_julgador'] or '—')}</li>
                <li>Cliente: {escape(p['cliente'] or '—')} · Parte contrária: {escape(p['parte_contraria'] or '—')}</li>
                <li>Responsável: {escape(p['responsavel'] or '—')}</li>
                <li>Fonte: {escape(fonte)} · última consulta {c.data_hora(p['ultima_consulta_em'])}</li>
              </ul>
              <div class="lm-rotulo">Movimentações novas ou pendentes</div>
              <div>{''.join(f"{estilo.badge(r, estilo.TOM_RELEVANCIA[r])}<b style='margin-right:14px'>{contagem.get(r, 0)}</b>" for r in ('Alta', 'Média', 'Baixa'))}</div>
            """)
            if p["erro_consulta"]:
                estilo.html(f'<div class="lm-muted" style="margin-top:10px">{escape(p["erro_consulta"])}</div>')


def _linha_do_tempo(movs: list[dict], mostrar_baixas: bool) -> None:
    itens = []
    for m in movs:
        if not mostrar_baixas and m["relevancia"] == "Baixa":
            continue
        extras = estilo.badge(m["rotulo"], estilo.TOM_RELEVANCIA[m["relevancia"]])
        if m["nova"]:
            extras += estilo.badge("Nova", "azul")
        if m["status"] in monitor.STATUS_ABERTOS:
            extras += estilo.badge(m["status"], estilo.TOM_STATUS[m["status"]])
        vinculo = f' · vinculada a {escape(m["vinculada_a"])}' if m["vinculada_a"] else ""
        itens.append(f"""<li class="{m['relevancia']}"><div class="linha-cab"><span class="evento">{escape(m['descricao'])}</span>{extras}</div>
          <div class="quando">{c.data_hora(m['data_hora'])} · {escape(m['grau'] or '—')} · {escape(m['orgao'] or '')}{vinculo}</div></li>""")
    estilo.html(f'<ul class="lm-tempo">{"".join(itens)}</ul>' if itens else
                '<div class="lm-muted">Nenhuma movimentação para exibir.</div>')


def renderizar() -> None:
    estilo.cabecalho("Análise do processo / 03", "Movimentações",
                     "Nível de atenção, movimentações classificadas, prazos estimados e providências sugeridas.",
                     c.SELO_FONTE.get(monitor.fonte_ativa()))
    c.mensagem_pendente()

    processos = monitor.painel_processos(incluir_inativos=True)
    if not processos:
        c.estado_vazio("Importe uma planilha para acompanhar as movimentações.", "movs")
        return

    ids = [p["id"] for p in processos]
    alvo = st.session_state.pop("processo_alvo", None)
    if alvo in ids:
        st.session_state["processo_escolhido"] = alvo
    if st.session_state.get("processo_escolhido") not in ids:
        st.session_state["processo_escolhido"] = ids[0]
    rotulos = {p["id"]: f"{p['numero']} — {p['cliente'] or 'sem cliente'} · {p['tribunal']} · "
                        f"{p['nivel'] if p['ativo'] else 'pausado'}" for p in processos}
    escolhido = st.selectbox("Selecione um processo para consultar", ids, format_func=rotulos.get,
                             key="processo_escolhido")
    p = next(x for x in processos if x["id"] == escolhido)
    movs = banco.listar_movimentacoes(processo_id=p["id"])

    _resumo(p, movs)
    st.write("")
    b1, b2, _ = st.columns([0.25, 0.25, 0.5])
    b1.button("Consultar este processo agora", on_click=c.consultar_agora, args=([p["id"]],), disabled=not p["ativo"])
    b2.download_button("Baixar dados JSON", c.json_processo(p), f"processo_{p['numero_limpo']}.json", "application/json")

    pendentes = [m for m in movs if m["status"] in monitor.STATUS_ABERTOS]
    notificacoes = banco.listar_notificacoes(processo_id=p["id"])
    historico = banco.listar_historico(p["id"])
    abas = st.tabs([f"Pendências ({len(pendentes)})", f"Linha do tempo ({len(movs)})", "Por classificação",
                    f"Alertas enviados ({len(notificacoes)})", f"Histórico ({len(historico)})"])

    with abas[0]:
        if not pendentes:
            st.caption("Nenhuma pendência aberta neste processo.")
        for m in sorted(pendentes, key=lambda m: (m.get("prazo") or "9999", m["data_hora"])):
            c.cartao_pendencia(m, "proc", mostrar_processo=False)

    with abas[1]:
        with st.container(border=True, key="cartao-tempo"):
            mostrar = st.toggle("Mostrar movimentações de baixa relevância (expediente)", value=False)
            _linha_do_tempo(movs, mostrar)

    with abas[2]:
        with st.container(border=True, key="cartao-categorias-proc"):
            contagem = {cat.rotulo: 0 for cat in CATEGORIAS.values()}
            for m in movs:
                contagem[CATEGORIAS[m["categoria"]].rotulo] += 1
            estilo.barras({k: v for k, v in contagem.items() if v})
            st.caption("Classificação por regras: código do movimento na TPU/CNJ, palavras-chave e grau de jurisdição.")

    with abas[3]:
        if not notificacoes:
            st.caption("Nenhum alerta registrado para este processo.")
        else:
            situacao = {"enviada": "Enviada", "sem_canal": "Sem canal configurado", "falha": "Falha no envio"}
            st.dataframe(pd.DataFrame([{
                "Quando": c.data_hora(n["criado_em"]), "Tipo": monitor.TIPOS_NOTIFICACAO.get(n["tipo"], n["tipo"]),
                "Movimentação": n["descricao"] or "—", "Situação": situacao.get(n["situacao"], n["situacao"]),
            } for n in notificacoes]), hide_index=True, width="stretch")

    with abas[4]:
        with st.container(border=True, key="cartao-historico"):
            estilo.html('<ul class="lm-tempo">' + "".join(
                f'<li><div class="evento">{escape(h["evento"])}</div><div class="desc">{escape(h["detalhe"])}</div>'
                f'<div class="quando">{c.data_hora(h["criado_em"])} · {escape(h["autor"])}</div></li>'
                for h in historico) + "</ul>")

    estilo.html('<div class="lm-aviso-rodape">Classificação e prazos gerados automaticamente para apoio ao '
                'acompanhamento. Não substituem a leitura do processo por um profissional.</div>')
