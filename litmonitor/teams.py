"""Mensagens para o Microsoft Teams (Adaptive Cards enviados pelo n8n a um webhook de Workflows do Teams)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from . import config

COR = {"Alta": "attention", "Média": "warning", "Baixa": "default"}
TITULOS = {
    "movimentacao_relevante": "Nova movimentação relevante",
    "prazo_proximo": "Prazo próximo do vencimento",
    "prazo_hoje": "Prazo vence hoje",
    "prazo_vencido": "Prazo vencido",
}


def _data(valor: str | None) -> str:
    if not valor:
        return "—"
    return f"{valor[8:10]}/{valor[5:7]}/{valor[0:4]}"


def link_processo(numero: str) -> str:
    return f"{config.url_painel()}/?processo={quote(numero)}"


def envelope(corpo: list[dict[str, Any]], acoes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard", "version": "1.4", "msteams": {"width": "Full"},
                "body": corpo, "actions": acoes,
            },
        }],
    }


def _cabecalho(sobretitulo: str, titulo: str, cor: str = "default") -> list[dict[str, Any]]:
    return [
        {"type": "TextBlock", "text": sobretitulo.upper(), "size": "Small", "weight": "Bolder", "color": "warning",
         "spacing": "None"},
        {"type": "TextBlock", "text": titulo, "size": "Large", "weight": "Bolder", "wrap": True, "color": cor},
    ]


def cartao_movimentacao(mov: dict[str, Any], tipo: str, texto_prazo: str) -> dict[str, Any]:
    fatos = [
        {"title": "Processo", "value": mov["numero"]},
        {"title": "Cliente", "value": mov.get("cliente") or "—"},
        {"title": "Tribunal", "value": f"{mov.get('tribunal', '')} · {mov.get('grau') or '—'}"},
        {"title": "Movimentação", "value": f"{mov['descricao']} ({_data(mov['data_hora'])})"},
        {"title": "Classificação", "value": f"{mov['rotulo']} · relevância {mov['relevancia'].lower()}"},
        {"title": "Prazo", "value": texto_prazo},
        {"title": "Responsável", "value": mov.get("responsavel") or "—"},
    ]
    corpo = _cabecalho("Litigation Monitor", f"{TITULOS[tipo]}: {mov['rotulo']}",
                       "attention" if tipo in ("prazo_vencido", "prazo_hoje") else COR.get(mov["relevancia"], "default"))
    corpo += [
        {"type": "FactSet", "facts": fatos},
        {"type": "TextBlock", "text": f"**Providência sugerida:** {mov['providencia']}", "wrap": True},
    ]
    if mov.get("prazo_situacao") == "estimado":
        corpo.append({"type": "TextBlock", "wrap": True, "size": "Small", "isSubtle": True,
                      "text": f"Prazo estimado automaticamente ({mov.get('prazo_regra', '')}). Confirme no processo."})
    return envelope(corpo, [{"type": "Action.OpenUrl", "title": "Abrir no painel", "url": link_processo(mov["numero"])}])


def cartao_resumo_diario(ind: dict[str, Any], itens: list[dict[str, str]], data: str) -> dict[str, Any]:
    corpo = _cabecalho("Litigation Monitor · resumo diário", f"Processos que exigem atenção — {data}")
    corpo.append({"type": "ColumnSet", "columns": [
        {"type": "Column", "width": "stretch", "items": [
            {"type": "TextBlock", "text": rotulo, "size": "Small", "isSubtle": True, "wrap": True},
            {"type": "TextBlock", "text": str(valor), "size": "ExtraLarge", "weight": "Bolder",
             "color": "attention" if alerta and valor else "default"}]}
        for rotulo, valor, alerta in (
            ("Exigem atenção", ind["exigem_atencao"], False), ("Prazos vencidos", ind["vencidos"], True),
            (f"Vencem em até {config.dias_alerta_prazo()} dias", ind["vencem_breve"], True),
            ("Novas (7 dias)", ind["novas_7_dias"], False))
    ]})
    if itens:
        corpo.append({"type": "TextBlock", "text": "Destaques", "weight": "Bolder", "spacing": "Medium"})
        corpo.append({"type": "FactSet", "facts": [{"title": i["titulo"], "value": i["texto"]} for i in itens]})
    else:
        corpo.append({"type": "TextBlock", "text": "Nenhum processo exige atenção hoje.", "wrap": True})
    return envelope(corpo, [{"type": "Action.OpenUrl", "title": "Abrir painel", "url": config.url_painel()}])


def cartao_relatorio(relatorio: dict[str, Any], ind: dict[str, Any]) -> dict[str, Any]:
    corpo = _cabecalho("Litigation Monitor · relatório semanal",
                       f"Relatório de {_data(relatorio['periodo_inicio'])} a {_data(relatorio['periodo_fim'])}")
    corpo.append({"type": "FactSet", "facts": [
        {"title": "Processos monitorados", "value": str(ind["processos"])},
        {"title": "Exigem atenção", "value": str(relatorio["processos_atencao"])},
        {"title": "Prazos vencidos", "value": str(ind["vencidos"])},
        {"title": "Novas movimentações (7 dias)", "value": str(ind["novas_7_dias"])},
    ]})
    base = f"{config.url_api_publica()}/relatorios/{relatorio['id']}"
    return envelope(corpo, [
        {"type": "Action.OpenUrl", "title": "Baixar PDF", "url": f"{base}/pdf"},
        {"type": "Action.OpenUrl", "title": "Baixar Excel", "url": f"{base}/xlsx"},
        {"type": "Action.OpenUrl", "title": "Abrir painel", "url": config.url_painel()},
    ])
