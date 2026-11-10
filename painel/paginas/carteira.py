"""Página: Carteira de processos (importação da planilha e cadastro)."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from litmonitor import banco, fontes, monitor, planilha, seed
from painel import componentes as c
from painel import estilo


def _resultado_importacao(r: monitor.ResultadoImportacao) -> str:
    partes = [f"{r.incluidos} incluído(s)", f"{r.atualizados} atualizado(s)"]
    if r.reativados:
        partes.append(f"{r.reativados} reativado(s)")
    if r.desativados:
        partes.append(f"{r.desativados} desativado(s)")
    if r.invalidos:
        partes.append(f"{len(r.invalidos)} número(s) inválido(s) ignorado(s)")
    if r.duplicados:
        partes.append(f"{r.duplicados} repetido(s)")
    return "Planilha importada: " + " · ".join(partes) + "."


def _limpar() -> None:
    st.session_state.pop("planilha_demo", None)
    st.session_state["uploader_versao"] = st.session_state.get("uploader_versao", 0) + 1


def _usar_demo() -> None:
    st.session_state["planilha_demo"] = True
    st.session_state["uploader_versao"] = st.session_state.get("uploader_versao", 0) + 1


def renderizar() -> None:
    c.cabecalho("Carteira de processos", "Leitura da planilha com os números dos processos que serão monitorados.")
    c.mensagem_pendente()

    estilo.secao("Entrada da carteira / 01", "Planilha de processos",
                 "Envie uma planilha Excel (.xlsx) ou CSV com a coluna “Número do processo”. Cliente, parte "
                 "contrária, responsável e observações são opcionais.")

    leitura = nome_arquivo = None
    erro = ""
    with st.container(border=True, key="cartao-upload"):
        estilo.titulo_cartao("01", "Planilha")
        arquivo = st.file_uploader("Planilha", type=["xlsx", "csv"], label_visibility="collapsed",
                                   key=f"uploader-{st.session_state.get('uploader_versao', 0)}")
        b1, b2, b3, _ = st.columns([0.27, 0.2, 0.2, 0.33])
        b1.button("Usar planilha demonstrativa", on_click=_usar_demo,
                  help="Carrega uma planilha fictícia com 9 linhas, incluindo um número digitado com erro.")
        b2.download_button("Baixar modelo", planilha.modelo_csv(), "modelo_processos.csv", "text/csv")
        b3.button("Limpar", on_click=_limpar)

    try:
        if arquivo is not None:
            nome_arquivo = arquivo.name
            leitura = planilha.ler(arquivo.getvalue(), arquivo.name)
        elif st.session_state.get("planilha_demo"):
            nome_arquivo = seed.PLANILHA_EXEMPLO.name
            leitura = planilha.ler_arquivo(seed.PLANILHA_EXEMPLO)
    except planilha.PlanilhaInvalida as e:
        erro = str(e)

    if erro:
        st.error(erro)
    if leitura is not None:
        st.write("")
        col1, col2 = st.columns([0.55, 0.45], gap="large")
        with col1:
            with st.container(border=True, key="cartao-identificados"):
                estilo.titulo_cartao("02", f"Processos identificados ({len(leitura.validas)})")
                itens = []
                for i, l in enumerate(leitura.validas, start=1):
                    d = l.dados or {}
                    det = " · ".join(x for x in (d.get("tribunal"), d.get("cliente"), d.get("responsavel")) if x)
                    novo = banco.obter_processo_por_numero(d["numero_limpo"]) is None
                    marca = estilo.badge("Novo", "azul") if novo else estilo.badge("Já monitorado", "neutro")
                    itens.append(f'<li><span class="n">{i}</span><div><div>{escape(d["numero"])}</div>'
                                 f'<div class="det">{escape(det)}</div></div><span class="dir">{marca}</span></li>')
                for l in leitura.invalidas:
                    itens.append(f'<li><span class="n x">×</span><div><div>{escape(l.numero_informado)}</div>'
                                 f'<div class="det">Linha {l.linha}: {escape(l.erro)}</div></div>'
                                 f'<span class="dir">{estilo.badge("Ignorado", "vermelho")}</span></li>')
                estilo.html(f'<ul class="lm-arquivos">{"".join(itens)}</ul>')
                rodape = f"Arquivo: {nome_arquivo}"
                if leitura.duplicadas:
                    rodape += f" · {leitura.duplicadas} linha(s) repetida(s) ignorada(s)"
                estilo.html(f'<div class="lm-muted" style="margin-top:10px">{escape(rodape)}</div>')
        with col2:
            with st.container(border=True, key="cartao-opcoes"):
                estilo.titulo_cartao("03", "Opções da importação")
                desativar = st.checkbox("Desativar processos que não estão nesta planilha",
                                        help="Eles deixam de ser consultados, mas o histórico é mantido.")
                consultar = st.checkbox("Consultar a fonte logo após importar", value=True)
                colunas = ", ".join(f"{k} → “{v}”" for k, v in leitura.colunas_reconhecidas.items())
                estilo.html(f'<div class="lm-muted" style="margin-top:8px">Colunas reconhecidas: {escape(colunas)}</div>'
                            f'<div class="lm-muted" style="margin-top:8px">Fonte de consulta: '
                            f'<b>{escape(fontes.FONTES[monitor.fonte_ativa()])}</b></div>')
        st.write("")
        if st.button("Importar processos", type="primary", disabled=not leitura.validas):
            resultado = monitor.importar(leitura, desativar_ausentes=desativar)
            texto = _resultado_importacao(resultado)
            if consultar:
                nome = fontes.FONTES[monitor.fonte_ativa()]
                with st.spinner(f"Consultando {nome}…"):
                    resumo = monitor.sincronizar(origem="painel")
                texto += " Consulta: " + c.texto_resumo_consulta(resumo)
            c.avisar("success", texto)
            _limpar()
            st.rerun()

    st.write("")
    estilo.secao("Carteira / 02", "Processos monitorados", c.ultima_consulta())
    processos = monitor.painel_processos(incluir_inativos=True)
    if not processos:
        c.estado_vazio("A carteira está vazia.", "carteira")
        return

    f1, f2, f3, f4 = st.columns(4)
    clientes = f1.multiselect("Cliente", sorted({p["cliente"] for p in processos if p["cliente"]}), placeholder="Todos")
    responsaveis = f2.multiselect("Responsável", sorted({p["responsavel"] for p in processos if p["responsavel"]}), placeholder="Todos")
    niveis = f3.multiselect("Nível de atenção", monitor.NIVEIS, placeholder="Todos")
    situacao = f4.selectbox("Monitoramento", ["Ativos", "Pausados", "Todos"])
    filtrados = [p for p in processos
                 if (not clientes or p["cliente"] in clientes) and (not responsaveis or p["responsavel"] in responsaveis)
                 and (not niveis or p["nivel"] in niveis)
                 and (situacao == "Todos" or bool(p["ativo"]) == (situacao == "Ativos"))]

    st.dataframe(pd.DataFrame([{
        "Nível": p["nivel"] if p["ativo"] else "Pausado",
        "Processo": p["numero"], "Tribunal": p["tribunal"], "Cliente": p["cliente"],
        "Parte contrária": p["parte_contraria"], "Responsável": p["responsavel"], "Classe": p["classe"],
        "Pendências": p["qtd_pendencias"],
        "Próximo prazo": monitor.formatar_data(p["proximo_prazo"]["prazo"]) if p["proximo_prazo"] else "",
        "Última movimentação": monitor.formatar_data(p["ultima_movimentacao"]),
        "Consulta": monitor.SITUACOES_CONSULTA.get(p["situacao_consulta"], p["situacao_consulta"]),
    } for p in filtrados]), hide_index=True, width="stretch")

    a1, a2, a3, _ = st.columns([0.4, 0.2, 0.2, 0.2])
    opcoes = {p["id"]: f"{p['numero']} · {p['cliente'] or 'sem cliente'}" for p in filtrados}
    if opcoes:
        escolhido = a1.selectbox("Processo", list(opcoes), format_func=opcoes.get, label_visibility="collapsed")
        proc = next(p for p in filtrados if p["id"] == escolhido)
        a2.button("Abrir movimentações", on_click=c.ir_para, args=("Movimentações", escolhido))
        if proc["ativo"]:
            if a3.button("Pausar monitoramento"):
                monitor.definir_ativo(escolhido, False)
                c.avisar("info", f"Monitoramento de {proc['numero']} pausado.")
                st.rerun()
        elif a3.button("Reativar monitoramento"):
            monitor.definir_ativo(escolhido, True)
            c.avisar("success", f"Monitoramento de {proc['numero']} reativado.")
            st.rerun()
