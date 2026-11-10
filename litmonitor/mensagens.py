"""E-mails de alerta (enviados pelo n8n via Gmail/SMTP), no mesmo visual do painel."""

from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import quote

from . import config

NAVY, OURO, TEXTO, SUAVE, BORDA, FUNDO = "#13213f", "#b07d2b", "#2b2f3a", "#5f6472", "#e6e1d6", "#f4f2ec"
TOM = {"Alta": ("#f9e0dc", "#9b2c1f"), "Média": ("#f8ecd0", "#7a5212"), "Baixa": ("#f0eee8", "#4b4f5c")}
TITULOS = {
    "movimentacao_relevante": "Nova movimentação relevante",
    "prazo_proximo": "Prazo próximo do vencimento",
    "prazo_hoje": "Prazo vence hoje",
    "prazo_vencido": "Prazo vencido",
}


def _data(valor: str | None) -> str:
    return f"{valor[8:10]}/{valor[5:7]}/{valor[0:4]}" if valor else "—"


def link_processo(numero: str) -> str:
    return f"{config.url_painel()}/?processo={quote(numero)}"


def _botao(texto: str, url: str) -> str:
    return (f'<a href="{escape(url)}" style="display:inline-block;background:{NAVY};color:#ffffff;text-decoration:none;'
            f'padding:11px 22px;border-radius:8px;font-weight:600;margin:4px 8px 4px 0">{escape(texto)}</a>')


def _selo(texto: str, relevancia: str = "Baixa") -> str:
    fundo, cor = TOM.get(relevancia, TOM["Baixa"])
    return (f'<span style="display:inline-block;background:{fundo};color:{cor};border-radius:999px;padding:3px 12px;'
            f'font-size:12px;font-weight:700;margin-right:6px">{escape(texto)}</span>')


def _fatos(linhas: list[tuple[str, str]]) -> str:
    return '<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse">' + "".join(
        f'<tr><td style="padding:8px 12px 8px 0;color:{SUAVE};font-size:13px;width:140px;vertical-align:top;'
        f'border-bottom:1px solid {BORDA}">{escape(r)}</td><td style="padding:8px 0;font-size:14px;color:{TEXTO};'
        f'border-bottom:1px solid {BORDA}">{escape(v)}</td></tr>' for r, v in linhas) + "</table>"


def _layout(sobretitulo: str, titulo: str, corpo: str) -> str:
    return f"""<!doctype html><html><body style="margin:0;background:{FUNDO};font-family:'Segoe UI',Arial,sans-serif;color:{TEXTO}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FUNDO};padding:24px 0"><tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%">
<tr><td style="background:{NAVY};padding:18px 28px;border-radius:14px 14px 0 0">
  <div style="font-family:Georgia,serif;color:#ffffff;font-size:20px;letter-spacing:4px">LITIGATION MONITOR</div>
  <div style="color:#d9a441;font-size:10px;letter-spacing:4px;font-weight:700;margin-top:4px">MONITORAMENTO DE PROCESSOS</div>
</td></tr>
<tr><td style="background:#ffffff;padding:28px;border:1px solid {BORDA};border-top:none;border-radius:0 0 14px 14px">
  <div style="color:{OURO};font-size:11px;letter-spacing:3px;font-weight:700;text-transform:uppercase">{escape(sobretitulo)}</div>
  <div style="font-family:Georgia,serif;color:{NAVY};font-size:26px;margin:6px 0 18px">{escape(titulo)}</div>
  {corpo}
</td></tr>
<tr><td style="padding:14px 6px;color:{SUAVE};font-size:12px">Mensagem automática do Litigation Monitor. Prazos estimados
devem ser confirmados no processo.</td></tr>
</table></td></tr></table></body></html>"""


def _email(assunto: str, html: str) -> dict[str, str]:
    return {"de": config.email_remetente(), "para": config.email_destino(), "assunto": assunto, "html": html}


def email_movimentacao(mov: dict[str, Any], tipo: str, texto_prazo: str) -> dict[str, str]:
    titulo = f"{TITULOS[tipo]}: {mov['rotulo']}"
    corpo = (
        f'<div style="margin-bottom:14px">{_selo("Relevância " + mov["relevancia"].lower(), mov["relevancia"])}'
        f'{_selo(texto_prazo, "Alta" if tipo in ("prazo_vencido", "prazo_hoje") else "Média")}</div>'
        + _fatos([
            ("Processo", mov["numero"]), ("Cliente", mov.get("cliente") or "—"),
            ("Tribunal", f"{mov.get('tribunal', '')} · {mov.get('grau') or '—'}"),
            ("Movimentação", f"{mov['descricao']} ({_data(mov['data_hora'])})"),
            ("Classificação", mov["rotulo"]), ("Prazo", texto_prazo), ("Responsável", mov.get("responsavel") or "—"),
        ])
        + f'<div style="background:#faf8f3;border-left:4px solid {OURO};padding:14px 18px;margin:20px 0;'
          f'border-radius:0 10px 10px 0"><div style="color:{OURO};font-size:10px;letter-spacing:3px;font-weight:700">'
          f'PROVIDÊNCIA SUGERIDA</div><div style="font-family:Georgia,serif;font-size:18px;color:{NAVY};margin-top:6px">'
          f'{escape(mov["providencia"])}</div></div>'
    )
    if mov.get("prazo_situacao") == "estimado":
        corpo += (f'<div style="color:{SUAVE};font-size:12px;margin-bottom:16px">Prazo estimado automaticamente '
                  f'({escape(mov.get("prazo_regra", ""))}). Confirme no processo.</div>')
    corpo += _botao("Abrir no painel", link_processo(mov["numero"]))
    assunto = f"[Litigation Monitor] {TITULOS[tipo]} · {mov['rotulo']} · {mov['numero']}"
    return _email(assunto, _layout("Alerta processual", titulo, corpo))


def email_resumo_diario(ind: dict[str, Any], itens: list[dict[str, str]], data: str) -> dict[str, str]:
    metricas = [("Exigem atenção", ind["exigem_atencao"], False), ("Prazos vencidos", ind["vencidos"], True),
                (f"Vencem em até {config.dias_alerta_prazo()} dias", ind["vencem_breve"], True),
                ("Novas (7 dias)", ind["novas_7_dias"], False)]
    corpo = '<table role="presentation" width="100%" style="margin-bottom:20px"><tr>' + "".join(
        f'<td style="vertical-align:top;padding-right:8px"><div style="font-size:12px;color:{SUAVE}">{escape(r)}</div>'
        f'<div style="font-size:30px;font-weight:700;color:{"#a23b22" if alerta and v else NAVY}">{v}</div></td>'
        for r, v, alerta in metricas) + "</tr></table>"
    if itens:
        corpo += _fatos([(i["titulo"], i["texto"]) for i in itens])
    else:
        corpo += f'<div style="color:{SUAVE}">Nenhum processo exige atenção hoje.</div>'
    corpo += '<div style="margin-top:20px">' + _botao("Abrir painel", config.url_painel()) + "</div>"
    return _email(f"[Litigation Monitor] Resumo diário · {data} · {ind['exigem_atencao']} processo(s) exigem atenção",
                  _layout("Resumo diário", f"Processos que exigem atenção — {data}", corpo))


def email_relatorio(relatorio: dict[str, Any], ind: dict[str, Any]) -> dict[str, str]:
    periodo = f"{_data(relatorio['periodo_inicio'])} a {_data(relatorio['periodo_fim'])}"
    base = f"{config.url_api_publica()}/relatorios/{relatorio['id']}"
    corpo = _fatos([
        ("Processos monitorados", str(ind["processos"])), ("Exigem atenção", str(relatorio["processos_atencao"])),
        ("Prazos vencidos", str(ind["vencidos"])), ("Novas movimentações (7 dias)", str(ind["novas_7_dias"])),
    ]) + '<div style="margin-top:20px">' + _botao("Baixar PDF", f"{base}/pdf") + _botao("Baixar Excel", f"{base}/xlsx") \
        + _botao("Abrir painel", config.url_painel()) + "</div>"
    return _email(f"[Litigation Monitor] Relatório semanal · {periodo}",
                  _layout("Relatório semanal", f"Relatório de {periodo}", corpo))
