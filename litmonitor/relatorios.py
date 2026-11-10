"""Relatórios periódicos: processos que exigem atenção (PDF e Excel) e resumo diário por e-mail."""

from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from . import VERSAO, banco, config, mensagens, monitor
from .monitor import formatar_data

TIPOS = {"semanal": "Relatório semanal", "sob_demanda": "Relatório sob demanda"}
NAVY, OURO, TEXTO, SUAVE, BORDA = (19, 33, 63), (176, 125, 43), (43, 47, 58), (95, 100, 114), (230, 225, 214)
COR_NIVEL = {"Crítica": (162, 59, 34), "Alta": (138, 90, 20), "Média": (42, 63, 110), "Verificar": (75, 79, 92),
             "Em dia": (42, 106, 65)}


# --------------------------------------------------------------------------- dados


def dados_relatorio(inicio: date, fim: date, referencia: date | None = None) -> dict[str, pd.DataFrame]:
    referencia = referencia or monitor.hoje()
    processos = monitor.painel_processos(referencia)

    atencao = []
    for p in processos:
        if not p["exige_atencao"]:
            continue
        if p["problema_consulta"] and not p["pendencias"]:
            atencao.append({
                "Nível": p["nivel"], "Processo": p["numero"], "Cliente": p["cliente"], "Responsável": p["responsavel"],
                "Movimentação": monitor.SITUACOES_CONSULTA[p["situacao_consulta"]], "Data": "",
                "Classificação": "Consulta", "Prazo": "", "Situação do prazo": "",
                "Providência sugerida": p["erro_consulta"] or "Conferir o número e a fonte de dados.",
            })
        for m in sorted(p["pendencias"], key=lambda m: (m.get("prazo") or "9999", m["data_hora"])):
            atencao.append({
                "Nível": p["nivel"], "Processo": p["numero"], "Cliente": p["cliente"], "Responsável": p["responsavel"],
                "Movimentação": m["descricao"], "Data": formatar_data(m["data_hora"]), "Classificação": m["rotulo"],
                "Prazo": formatar_data(m["prazo"]) if m.get("prazo") else "",
                "Situação do prazo": monitor.texto_prazo(m, referencia),
                "Providência sugerida": m["providencia"],
            })

    desde = datetime.combine(inicio, datetime.min.time()).isoformat()
    ate = datetime.combine(fim + timedelta(days=1), datetime.min.time()).isoformat()
    periodo = [m for m in banco.listar_movimentacoes(desde=desde, apenas_novas=True) if m["detectada_em"] < ate]
    movimentos = [{
        "Detectada em": formatar_data(m["detectada_em"]), "Data do movimento": formatar_data(m["data_hora"]),
        "Processo": m["numero"], "Cliente": m["cliente"], "Movimentação": m["descricao"],
        "Classificação": m["rotulo"], "Relevância": m["relevancia"], "Status": m["status"],
    } for m in periodo]

    carteira = [{
        "Processo": p["numero"], "Tribunal": p["tribunal"], "Cliente": p["cliente"],
        "Parte contrária": p["parte_contraria"], "Responsável": p["responsavel"], "Classe": p["classe"],
        "Nível de atenção": p["nivel"], "Pendências": p["qtd_pendencias"],
        "Próximo prazo": formatar_data(p["proximo_prazo"]["prazo"]) if p["proximo_prazo"] else "",
        "Última movimentação": formatar_data(p["ultima_movimentacao"]),
        "Situação da consulta": monitor.SITUACOES_CONSULTA.get(p["situacao_consulta"], p["situacao_consulta"]),
        "Última consulta": formatar_data(p["ultima_consulta_em"]),
    } for p in processos]

    return {
        "Exigem atenção": pd.DataFrame(atencao, columns=["Nível", "Processo", "Cliente", "Responsável", "Movimentação",
                                                         "Data", "Classificação", "Prazo", "Situação do prazo",
                                                         "Providência sugerida"]),
        "Movimentações do período": pd.DataFrame(movimentos, columns=["Detectada em", "Data do movimento", "Processo",
                                                                      "Cliente", "Movimentação", "Classificação",
                                                                      "Relevância", "Status"]),
        "Carteira": pd.DataFrame(carteira),
    }


# --------------------------------------------------------------------------- Excel


def gerar_excel(tabelas: dict[str, pd.DataFrame]) -> bytes:
    from openpyxl.styles import Alignment, Font, PatternFill

    saida = io.BytesIO()
    with pd.ExcelWriter(saida, engine="openpyxl") as escritor:
        for nome, df in tabelas.items():
            df.to_excel(escritor, sheet_name=nome[:31], index=False)
            planilha = escritor.sheets[nome[:31]]
            for celula in planilha[1]:
                celula.font = Font(bold=True, color="FFFFFF")
                celula.fill = PatternFill("solid", fgColor="13213F")
                celula.alignment = Alignment(vertical="center", wrap_text=True)
            for i, coluna in enumerate(df.columns, start=1):
                largura = max([len(str(coluna))] + [len(str(v)) for v in df[coluna].head(200)]) + 2
                planilha.column_dimensions[planilha.cell(1, i).column_letter].width = min(max(largura, 10), 60)
            planilha.freeze_panes = "A2"
            if len(df):
                planilha.auto_filter.ref = planilha.dimensions
    return saida.getvalue()


# --------------------------------------------------------------------------- PDF


def _txt(valor: Any) -> str:
    """As fontes padrão do PDF usam Latin-1: troca os poucos caracteres fora dele."""
    texto = str(valor if valor is not None else "")
    for de, para in {"—": "-", "–": "-", "→": "->", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "≥": ">=",
                     "≤": "<="}.items():
        texto = texto.replace(de, para)
    return texto.encode("latin-1", "replace").decode("latin-1")


class _PDF(FPDF):
    titulo = ""

    def header(self) -> None:
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, 16, "F")
        self.set_xy(12, 5)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(255, 255, 255)
        self.cell(0, 6, "LITIGATION MONITOR", new_x=XPos.LMARGIN, new_y=YPos.TOP)
        self.set_xy(-110, 5)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(217, 164, 65)
        self.cell(98, 6, _txt(self.titulo.upper()), align="R")
        self.set_y(24)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*SUAVE)
        self.cell(0, 5, _txt(f"Relatório gerado automaticamente em {datetime.now():%d/%m/%Y %H:%M} · versão {VERSAO} · "
                             "prazos estimados devem ser confirmados no processo."), align="L")
        self.cell(0, 5, f"{self.page_no()}/{{nb}}", align="R")


def _eyebrow(pdf: _PDF, texto: str) -> None:
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*OURO)
    pdf.cell(0, 5, _txt(" ".join(texto.upper())), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _titulo(pdf: _PDF, texto: str, tamanho: float = 20) -> None:
    pdf.set_font("Times", "", tamanho)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, tamanho * 0.5, _txt(texto), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def gerar_pdf(tabelas: dict[str, pd.DataFrame], titulo: str, inicio: date, fim: date, ind: dict[str, Any]) -> bytes:
    pdf = _PDF(orientation="L", unit="mm", format="A4")
    pdf.titulo = titulo
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(True, margin=16)
    pdf.set_margins(12, 20, 12)
    pdf.add_page()

    _eyebrow(pdf, "Monitoramento processual")
    _titulo(pdf, titulo, 26)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*SUAVE)
    pdf.cell(0, 6, _txt(f"Período de {formatar_data(inicio)} a {formatar_data(fim)} · fonte: "
                        f"{monitor.fontes.FONTES.get(monitor.fonte_ativa(), '')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # indicadores
    metricas = [("Processos monitorados", ind["processos"], False), ("Exigem atenção", ind["exigem_atencao"], False),
                ("Prazos vencidos", ind["vencidos"], True),
                (f"Vencem em até {config.dias_alerta_prazo()} dias", ind["vencem_breve"], True),
                ("Novas movimentações (7 dias)", ind["novas_7_dias"], False)]
    largura = (pdf.w - 24) / len(metricas)
    y = pdf.get_y()
    for i, (rotulo, valor, alerta) in enumerate(metricas):
        x = 12 + i * largura
        pdf.set_xy(x, y)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*NAVY)
        pdf.cell(largura - 4, 5, _txt(rotulo))
        pdf.set_xy(x, y + 6)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(*((162, 59, 34) if alerta and valor else NAVY))
        pdf.cell(largura - 4, 10, str(valor))
    pdf.set_y(y + 20)
    pdf.set_draw_color(*BORDA)
    pdf.line(12, pdf.get_y(), pdf.w - 12, pdf.get_y())
    pdf.ln(5)

    def tabela(df: pd.DataFrame, colunas: list[tuple[str, float]], destacar_nivel: bool = False) -> None:
        total = sum(l for _, l in colunas)
        escala = (pdf.w - 24) / total
        larguras = [l * escala for _, l in colunas]

        def cabecalho() -> None:
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_fill_color(*NAVY)
            pdf.set_text_color(255, 255, 255)
            for (nome, _), w in zip(colunas, larguras):
                pdf.cell(w, 7, _txt(nome), border=0, fill=True)
            pdf.ln(7)

        cabecalho()
        pdf.set_font("Helvetica", "", 7.8)
        for indice, (_, linha) in enumerate(df.iterrows()):
            textos = [_txt(linha.get(nome, "")) for nome, _ in colunas]
            linhas_necessarias = max(len(pdf.multi_cell(w, 4, t, align="L", dry_run=True, output="LINES")) for w, t in zip(larguras, textos))
            altura = max(linhas_necessarias * 4 + 2, 7)
            if pdf.get_y() + altura > pdf.h - 16:
                pdf.add_page()
                cabecalho()
                pdf.set_font("Helvetica", "", 7.8)
            y0 = pdf.get_y()
            if indice % 2:
                pdf.set_fill_color(250, 248, 243)
                pdf.rect(12, y0, pdf.w - 24, altura, "F")
            x = 12
            for (nome, _), w, t in zip(colunas, larguras, textos):
                pdf.set_xy(x, y0 + 1)
                if destacar_nivel and nome == "Nível":
                    pdf.set_font("Helvetica", "B", 7.8)
                    pdf.set_text_color(*COR_NIVEL.get(t, SUAVE))
                else:
                    pdf.set_font("Helvetica", "", 7.8)
                    pdf.set_text_color(*TEXTO)
                pdf.multi_cell(w, 4, t, align="L")
                x += w
            pdf.set_y(y0 + altura)
            pdf.set_draw_color(*BORDA)
            pdf.line(12, pdf.get_y(), pdf.w - 12, pdf.get_y())

    _eyebrow(pdf, "Prioridades")
    _titulo(pdf, "Processos que exigem atenção")
    pdf.ln(2)
    atencao = tabelas["Exigem atenção"]
    if atencao.empty:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*SUAVE)
        pdf.cell(0, 8, "Nenhum processo exige atenção no momento.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        tabela(atencao, [("Nível", 14), ("Processo", 42), ("Cliente", 30), ("Movimentação", 48), ("Classificação", 26),
                         ("Situação do prazo", 34), ("Providência sugerida", 62), ("Responsável", 22)], True)

    pdf.ln(6)
    if pdf.get_y() > pdf.h - 50:
        pdf.add_page()
    _eyebrow(pdf, "Período")
    _titulo(pdf, "Movimentações detectadas no período")
    pdf.ln(2)
    periodo = tabelas["Movimentações do período"]
    if periodo.empty:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*SUAVE)
        pdf.cell(0, 8, "Nenhuma movimentação nova no período.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        tabela(periodo, [("Data do movimento", 20), ("Processo", 40), ("Cliente", 32), ("Movimentação", 70),
                         ("Classificação", 30), ("Relevância", 16), ("Status", 20)])
    return bytes(pdf.output())


# --------------------------------------------------------------------------- geração e registro


def gerar(tipo: str = "sob_demanda", origem: str = "painel", fim: date | None = None, dias: int = 7) -> dict[str, Any]:
    """Gera PDF + Excel, grava em dados/relatorios e registra no banco."""
    banco.inicializar()
    fim = fim or monitor.hoje()
    inicio = fim - timedelta(days=dias - 1)
    tabelas = dados_relatorio(inicio, fim, fim)
    ind = monitor.indicadores(fim)
    titulo = TIPOS.get(tipo, "Relatório")
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta = config.dir_relatorios()
    pdf = pasta / f"litigation-monitor_{tipo}_{carimbo}.pdf"
    xlsx = pasta / f"litigation-monitor_{tipo}_{carimbo}.xlsx"
    pdf.write_bytes(gerar_pdf(tabelas, titulo, inicio, fim, ind))
    xlsx.write_bytes(gerar_excel(tabelas))
    processos_atencao = tabelas["Exigem atenção"]["Processo"].nunique() if not tabelas["Exigem atenção"].empty else 0
    rid = banco.inserir_relatorio({
        "tipo": tipo, "origem": origem, "periodo_inicio": inicio.isoformat(), "periodo_fim": fim.isoformat(),
        "arquivo_pdf": pdf.name, "arquivo_xlsx": xlsx.name, "processos_atencao": int(processos_atencao),
    })
    relatorio = banco.obter_relatorio(rid) or {}
    return {"relatorio": relatorio, "indicadores": ind}


def caminho_arquivo(relatorio: dict[str, Any], formato: str) -> Path:
    nome = relatorio["arquivo_pdf"] if formato == "pdf" else relatorio["arquivo_xlsx"]
    return config.dir_relatorios() / Path(nome).name


def notificacao_relatorio(relatorio: dict[str, Any], ind: dict[str, Any]) -> dict[str, Any]:
    return {"tipo": "relatorio_semanal", "email": mensagens.email_relatorio(relatorio, ind)}


def resumo_diario(referencia: date | None = None, limite: int = 8) -> dict[str, Any]:
    """E-mail do resumo diário (o n8n envia toda manhã)."""
    referencia = referencia or monitor.hoje()
    ind = monitor.indicadores(referencia)
    itens = []
    for p in monitor.painel_processos(referencia):
        if not p["exige_atencao"]:
            continue
        if p["proximo_prazo"]:
            texto = f"{p['proximo_prazo']['rotulo']} · {monitor.texto_prazo(p['proximo_prazo'], referencia)}"
        elif p["pendencias"]:
            texto = f"{p['pendencias'][0]['rotulo']} · {monitor.texto_prazo(p['pendencias'][0], referencia)}"
        else:
            texto = monitor.SITUACOES_CONSULTA[p["situacao_consulta"]]
        itens.append({"titulo": f"{p['nivel']} · {p['numero']}", "texto": f"{p['cliente'] or '—'} · {texto}"})
    return {
        "tipo": "resumo_diario",
        "quantidade": ind["exigem_atencao"],
        "itens": itens[:limite],
        "email": mensagens.email_resumo_diario(ind, itens[:limite], formatar_data(referencia)),
    }
