"""Dias úteis forenses para a estimativa de prazos.

Considera fins de semana, feriados nacionais, Carnaval, Sexta-feira Santa e Corpus Christi (sem expediente
forense na maior parte dos tribunais) e a suspensão de prazos de 20/12 a 20/01 (CPC, art. 220).
Feriados estaduais, municipais e suspensões pontuais de expediente NÃO são considerados — por isso o prazo
calculado é sempre uma estimativa a ser confirmada pelo analista.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

FIXOS = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25)]


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


@lru_cache(maxsize=32)
def feriados(ano: int) -> frozenset[date]:
    p = pascoa(ano)
    moveis = [p - timedelta(days=48), p - timedelta(days=47), p - timedelta(days=2), p + timedelta(days=60)]
    return frozenset([date(ano, m, d) for m, d in FIXOS] + moveis)


def em_recesso(d: date) -> bool:
    """Suspensão de prazos entre 20 de dezembro e 20 de janeiro, inclusive (CPC, art. 220)."""
    return (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 20)


def dia_util(d: date) -> bool:
    return d.weekday() < 5 and d not in feriados(d.year) and not em_recesso(d)


def proximo_dia_util(d: date) -> date:
    d += timedelta(days=1)
    while not dia_util(d):
        d += timedelta(days=1)
    return d


def somar_dias_uteis(evento: date, dias: int) -> date:
    """Último dia do prazo: exclui o dia do evento e conta só dias úteis (CPC, arts. 219 e 224)."""
    d = evento
    for _ in range(dias):
        d = proximo_dia_util(d)
    return d


def prazo_final(evento: date, dias: int, disponibilizacao_dje: bool = False) -> date:
    """Prazo contado da intimação.

    Pelo Diário da Justiça eletrônico, considera-se publicada no primeiro dia útil seguinte ao da
    disponibilização (Lei nº 11.419/2006, art. 4º, § 3º), e o prazo começa no dia útil seguinte à publicação.
    """
    inicio = proximo_dia_util(evento) if disponibilizacao_dje else evento
    return somar_dias_uteis(inicio, dias)


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Quantidade de dias úteis em (inicio, fim]. Negativo se fim < inicio."""
    if fim == inicio:
        return 0
    sinal, a, b = (1, inicio, fim) if fim > inicio else (-1, fim, inicio)
    total, d = 0, a
    while d < b:
        d += timedelta(days=1)
        total += dia_util(d)
    return sinal * total
