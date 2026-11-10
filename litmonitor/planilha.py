"""Leitura da planilha de processos (.xlsx ou .csv) com pandas.

Coluna obrigatória: número do processo. Opcionais: cliente, parte contrária, responsável, observações.
Os cabeçalhos são reconhecidos sem diferenciar maiúsculas, acentos ou espaços (ex.: "Número do processo",
"numero_cnj", "Processo").
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from . import cnj
from .classificacao import normalizar

SINONIMOS = {
    "numero": ["numero do processo", "numero processo", "numero_processo", "numero cnj", "numero_cnj", "processo",
               "n do processo", "no do processo", "numero", "n processo", "autos"],
    "cliente": ["cliente", "empresa", "parte representada", "parte_representada"],
    "parte_contraria": ["parte contraria", "parte_contraria", "adverso", "parte adversa", "contraparte"],
    "responsavel": ["responsavel", "advogado", "advogado responsavel", "analista"],
    "observacoes": ["observacoes", "observacao", "obs", "notas"],
}
COLUNAS = list(SINONIMOS)
ROTULOS = {"numero": "Número do processo", "cliente": "Cliente", "parte_contraria": "Parte contrária",
           "responsavel": "Responsável", "observacoes": "Observações"}


class PlanilhaInvalida(ValueError):
    pass


@dataclass
class LinhaPlanilha:
    linha: int
    numero_informado: str
    dados: dict[str, Any] | None = None   # preenchido quando o número é válido
    erro: str = ""


@dataclass
class LeituraPlanilha:
    validas: list[LinhaPlanilha] = field(default_factory=list)
    invalidas: list[LinhaPlanilha] = field(default_factory=list)
    duplicadas: int = 0
    colunas_reconhecidas: dict[str, str] = field(default_factory=dict)


def _chave(cabecalho: Any) -> str:
    return re.sub(r"[^a-z0-9 _]", "", normalizar(str(cabecalho)).replace("º", "").replace(".", " ")).strip()


def _mapear_colunas(df: pd.DataFrame) -> dict[str, str]:
    mapa: dict[str, str] = {}
    for coluna in df.columns:
        chave = _chave(coluna)
        for campo, sinonimos in SINONIMOS.items():
            if campo not in mapa and chave in sinonimos:
                mapa[campo] = coluna
                break
    return mapa


def carregar_dataframe(conteudo: bytes, nome_arquivo: str) -> pd.DataFrame:
    extensao = Path(nome_arquivo).suffix.lower()
    if extensao in (".xlsx", ".xlsm"):
        return pd.read_excel(io.BytesIO(conteudo), dtype=str)
    if extensao == ".csv":
        texto = None
        for codificacao in ("utf-8-sig", "latin-1"):
            try:
                texto = conteudo.decode(codificacao)
                break
            except UnicodeDecodeError:
                continue
        return pd.read_csv(io.StringIO(texto or ""), dtype=str, sep=None, engine="python")
    raise PlanilhaInvalida("Formato não suportado — envie .xlsx ou .csv.")


def ler(conteudo: bytes, nome_arquivo: str) -> LeituraPlanilha:
    try:
        df = carregar_dataframe(conteudo, nome_arquivo)
    except PlanilhaInvalida:
        raise
    except Exception as erro:  # pandas/openpyxl levantam vários tipos
        raise PlanilhaInvalida(f"Não foi possível ler a planilha: {erro}") from erro

    df = df.dropna(how="all")
    mapa = _mapear_colunas(df)
    if "numero" not in mapa:
        raise PlanilhaInvalida("Coluna com o número do processo não encontrada. Use, por exemplo, "
                               "o cabeçalho “Número do processo”.")
    leitura = LeituraPlanilha(colunas_reconhecidas={ROTULOS[k]: str(v) for k, v in mapa.items()})
    vistos: set[str] = set()
    for posicao, (_, registro) in enumerate(df.iterrows(), start=2):  # linha 1 = cabeçalho
        valores = {campo: ("" if pd.isna(registro[col]) else str(registro[col]).strip()) for campo, col in mapa.items()}
        informado = valores.get("numero", "")
        if not informado:
            continue
        try:
            numero = cnj.interpretar(informado)
        except cnj.NumeroInvalido as erro:
            leitura.invalidas.append(LinhaPlanilha(posicao, informado, erro=str(erro)))
            continue
        if numero.limpo in vistos:
            leitura.duplicadas += 1
            continue
        vistos.add(numero.limpo)
        dados = {campo: valores.get(campo, "") for campo in COLUNAS if campo != "numero"}
        dados.update(numero=numero.formatado, numero_limpo=numero.limpo, tribunal=numero.tribunal)
        leitura.validas.append(LinhaPlanilha(posicao, informado, dados=dados))
    return leitura


def ler_arquivo(caminho: str | Path) -> LeituraPlanilha:
    caminho = Path(caminho)
    return ler(caminho.read_bytes(), caminho.name)


def modelo_csv() -> bytes:
    """Planilha modelo vazia, com os cabeçalhos esperados."""
    return ("Número do processo;Cliente;Parte contrária;Responsável;Observações\n").encode("utf-8-sig")
