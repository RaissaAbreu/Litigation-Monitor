"""Carrega a carteira fictícia e simula duas consultas (histórico + novidades) no modo demonstração.

    python -m litmonitor.seed
"""

from __future__ import annotations

from . import banco, config, monitor, planilha

PLANILHA_EXEMPLO = config.RAIZ_PROJETO / "exemplos" / "processos_exemplo.xlsx"


def carregar_demo(limpar: bool = True) -> monitor.ResumoConsulta:
    banco.inicializar()
    if limpar:
        banco.excluir_tudo()
    monitor.definir_fonte("demo")
    monitor.importar(planilha.ler_arquivo(PLANILHA_EXEMPLO), autor="Carteira demonstrativa")
    monitor.sincronizar(origem="demonstração")          # 1ª consulta: histórico de cada processo
    return monitor.sincronizar(origem="demonstração")   # 2ª consulta: novas movimentações


if __name__ == "__main__":
    resumo = carregar_demo()
    print(f"{resumo.processos} processo(s) consultado(s) · {resumo.novas} nova(s) movimentação(ões) · "
          f"{resumo.relevantes} relevante(s) · {resumo.nao_localizados} não localizado(s)")
