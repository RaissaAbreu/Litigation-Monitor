"""Configurações lidas de variáveis de ambiente (lidas a cada chamada, para facilitar testes)."""

from __future__ import annotations

import os
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

# Chave pública divulgada pelo CNJ na wiki da API Pública do DataJud
# (https://datajud-wiki.cnj.jus.br/api-publica/acesso). O CNJ pode trocá-la a qualquer momento:
# se as consultas começarem a falhar com 401/403, atualize DATAJUD_API_KEY no .env.
CHAVE_PUBLICA_DATAJUD = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="
URL_DATAJUD = "https://api-publica.datajud.cnj.jus.br"


def dir_dados() -> Path:
    caminho = Path(os.getenv("LM_DADOS", RAIZ_PROJETO / "dados"))
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def caminho_banco() -> Path:
    return Path(os.getenv("LM_BANCO", dir_dados() / "litigation_monitor.db"))


def dir_relatorios() -> Path:
    caminho = dir_dados() / "relatorios"
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def fonte_padrao() -> str:
    """'demo' ou 'datajud'. O painel pode trocar a fonte; a escolha fica salva no banco."""
    valor = os.getenv("LM_FONTE", "demo").strip().lower()
    return valor if valor in ("demo", "datajud") else "demo"


def datajud_url() -> str:
    return os.getenv("DATAJUD_URL", URL_DATAJUD).rstrip("/")


def datajud_chave() -> str:
    return os.getenv("DATAJUD_API_KEY", "").strip() or CHAVE_PUBLICA_DATAJUD


def datajud_timeout() -> float:
    return float(os.getenv("DATAJUD_TIMEOUT", "90"))


def datajud_tentativas() -> int:
    return int(os.getenv("DATAJUD_TENTATIVAS", "3"))


def caminho_planilha() -> str:
    """Planilha relida automaticamente antes de cada consulta agendada (opcional)."""
    return os.getenv("LM_PLANILHA", "").strip()


def email_remetente() -> str:
    """Conta Gmail que envia os alertas (a mesma da senha de app configurada no n8n)."""
    return os.getenv("GMAIL_USUARIO", "").strip()


def email_destino() -> str:
    """Destinatários dos alertas (separe vários com vírgula). Padrão: a própria conta remetente."""
    return os.getenv("EMAIL_ALERTAS", "").strip() or email_remetente()


def url_painel() -> str:
    return os.getenv("LM_URL_PAINEL", "http://localhost:8501").rstrip("/")


def url_api_publica() -> str:
    """Endereço da API acessível por quem recebe o e-mail (links de download dos relatórios)."""
    return os.getenv("LM_URL_API", "http://localhost:8000").rstrip("/")


def dias_alerta_prazo() -> int:
    return int(os.getenv("LM_DIAS_ALERTA", "3"))


def horas_repeticao_vencido() -> int:
    return int(os.getenv("LM_HORAS_REPETICAO_VENCIDO", "24"))


def dias_retroativos() -> int:
    """Na primeira consulta de um processo, movimentações relevantes desta janela contam como novas."""
    return int(os.getenv("LM_DIAS_RETROATIVOS", "15"))


def relevancia_minima_alerta() -> str:
    valor = os.getenv("LM_RELEVANCIA_ALERTA", "Média").strip().capitalize()
    return {"Media": "Média"}.get(valor, valor) if valor in ("Alta", "Média", "Media", "Baixa") else "Média"
