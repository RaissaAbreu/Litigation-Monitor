from datetime import date

import pytest

from litmonitor import calendario, cnj


def test_numero_real_valido_e_tribunal():
    n = cnj.interpretar("0704252-62.2026.8.07.0021")
    assert n.limpo == "07042526220268070021"
    assert n.alias == "tjdft" and n.tribunal == "TJDFT"


@pytest.mark.parametrize("numero,alias", [
    (cnj.montar("1", "2025", "8", "26", "100"), "tjsp"),
    (cnj.montar("1", "2025", "5", "2", "11"), "trt2"),
    (cnj.montar("1", "2025", "4", "3", "6100"), "trf3"),
    (cnj.montar("1", "2025", "5", "0", "0"), "tst"),
    (cnj.montar("1", "2025", "3", "0", "0"), "stj"),
    (cnj.montar("1", "2025", "6", "26", "1"), "tre-sp"),
    (cnj.montar("1", "2025", "9", "13", "1"), "tjmmg"),
])
def test_alias_por_segmento(numero, alias):
    assert cnj.interpretar(numero).alias == alias


def test_aceita_numero_sem_pontuacao():
    assert cnj.interpretar("07042526220268070021").formatado == "0704252-62.2026.8.07.0021"


@pytest.mark.parametrize("numero,trecho", [
    ("1234567-00.2025.8.26.0100", "Dígito verificador"),
    ("123", "20 dígitos"),
    (cnj.montar("1", "2025", "1", "0", "0"), "não disponível"),  # STF não está no DataJud
])
def test_numeros_invalidos(numero, trecho):
    with pytest.raises(cnj.NumeroInvalido, match=trecho):
        cnj.interpretar(numero)


def test_feriados_moveis_2026():
    f = calendario.feriados(2026)
    assert date(2026, 4, 3) in f        # Sexta-feira Santa
    assert date(2026, 2, 16) in f and date(2026, 2, 17) in f  # Carnaval
    assert date(2026, 6, 4) in f        # Corpus Christi
    assert date(2026, 11, 20) in f      # Consciência Negra


def test_prazo_dje_com_feriado():
    # Disponibilizado no sábado 29/08/2026 → publicado 31/08 → conta de 01/09; 07/09 é feriado.
    assert calendario.prazo_final(date(2026, 8, 29), 15, disponibilizacao_dje=True) == date(2026, 9, 22)


def test_recesso_suspende_prazo():
    # Evento em 18/12/2026 (sexta): 21/12 a 20/01 suspenso; 1º dia útil é 21/01/2027.
    assert calendario.somar_dias_uteis(date(2026, 12, 18), 1) == date(2027, 1, 21)


def test_dias_uteis_entre():
    assert calendario.dias_uteis_entre(date(2026, 11, 6), date(2026, 11, 9)) == 1   # sexta → segunda
    assert calendario.dias_uteis_entre(date(2026, 11, 9), date(2026, 11, 6)) == -1
