"""Gera os workflows do n8n (n8n/workflows/*.json).

Os JSON gerados já estão no repositório; rode este script só se quiser alterar os fluxos por código:
    python scripts/gerar_workflows_n8n.py
"""

import json
import uuid
from pathlib import Path

API = "http://api:8000"  # nome do serviço no docker-compose
DESTINO = Path(__file__).resolve().parent.parent / "n8n" / "workflows"


def no(nome, tipo, versao, posicao, parametros, **extra):
    return {"parameters": parametros, "name": nome, "type": tipo, "typeVersion": versao, "position": posicao,
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"litigation-monitor/{nome}")), **extra}


def http(nome, posicao, url, corpo=None, metodo="POST", timeout=30000, **extra):
    parametros = {"method": metodo, "url": url, "options": {"timeout": timeout}}
    if corpo is not None:
        parametros.update(sendBody=True, specifyBody="json", jsonBody=corpo)
    return no(nome, "n8n-nodes-base.httpRequest", 4.2, posicao, parametros, **extra)


def agendamento(nome, posicao, cron):
    return no(nome, "n8n-nodes-base.scheduleTrigger", 1.2, posicao,
              {"rule": {"interval": [{"field": "cronExpression", "expression": cron}]}})


def manual(posicao):
    return no("Executar agora (teste)", "n8n-nodes-base.manualTrigger", 1, posicao, {})


def tem_canal(nome, posicao, expressao):
    return no(nome, "n8n-nodes-base.if", 2, posicao, {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "conditions": [{"id": "canal-teams", "leftValue": expressao, "rightValue": "",
                            "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
            "combinator": "and",
        },
        "options": {},
    })


def liga(*destinos):
    return [[{"node": d, "type": "main", "index": 0}] for d in destinos]


def se(sim, nao):
    return [[{"node": sim, "type": "main", "index": 0}], [{"node": nao, "type": "main", "index": 0}]]


def registrar(nome, posicao, tipo, situacao, movimentacao_id="null"):
    corpo = ("={{ JSON.stringify({ tipo: " + tipo + ", situacao: " + situacao + ", movimentacao_id: "
             + movimentacao_id + ", destino: 'Microsoft Teams' }) }}")
    return http(nome, posicao, f"{API}/notificacoes", corpo)


def fluxo(id_, nome, nos, conexoes):
    return {"id": id_, "name": nome, "nodes": nos, "connections": conexoes, "active": False,
            "settings": {"executionOrder": "v1", "timezone": "America/Sao_Paulo"}, "pinData": {}}


def consulta_diaria():
    sep = "Separar alertas"
    nos = [
        agendamento("Todos os dias às 7h", [0, 200], "0 7 * * *"),
        manual([0, 400]),
        # Relê a planilha (LM_PLANILHA), consulta o DataJud e classifica. Pode levar minutos: timeout de 30 min.
        http("Consultar processos (API)", [240, 300], f"{API}/consultas",
             "={{ JSON.stringify({ reler_planilha: true }) }}", timeout=1800000),
        http("Buscar alertas pendentes", [480, 300], f"{API}/alertas/pendentes", metodo="GET"),
        no(sep, "n8n-nodes-base.splitOut", 1, [720, 300], {"fieldToSplitOut": "alertas", "options": {}}),
        tem_canal("Tem canal do Teams?", [960, 300], "={{ $json.webhook_url }}"),
        http("Enviar alerta ao Teams", [1200, 200], "={{ $json.webhook_url }}", "={{ JSON.stringify($json.payload) }}",
             onError="continueRegularOutput"),
        registrar("Registrar envio", [1440, 200], f"$('{sep}').item.json.tipo", "($json.error ? 'falha' : 'enviada')",
                  f"$('{sep}').item.json.movimentacao_id"),
        registrar("Registrar sem canal", [1200, 420], "$json.tipo", "'sem_canal'", "$json.movimentacao_id"),
    ]
    conexoes = {
        "Todos os dias às 7h": {"main": liga("Consultar processos (API)")},
        "Executar agora (teste)": {"main": liga("Consultar processos (API)")},
        "Consultar processos (API)": {"main": liga("Buscar alertas pendentes")},
        "Buscar alertas pendentes": {"main": liga(sep)},
        sep: {"main": liga("Tem canal do Teams?")},
        "Tem canal do Teams?": {"main": se("Enviar alerta ao Teams", "Registrar sem canal")},
        "Enviar alerta ao Teams": {"main": liga("Registrar envio")},
    }
    return fluxo("LitMonitorConsulta01", "LITIGATION MONITOR — Consulta diária e alertas", nos, conexoes)


def resumo_diario():
    nos = [
        agendamento("Dias úteis às 7h30", [0, 200], "30 7 * * 1-5"),
        manual([0, 400]),
        http("Montar resumo (API)", [240, 300], f"{API}/relatorios/resumo-diario", metodo="GET"),
        tem_canal("Tem canal do Teams?", [480, 300], "={{ $json.webhook_url }}"),
        http("Enviar resumo ao Teams", [720, 200], "={{ $json.webhook_url }}", "={{ JSON.stringify($json.payload) }}",
             onError="continueRegularOutput"),
        registrar("Registrar envio", [960, 200], "'resumo_diario'", "($json.error ? 'falha' : 'enviada')"),
        registrar("Registrar sem canal", [720, 420], "'resumo_diario'", "'sem_canal'"),
    ]
    conexoes = {
        "Dias úteis às 7h30": {"main": liga("Montar resumo (API)")},
        "Executar agora (teste)": {"main": liga("Montar resumo (API)")},
        "Montar resumo (API)": {"main": liga("Tem canal do Teams?")},
        "Tem canal do Teams?": {"main": se("Enviar resumo ao Teams", "Registrar sem canal")},
        "Enviar resumo ao Teams": {"main": liga("Registrar envio")},
    }
    return fluxo("LitMonitorResumo01", "LITIGATION MONITOR — Resumo diário no Teams", nos, conexoes)


def relatorio_semanal():
    nos = [
        agendamento("Segundas às 8h", [0, 200], "0 8 * * 1"),
        manual([0, 400]),
        http("Gerar relatório semanal (API)", [240, 300], f"{API}/relatorios/semanal", timeout=300000),
        tem_canal("Tem canal do Teams?", [480, 300], "={{ $json.webhook_url }}"),
        http("Enviar relatório ao Teams", [720, 200], "={{ $json.webhook_url }}",
             "={{ JSON.stringify($json.payload) }}", onError="continueRegularOutput"),
        registrar("Registrar envio", [960, 200], "'relatorio_semanal'", "($json.error ? 'falha' : 'enviada')"),
        registrar("Registrar sem canal", [720, 420], "'relatorio_semanal'", "'sem_canal'"),
    ]
    conexoes = {
        "Segundas às 8h": {"main": liga("Gerar relatório semanal (API)")},
        "Executar agora (teste)": {"main": liga("Gerar relatório semanal (API)")},
        "Gerar relatório semanal (API)": {"main": liga("Tem canal do Teams?")},
        "Tem canal do Teams?": {"main": se("Enviar relatório ao Teams", "Registrar sem canal")},
        "Enviar relatório ao Teams": {"main": liga("Registrar envio")},
    }
    return fluxo("LitMonitorSemanal01", "LITIGATION MONITOR — Relatório semanal", nos, conexoes)


if __name__ == "__main__":
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nome, f in (("01_consulta_diaria.json", consulta_diaria()), ("02_resumo_diario.json", resumo_diario()),
                    ("03_relatorio_semanal.json", relatorio_semanal())):
        (DESTINO / nome).write_text(json.dumps(f, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("gerado:", DESTINO / nome)
