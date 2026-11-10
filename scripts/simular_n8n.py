"""Executa, sem o n8n, os mesmos passos dos três workflows — útil para testar a API e o envio pelo Gmail.

    python scripts/simular_n8n.py consulta    # "Consulta diária e alertas"
    python scripts/simular_n8n.py resumo      # "Resumo diário por e-mail"
    python scripts/simular_n8n.py semanal     # "Relatório semanal"

Lê GMAIL_USUARIO, GMAIL_SENHA_APP e LM_API_URL (padrão http://localhost:8000) do ambiente ou do arquivo .env.
"""

import json
import os
import smtplib
import ssl
import sys
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path


def carregar_env() -> None:
    arquivo = Path(__file__).resolve().parent.parent / ".env"
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.lstrip().startswith("#"):
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.split(" #")[0].strip())


carregar_env()
API = os.getenv("LM_API_URL", "http://localhost:8000").rstrip("/")


def requisitar(url, corpo=None, metodo=None, timeout=1800):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo or ("POST" if dados else "GET"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        texto = resp.read().decode() or "{}"
        return json.loads(texto) if texto.strip().startswith(("{", "[")) else {}


def enviar(tipo, email, movimentacao_id=None):
    """Envia pelo Gmail (se configurado) e registra o resultado — como os nós do n8n."""
    usuario = os.getenv("GMAIL_USUARIO", "").strip()
    senha = os.getenv("GMAIL_SENHA_APP", "").replace(" ", "")
    if email.get("para") and usuario and senha:
        msg = MIMEText(email["html"], "html", "utf-8")
        msg["Subject"], msg["From"], msg["To"] = email["assunto"], email["de"] or usuario, email["para"]
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as smtp:
                smtp.login(usuario, senha)
                smtp.sendmail(usuario, [e.strip() for e in email["para"].split(",")], msg.as_string())
            situacao = "enviada"
        except (smtplib.SMTPException, OSError) as erro:
            print("    falha no envio:", erro)
            situacao = "falha"
    else:
        situacao = "sem_canal"
    requisitar(f"{API}/notificacoes", {"tipo": tipo, "situacao": situacao, "movimentacao_id": movimentacao_id,
                                       "destino": "Gmail"})
    return situacao


def consulta():
    r = requisitar(f"{API}/consultas", {"reler_planilha": True})
    c = r["consulta"]
    print(f"Consulta: {c['processos']} processo(s) · {c['novas']} nova(s) · {c['relevantes']} relevante(s) · "
          f"{c['nao_localizados']} não localizado(s) · {c['erros']} falha(s)")
    alertas = requisitar(f"{API}/alertas/pendentes")["alertas"]
    for a in alertas:
        print(f"  {a['numero']} · {a['tipo_descricao']} · {enviar(a['tipo'], a['email'], a['movimentacao_id'])}")
    print(f"{len(alertas)} alerta(s) processado(s).")


def resumo():
    r = requisitar(f"{API}/relatorios/resumo-diario")
    print(f"Resumo diário: {r['quantidade']} processo(s) exigem atenção · {enviar('resumo_diario', r['email'])}")


def semanal():
    r = requisitar(f"{API}/relatorios/semanal", {}, metodo="POST")
    rel = r["relatorio"]
    print(f"Relatório #{rel['id']} gerado ({rel['arquivo_pdf']}) · {enviar('relatorio_semanal', r['email'])}")


if __name__ == "__main__":
    acoes = {"consulta": consulta, "resumo": resumo, "semanal": semanal}
    if len(sys.argv) != 2 or sys.argv[1] not in acoes:
        print(__doc__)
        sys.exit(1)
    acoes[sys.argv[1]]()
