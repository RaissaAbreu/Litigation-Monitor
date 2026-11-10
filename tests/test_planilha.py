import io

import pandas as pd
import pytest

from litmonitor import planilha, seed

VALIDO = "0704252-62.2026.8.07.0021"


def test_planilha_exemplo_xlsx():
    leitura = planilha.ler_arquivo(seed.PLANILHA_EXEMPLO)
    assert len(leitura.validas) == 8
    assert len(leitura.invalidas) == 1 and "Dígito verificador" in leitura.invalidas[0].erro
    assert leitura.invalidas[0].linha == 10


def test_csv_com_cabecalhos_variados_e_duplicados():
    csv = f"Nº do Processo;Empresa;Advogado\n{VALIDO};ACME;Ana\n07042526220268070021;ACME;Ana\n;;\n".encode("utf-8")
    leitura = planilha.ler(csv, "carteira.csv")
    assert len(leitura.validas) == 1 and leitura.duplicadas == 1
    dados = leitura.validas[0].dados
    assert dados["cliente"] == "ACME" and dados["responsavel"] == "Ana" and dados["tribunal"] == "TJDFT"


def test_csv_latin1_e_virgula():
    csv = f"Processo,Cliente\n{VALIDO},Associação São João\n".encode("latin-1")
    assert planilha.ler(csv, "x.csv").validas[0].dados["cliente"] == "Associação São João"


def test_excel_numero_sem_mascara():
    buf = io.BytesIO()
    pd.DataFrame({"numero_cnj": ["07042526220268070021"]}).to_excel(buf, index=False)
    assert planilha.ler(buf.getvalue(), "a.xlsx").validas[0].dados["numero"] == VALIDO


def test_sem_coluna_de_numero():
    with pytest.raises(planilha.PlanilhaInvalida, match="Número do processo"):
        planilha.ler(b"Cliente;Responsavel\nA;B\n", "a.csv")


def test_formato_nao_suportado():
    with pytest.raises(planilha.PlanilhaInvalida, match="Formato"):
        planilha.ler(b"x", "a.pdf")
