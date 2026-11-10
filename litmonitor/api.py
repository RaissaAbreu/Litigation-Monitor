"""API HTTP consumida pelo n8n (e útil para integrações).

    POST /consultas                 consulta todos os processos ativos na fonte (relê a planilha, se configurada)
    GET  /alertas/pendentes         alertas que o n8n deve enviar ao Teams agora
    POST /notificacoes              o n8n informa o resultado do envio (para não repetir alertas)
    GET  /relatorios/resumo-diario  cartão do resumo diário para o Teams
    POST /relatorios/semanal        gera o relatório semanal (PDF + Excel) e devolve o cartão para o Teams
    GET  /relatorios/{id}/pdf|xlsx  download dos arquivos
"""

from __future__ import annotations

import base64
import binascii
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import VERSAO, banco, config, monitor, planilha, relatorios


@asynccontextmanager
async def _ciclo_de_vida(_: FastAPI):
    banco.inicializar()
    yield


app = FastAPI(title="LITIGATION MONITOR API", version=VERSAO, lifespan=_ciclo_de_vida,
              description="Monitoramento automatizado de processos: consulta, classificação, alertas e relatórios.")


class ConsultaEntrada(BaseModel):
    reler_planilha: bool = Field(True, description="Relê a planilha de LM_PLANILHA (se configurada) antes de consultar")
    desativar_ausentes: bool = Field(False, description="Desativa processos que não constam mais na planilha")


class ImportacaoEntrada(BaseModel):
    nome_arquivo: str = Field(description="Nome com extensão .xlsx ou .csv")
    conteudo_base64: str
    desativar_ausentes: bool = False


class NotificacaoEntrada(BaseModel):
    tipo: Literal[tuple(monitor.TIPOS_NOTIFICACAO)]  # type: ignore[valid-type]
    situacao: Literal[monitor.SITUACOES_NOTIFICACAO]  # type: ignore[valid-type]
    movimentacao_id: int | None = None
    processo_id: int | None = None
    destino: str = "Microsoft Teams"


def _importacao_como_dict(r: monitor.ResultadoImportacao) -> dict[str, Any]:
    return r.__dict__.copy()


@app.get("/saude")
def saude() -> dict[str, Any]:
    return {"status": "ok", "versao": VERSAO, "fonte": monitor.fonte_ativa(),
            "processos": len(banco.listar_processos(apenas_ativos=True))}


@app.get("/processos")
def listar_processos() -> list[dict[str, Any]]:
    return [{k: v for k, v in p.items() if k != "pendencias"} | {"pendencias": p["qtd_pendencias"]}
            for p in monitor.painel_processos(incluir_inativos=True)]


@app.post("/processos/importar")
def importar_planilha(entrada: ImportacaoEntrada) -> dict[str, Any]:
    try:
        conteudo = base64.b64decode(entrada.conteudo_base64, validate=True)
    except (binascii.Error, ValueError) as erro:
        raise HTTPException(422, "conteudo_base64 inválido") from erro
    try:
        leitura = planilha.ler(conteudo, entrada.nome_arquivo)
    except planilha.PlanilhaInvalida as erro:
        raise HTTPException(422, str(erro)) from erro
    return _importacao_como_dict(monitor.importar(leitura, entrada.desativar_ausentes, autor="API"))


@app.post("/consultas")
def executar_consulta(entrada: ConsultaEntrada | None = None) -> dict[str, Any]:
    entrada = entrada or ConsultaEntrada()
    importacao = None
    if entrada.reler_planilha and config.caminho_planilha():
        caminho = Path(config.caminho_planilha())
        if not caminho.exists():
            raise HTTPException(422, f"Planilha não encontrada: {caminho}")
        try:
            leitura = planilha.ler_arquivo(caminho)
        except planilha.PlanilhaInvalida as erro:
            raise HTTPException(422, str(erro)) from erro
        importacao = _importacao_como_dict(monitor.importar(leitura, entrada.desativar_ausentes, autor="n8n"))
    resumo = monitor.sincronizar(origem="n8n")
    return {"consulta": resumo.como_dict(), "importacao": importacao}


@app.get("/alertas/pendentes")
def alertas_pendentes() -> dict[str, Any]:
    alertas = monitor.alertas_pendentes()
    return {"quantidade": len(alertas), "alertas": alertas}


@app.post("/notificacoes", status_code=201)
def registrar_notificacao(entrada: NotificacaoEntrada) -> dict[str, Any]:
    try:
        nid = monitor.registrar_notificacao(entrada.tipo, entrada.situacao, entrada.movimentacao_id,
                                            entrada.processo_id, entrada.destino)
    except ValueError as erro:
        raise HTTPException(404, str(erro)) from erro
    return {"id": nid}


@app.get("/relatorios/resumo-diario")
def resumo_diario() -> dict[str, Any]:
    return relatorios.resumo_diario()


@app.post("/relatorios/semanal", status_code=201)
def relatorio_semanal() -> dict[str, Any]:
    gerado = relatorios.gerar("semanal", origem="n8n")
    return {"relatorio": gerado["relatorio"], **relatorios.notificacao_relatorio(gerado["relatorio"], gerado["indicadores"])}


@app.get("/relatorios")
def listar_relatorios() -> list[dict[str, Any]]:
    return banco.listar_relatorios()


@app.get("/relatorios/{relatorio_id}/{formato}")
def baixar_relatorio(relatorio_id: int, formato: Literal["pdf", "xlsx"]) -> FileResponse:
    relatorio = banco.obter_relatorio(relatorio_id)
    if relatorio is None:
        raise HTTPException(404, "Relatório não encontrado")
    caminho = relatorios.caminho_arquivo(relatorio, formato)
    if not caminho.exists():
        raise HTTPException(404, "Arquivo do relatório não encontrado")
    tipo = "application/pdf" if formato == "pdf" else \
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(caminho, media_type=tipo, filename=caminho.name)
