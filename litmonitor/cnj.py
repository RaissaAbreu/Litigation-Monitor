"""Número único de processo (Resolução CNJ nº 65/2008): validação, formatação e tribunal.

Formato: NNNNNNN-DD.AAAA.J.TR.OOOO
    N sequencial · DD dígito verificador · A ano · J segmento da Justiça · TR tribunal · O origem
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SEGMENTOS = {
    "1": "Supremo Tribunal Federal", "2": "Conselho Nacional de Justiça", "3": "Superior Tribunal de Justiça",
    "4": "Justiça Federal", "5": "Justiça do Trabalho", "6": "Justiça Eleitoral",
    "7": "Justiça Militar da União", "8": "Justiça Estadual", "9": "Justiça Militar Estadual",
}

# Código TR da Justiça Estadual/Eleitoral → UF (ordem definida pela Resolução CNJ nº 65/2008)
UFS = ["ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt", "ms", "mg", "pa", "pb",
       "pr", "pe", "pi", "rj", "rn", "rs", "ro", "rr", "sc", "se", "sp", "to"]
TJM = {"13": "tjmmg", "21": "tjmrs", "26": "tjmsp"}


class NumeroInvalido(ValueError):
    pass


@dataclass(frozen=True)
class NumeroCNJ:
    limpo: str        # 20 dígitos
    formatado: str    # NNNNNNN-DD.AAAA.J.TR.OOOO
    segmento: str
    tribunal: str     # sigla em maiúsculas (ex.: TJSP)
    alias: str        # índice do DataJud (ex.: tjsp → api_publica_tjsp)


def somente_digitos(numero: str) -> str:
    return re.sub(r"\D", "", str(numero or ""))


def digito_verificador(limpo_sem_dv: str) -> str:
    """Calcula DD (módulo 97) a partir de NNNNNNN + AAAA + J + TR + OOOO (18 dígitos)."""
    n, a, j, tr, o = limpo_sem_dv[:7], limpo_sem_dv[7:11], limpo_sem_dv[11], limpo_sem_dv[12:14], limpo_sem_dv[14:18]
    resto = int(f"{n}{a}{j}{tr}{o}00") % 97
    return f"{98 - resto:02d}"


def formatar(limpo: str) -> str:
    return f"{limpo[:7]}-{limpo[7:9]}.{limpo[9:13]}.{limpo[13]}.{limpo[14:16]}.{limpo[16:20]}"


def alias_tribunal(segmento: str, tr: str) -> str | None:
    """Nome do índice do tribunal na API Pública do DataJud (sem o prefixo api_publica_)."""
    t = int(tr)
    if segmento == "8" and 1 <= t <= 27:
        return "tjdft" if UFS[t - 1] == "df" else f"tj{UFS[t - 1]}"
    if segmento == "4" and 1 <= t <= 6:
        return f"trf{t}"
    if segmento == "5":
        return "tst" if t == 0 else (f"trt{t}" if 1 <= t <= 24 else None)
    if segmento == "6":
        return "tse" if t == 0 else (f"tre-{UFS[t - 1]}" if 1 <= t <= 27 else None)
    if segmento == "3" and t == 0:
        return "stj"
    if segmento == "7":
        return "stm"
    if segmento == "9":
        return TJM.get(tr)
    return None


def interpretar(numero: str) -> NumeroCNJ:
    """Valida o número (20 dígitos e dígito verificador) e identifica o tribunal."""
    limpo = somente_digitos(numero)
    if len(limpo) != 20:
        raise NumeroInvalido(f"O número precisa ter 20 dígitos (tem {len(limpo)}).")
    dv_informado = limpo[7:9]
    sem_dv = limpo[:7] + limpo[9:]
    if digito_verificador(sem_dv) != dv_informado:
        raise NumeroInvalido("Dígito verificador inválido — confira o número.")
    segmento, tr = limpo[13], limpo[14:16]
    alias = alias_tribunal(segmento, tr)
    if alias is None:
        raise NumeroInvalido(f"Tribunal não disponível na API Pública do DataJud (J={segmento}, TR={tr}).")
    return NumeroCNJ(limpo, formatar(limpo), segmento, alias.upper(), alias)


def montar(sequencial: str, ano: str, segmento: str, tr: str, origem: str) -> str:
    """Monta um número válido (usado nos dados fictícios e nos testes)."""
    sem_dv = f"{int(sequencial):07d}{ano}{segmento}{int(tr):02d}{int(origem):04d}"
    dv = digito_verificador(sem_dv)
    return formatar(sem_dv[:7] + dv + sem_dv[7:])
