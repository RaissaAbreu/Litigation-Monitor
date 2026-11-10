"""Identidade visual do painel (mesma linguagem do Dispute AI e do Legal Flow): CSS e componentes em HTML."""

from __future__ import annotations

from html import escape

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&family=Source+Sans+3:wght@400;600;700&display=swap');

:root {
  --lm-navy: #13213f;
  --lm-navy-2: #1d2d52;
  --lm-ink: #14213d;
  --lm-texto: #2b2f3a;
  --lm-suave: #5f6472;
  --lm-ouro: #b07d2b;
  --lm-ouro-claro: #d9a441;
  --lm-fundo: #f4f2ec;
  --lm-papel: #faf8f3;
  --lm-cartao: #ffffff;
  --lm-borda: #e6e1d6;
  --lm-borda-forte: #d6d0c2;
}

html, body, .stApp, [class*="css"], .stMarkdown, button, input, textarea, select {
  font-family: 'Source Sans 3', 'Segoe UI', sans-serif;
}
.stApp { background: var(--lm-fundo); color: var(--lm-texto); }
.block-container { padding-top: 3.5rem; max-width: 1180px; }
header[data-testid="stHeader"] { background: transparent; }

/* ---------- barra lateral ---------- */
section[data-testid="stSidebar"] { background: var(--lm-navy); }
section[data-testid="stSidebar"] * { color: #f3f1ea; }
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] svg { fill: #f3f1ea; }
.lm-marca { text-align: center; padding: 8px 0 26px; border-bottom: 1px solid rgba(255,255,255,.14); margin-bottom: 26px; }
.lm-marca .nome { font-family: 'Cormorant Garamond', serif; font-size: 31px; letter-spacing: .16em; white-space: nowrap; color: #fff; font-weight: 500; }
.lm-marca .sub { font-size: 11px; font-weight: 700; letter-spacing: .34em; color: var(--lm-ouro-claro) !important; margin-top: 14px; line-height: 1.7; }
.lm-rotulo-lateral { font-size: 11px; font-weight: 600; letter-spacing: .32em; text-transform: uppercase; color: #f3f1ea; margin: 4px 0 10px; }
.lm-sep { border-top: 1px solid rgba(255,255,255,.14); margin: 22px 0; }
.lm-nota-lateral { font-size: 13px; color: #f3f1ea; display: flex; gap: 6px; align-items: center; margin-top: 10px; }
.lm-nota-lateral .ponto { width: 9px; height: 9px; border-radius: 50%; background: #fff; display: inline-block; }
.lm-nota-lateral .ponto.ok { background: #7cc79a; } .lm-nota-lateral .ponto.off { background: #8a90a3; }
.lm-rodape-lateral .titulo { font-size: 16px; margin-bottom: 4px; line-height: 1.5; }
.lm-rodape-lateral .meta { font-size: 13px; color: #a9afc0 !important; line-height: 1.6; }
section[data-testid="stSidebar"] [role="radiogroup"] label p { font-size: 17px; }
section[data-testid="stSidebar"] [role="radiogroup"] { gap: 4px; }
section[data-testid="stSidebar"] [data-baseweb="select"] > div { background: var(--lm-navy-2) !important; border-color: rgba(255,255,255,.35) !important; }
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"] { background: var(--lm-navy-2) !important; border-color: rgba(255,255,255,.35) !important; }
section[data-testid="stSidebar"] [data-testid="stSelectbox"] input { color: #f3f1ea !important; -webkit-text-fill-color: #f3f1ea; background: transparent !important; }
section[data-testid="stSidebar"] [data-testid="stSelectbox"] svg { fill: #f3f1ea; color: #f3f1ea; }
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { font-size: 14px; }

/* ---------- tipografia ---------- */
.lm-eyebrow { font-size: 11px; font-weight: 700; letter-spacing: .32em; text-transform: uppercase; color: var(--lm-ouro); margin-bottom: 8px; }
.lm-titulo { font-family: 'Cormorant Garamond', serif; font-weight: 500; font-size: 52px; line-height: 1.1; color: var(--lm-ink); margin: 6px 0 0; }
.lm-subtitulo { color: var(--lm-suave); font-size: 15.5px; margin-top: 8px; }
.lm-cabecalho { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding-bottom: 28px; border-bottom: 1px solid var(--lm-borda-forte); margin-bottom: 30px; }
.lm-selo { background: #f6e9c9; border: 1px solid #ecd59c; color: #6b4a10; border-radius: 999px; padding: 14px 28px; font-weight: 700; white-space: nowrap; }
.lm-selo::before { content: "●"; margin-right: 6px; }
.lm-secao-titulo { font-family: 'Cormorant Garamond', serif; font-weight: 500; font-size: 38px; color: var(--lm-ink); margin: 6px 0 4px; }
.lm-secao-texto { color: var(--lm-texto); font-size: 15px; margin-bottom: 18px; }
.lm-cartao-titulo { font-weight: 700; font-size: 17px; color: var(--lm-ink); margin-bottom: 10px; }
.lm-cartao-titulo .num { margin-right: 8px; }
.lm-rotulo { font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #2a3f6e; margin: 14px 0 8px; }
.lm-muted { color: var(--lm-suave); font-size: 14px; }

/* ---------- cartões ---------- */
div[class*="st-key-cartao"] {
  background: var(--lm-cartao); border: 1px solid var(--lm-borda) !important; border-radius: 18px;
  padding: 28px 32px; box-shadow: 0 2px 10px rgba(20, 33, 61, .04);
}

/* ---------- métricas ---------- */
.lm-metricas { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 16px; padding: 4px 0 26px; border-bottom: 1px solid var(--lm-borda-forte); margin-bottom: 26px; }
.lm-metrica .rotulo { font-weight: 700; color: var(--lm-ink); font-size: 16px; }
.lm-metrica .valor { font-weight: 700; color: var(--lm-ink); font-size: 40px; line-height: 1.2; }
.lm-metrica .valor.alerta { color: #a23b22; }
.lm-metrica .nota { font-size: 13px; color: var(--lm-suave); }

/* ---------- selos ---------- */
.lm-badge { display: inline-block; border-radius: 999px; padding: 4px 14px; font-size: 12.5px; font-weight: 700; border: 1px solid; margin: 2px 6px 2px 0; white-space: nowrap; }
.lm-badge.vermelho { background: #f9e0dc; color: #9b2c1f; border-color: #f0c4bd; }
.lm-badge.ambar    { background: #f8ecd0; color: #7a5212; border-color: #ecd59c; }
.lm-badge.azul     { background: #e5ebf6; color: #2a3f6e; border-color: #cbd6ec; }
.lm-badge.verde    { background: #dff0e4; color: #2a6a41; border-color: #bfdfc9; }
.lm-badge.neutro   { background: #f0eee8; color: #4b4f5c; border-color: #dedad0; }

/* ---------- destaque de prioridade (caixa grande) ---------- */
.lm-risco { border-radius: 16px; padding: 30px 32px; height: 100%; min-height: 220px; }
.lm-risco .rotulo { font-size: 11.5px; font-weight: 700; letter-spacing: .3em; text-transform: uppercase; }
.lm-risco .valor { font-family: 'Cormorant Garamond', serif; font-size: 76px; line-height: 1.05; margin: 6px 0 8px; }
.lm-risco .nota { font-weight: 700; font-size: 16px; }
.lm-risco.Crítica { background: #f6e1da; color: #a23b22; }
.lm-risco.Alta    { background: #f7ecd5; color: #8a5a14; }
.lm-risco.Média   { background: #e7ecf6; color: #2a3f6e; }
.lm-risco.Verificar { background: #efede7; color: #4b4f5c; }
.lm-risco.Emdia   { background: #e2f0e6; color: #2a6a41; }
.lm-risco.Inativo { background: #efede7; color: #4b4f5c; }

.lm-lista { margin: 0; padding-left: 20px; color: var(--lm-texto); }
.lm-lista li { margin: 6px 0; font-size: 15.5px; }

/* ---------- bloco de recomendação ---------- */
.lm-recomendacao { background: var(--lm-papel); border-left: 4px solid var(--lm-ouro); border-radius: 0 12px 12px 0; padding: 18px 24px; margin: 14px 0 18px; }
.lm-recomendacao .texto { font-family: 'Cormorant Garamond', serif; font-size: 25px; color: var(--lm-ink); line-height: 1.3; }

/* ---------- itens de demanda ---------- */
.lm-item-cab { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.lm-item-titulo { font-weight: 700; font-size: 17px; color: var(--lm-ink); }
.lm-item-titulo .codigo { margin-right: 8px; }
.lm-item-meta { color: var(--lm-suave); font-size: 15px; margin-top: 4px; }

/* ---------- lista numerada de arquivos ---------- */
.lm-arquivos { list-style: none; padding: 0; margin: 0; }
.lm-arquivos li { display: flex; align-items: center; gap: 14px; padding: 13px 18px; border-bottom: 1px solid #efebe2; font-size: 15.5px; }
.lm-arquivos li:last-child { border-bottom: none; }
.lm-arquivos .n { width: 24px; height: 24px; border-radius: 50%; background: #e7ecf6; color: #2a3f6e; font-size: 11px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; flex: none; }
.lm-arquivos .n.x { background: #f9e0dc; color: #9b2c1f; }
.lm-arquivos .det { color: var(--lm-suave); font-size: 13.5px; margin-top: 2px; }
.lm-arquivos .dir { margin-left: auto; white-space: nowrap; }

/* ---------- barras ---------- */
.lm-barras { display: grid; gap: 12px; }
.lm-barra { display: grid; grid-template-columns: 130px 1fr 34px; align-items: center; gap: 12px; font-size: 15px; }
.lm-barra .trilho { background: #f0ede5; border-radius: 4px; height: 12px; overflow: hidden; }
.lm-barra .preenchido { background: var(--lm-navy-2); height: 100%; border-radius: 0 4px 4px 0; min-width: 2px; }
.lm-barra .preenchido.vazio { background: transparent; }
.lm-barra .num { text-align: right; font-weight: 700; color: var(--lm-ink); font-variant-numeric: tabular-nums; }

/* ---------- linha do tempo ---------- */
.lm-tempo { list-style: none; margin: 0; padding: 0; }
.lm-tempo li { position: relative; padding: 0 0 18px 26px; border-left: 2px solid var(--lm-borda); margin-left: 6px; }
.lm-tempo li::before { content: ""; position: absolute; left: -7px; top: 3px; width: 12px; height: 12px; border-radius: 50%; background: var(--lm-ouro); border: 2px solid #fff; }
.lm-tempo .evento { font-weight: 700; color: var(--lm-ink); }
.lm-tempo .quando { color: var(--lm-suave); font-size: 13px; }

/* ---------- passos (como funciona) ---------- */
.lm-passo { display: flex; gap: 18px; padding: 16px 0; border-bottom: 1px solid #efebe2; }
.lm-passo:last-child { border-bottom: none; }
.lm-passo .n { font-family: 'Cormorant Garamond', serif; font-size: 34px; color: var(--lm-ouro); line-height: 1; min-width: 44px; }
.lm-passo .t { font-weight: 700; color: var(--lm-ink); font-size: 16.5px; }
.lm-passo .d { color: var(--lm-suave); font-size: 14.5px; margin-top: 2px; }

/* ---------- linha do tempo de movimentações ---------- */
.lm-tempo li.Alta::before { background: #a23b22; }
.lm-tempo li.Média::before { background: var(--lm-ouro); }
.lm-tempo li.Baixa::before { background: #c9c3b5; }
.lm-tempo .desc { color: var(--lm-texto); font-size: 14.5px; margin-top: 2px; }
.lm-tempo .linha-cab { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }

/* ---------- linhas de processo ---------- */
.lm-proc { display: grid; grid-template-columns: 96px 1fr auto; gap: 16px; align-items: center; padding: 14px 4px; border-bottom: 1px solid #efebe2; }
.lm-proc:last-child { border-bottom: none; }
.lm-proc .nivel { font-family: 'Cormorant Garamond', serif; font-size: 22px; font-weight: 600; }
.lm-proc .nivel.Crítica { color: #a23b22; } .lm-proc .nivel.Alta { color: #8a5a14; }
.lm-proc .nivel.Média { color: #2a3f6e; } .lm-proc .nivel.Verificar { color: #4b4f5c; } .lm-proc .nivel.Emdia { color: #2a6a41; }
.lm-proc .t { font-weight: 700; color: var(--lm-ink); font-size: 15.5px; }
.lm-proc .d { color: var(--lm-suave); font-size: 13.5px; margin-top: 2px; }
.lm-proc .dir { text-align: right; }

/* ---------- widgets ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 8px; padding: .65rem 1.6rem; border: 1px solid var(--lm-navy); background: #fff; color: var(--lm-navy); font-weight: 500;
}
.stButton > button:hover, .stDownloadButton > button:hover { border-color: var(--lm-ouro); color: var(--lm-navy); }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"] {
  background: var(--lm-navy); color: #fff; border-color: var(--lm-navy);
}
.stButton > button[kind="primary"]:hover { background: var(--lm-navy-2); color: #fff; }
.stTextInput input, .stTextArea textarea, .stDateInput input, [data-baseweb="select"] > div, [data-testid="stFileUploaderDropzone"],
.main [data-testid="stSelectbox"] [role="group"], .main [data-testid="stMultiSelect"] [role="group"] {
  background: var(--lm-papel) !important;
}
[data-testid="stFileUploaderDropzone"] { border: 1px dashed #e2c9a0; }
.stTabs [data-baseweb="tab-list"] { gap: 18px; border-bottom: 1px solid var(--lm-borda-forte); }
.stTabs [data-baseweb="tab"] { padding: 8px 0; }
.stTabs [aria-selected="true"] p { color: var(--lm-ink); }
.stTabs [data-baseweb="tab-highlight"] { background: var(--lm-ouro); }
.lm-aviso-rodape { color: var(--lm-suave); font-size: 14.5px; margin-top: 14px; }

@media (max-width: 760px) {
  .lm-titulo { font-size: 38px; }
  .lm-cabecalho { flex-direction: column; }
  div[class*="st-key-cartao"] { padding: 20px; }
  .lm-barra { grid-template-columns: 100px 1fr 30px; }
  .lm-proc { grid-template-columns: 1fr; gap: 4px; }
  .lm-proc .dir { text-align: left; }
}
</style>
"""

TOM_NIVEL = {"Crítica": "vermelho", "Alta": "ambar", "Média": "azul", "Verificar": "neutro", "Em dia": "verde"}
TOM_RELEVANCIA = {"Alta": "vermelho", "Média": "ambar", "Baixa": "neutro"}
TOM_STATUS = {"Pendente": "ambar", "Em andamento": "azul", "Concluída": "verde", "Sem providência": "neutro",
              "Informativa": "neutro", "Histórico": "neutro"}
TOM_SITUACAO_PRAZO = {
    "vencido": ("Prazo vencido", "vermelho"), "hoje": ("Vence hoje", "vermelho"),
    "proximo": ("Prazo próximo", "ambar"), "no_prazo": ("No prazo", "verde"), "a_confirmar": ("Data a confirmar", "ambar"),
}
TOM_CONSULTA = {"pendente": "neutro", "ok": "verde", "nao_localizado": "ambar", "erro": "vermelho"}


def classe_nivel(nivel: str) -> str:
    return nivel.replace(" ", "")


def aplicar() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def html(conteudo: str) -> None:
    st.markdown(conteudo, unsafe_allow_html=True)


def badge(texto: str, tom: str = "neutro") -> str:
    return f'<span class="lm-badge {tom}">{escape(str(texto))}</span>'


def cabecalho(eyebrow: str, titulo: str, subtitulo: str, selo: str | None = None) -> None:
    selo_html = f'<div class="lm-selo">{escape(selo)}</div>' if selo else ""
    html(f"""<div class="lm-cabecalho"><div>
      <div class="lm-eyebrow">{escape(eyebrow)}</div>
      <div class="lm-titulo">{escape(titulo)}</div>
      <div class="lm-subtitulo">{escape(subtitulo)}</div></div>{selo_html}</div>""")


def secao(eyebrow: str, titulo: str, texto: str = "") -> None:
    html(f"""<div class="lm-eyebrow">{escape(eyebrow)}</div>
    <div class="lm-secao-titulo">{escape(titulo)}</div>
    {f'<div class="lm-secao-texto">{escape(texto)}</div>' if texto else ''}""")


def titulo_cartao(numero: str | None, texto: str) -> None:
    num = f'<span class="num">{escape(numero)}</span>' if numero else ""
    html(f'<div class="lm-cartao-titulo">{num}{escape(texto)}</div>')


def metricas(itens: list[tuple[str, int | str, bool]]) -> None:
    """itens: (rótulo, valor, destacar_em_vermelho)."""
    blocos = "".join(
        f'<div class="lm-metrica"><div class="rotulo">{escape(r)}</div>'
        f'<div class="valor{" alerta" if alerta and v else ""}">{escape(str(v))}</div></div>'
        for r, v, alerta in itens
    )
    html(f'<div class="lm-metricas">{blocos}</div>')


def barras(contagens: dict[str, int]) -> None:
    """Barras horizontais de uma só cor (magnitude). O número fica sempre visível ao lado."""
    maximo = max(contagens.values(), default=0) or 1
    linhas = "".join(
        f'<div class="lm-barra" title="{escape(k)}: {v}"><span>{escape(k)}</span>'
        f'<div class="trilho"><div class="preenchido{" vazio" if not v else ""}" style="width:{v / maximo * 100:.0f}%"></div></div>'
        f'<span class="num">{v}</span></div>'
        for k, v in contagens.items()
    )
    html(f'<div class="lm-barras">{linhas}</div>')


def recomendacao(eyebrow: str, texto: str) -> None:
    html(f'<div class="lm-recomendacao"><div class="lm-eyebrow">{escape(eyebrow)}</div>'
         f'<div class="texto">{escape(texto)}</div></div>')
