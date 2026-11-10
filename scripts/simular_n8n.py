"""Executa, sem o n8n, os mesmos passos dos três workflows — útil para testar a API e o Teams.

    python scripts/simular_n8n.py consulta    # "Consulta diária e alertas"
    python scripts/simular_n8n.py resumo      # "Resumo diário no Teams"
    python scripts/simular_n8n.py semanal     # "Relatório semanal"

Variável LM_API_URL (padrão http://localhost:8000).
"""

import json
import os
import sys
import urllib.error
import urllib.request

API = os.getenv("LM_API_URL", "http://localhost:8000").rstrip("/")


def requisitar(url, corpo=None, metodo=None, timeout=1800):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo or ("POST" if dados else "GET"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        texto = resp.read().decode() or "{}"
        return json.loads(texto) if texto.strip().startswith(("{", "[")) else {}


def enviar(tipo, webhook_url, payload, movimentacao_id=None):
    """Envia ao Teams (se houver canal) e registra o resultado — como os nós do n8n."""
    if webhook_url:
        try:
            requisitar(webhook_url, payload, timeout=30)
            situacao = "enviada"
        except (urllib.error.URLError, TimeoutError):
            situacao = "falha"
    else:
        situacao = "sem_canal"
    requisitar(f"{API}/notificacoes", {"tipo": tipo, "situacao": situacao, "movimentacao_id": movimentacao_id,
                                       "destino": "Microsoft Teams"})
    return situacao


def consulta():
    r = requisitar(f"{API}/consultas", {"reler_planilha": True})
    c = r["consulta"]
    print(f"Consulta: {c['processos']} processo(s) · {c['novas']} nova(s) · {c['relevantes']} relevante(s) · "
          f"{c['nao_localizados']} não localizado(s) · {c['erros']} falha(s)")
    alertas = requisitar(f"{API}/alertas/pendentes")["alertas"]
    for a in alertas:
        print(f"  {a['numero']} · {a['tipo_descricao']} · {enviar(a['tipo'], a['webhook_url'], a['payload'], a['movimentacao_id'])}")
    print(f"{len(alertas)} alerta(s) processado(s).")


def resumo():
    r = requisitar(f"{API}/relatorios/resumo-diario")
    print(f"Resumo diário: {r['quantidade']} processo(s) exigem atenção · {enviar('resumo_diario', r['webhook_url'], r['payload'])}")


def semanal():
    r = requisitar(f"{API}/relatorios/semanal", {}, metodo="POST")
    rel = r["relatorio"]
    print(f"Relatório #{rel['id']} gerado ({rel['arquivo_pdf']}) · {enviar('relatorio_semanal', r['webhook_url'], r['payload'])}")


if __name__ == "__main__":
    acoes = {"consulta": consulta, "resumo": resumo, "semanal": semanal}
    if len(sys.argv) != 2 or sys.argv[1] not in acoes:
        print(__doc__)
        sys.exit(1)
    acoes[sys.argv[1]]()
