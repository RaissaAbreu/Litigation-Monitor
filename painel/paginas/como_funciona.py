"""Página: Como funciona (fluxo, fontes, classificação, prazos e alertas)."""

from __future__ import annotations

from html import escape

import streamlit as st

from litmonitor import config
from litmonitor.classificacao import CATEGORIAS
from painel import componentes as c
from painel import estilo

PASSOS = [
    ("Planilha", "A carteira vem de uma planilha Excel ou CSV com os números dos processos. O número é validado pelo "
                 "dígito verificador do CNJ e o tribunal é identificado pelo próprio número."),
    ("Consulta", "Todos os dias às 7h o n8n aciona a API, que consulta a API Pública do DataJud (CNJ) — fonte oficial "
                 "e autorizada — ou, no modo demonstração, dados fictícios."),
    ("Novas movimentações", "Cada movimento recebe uma identidade (código, data, grau e complementos). O que não estava "
                            "no banco é novo. Na primeira consulta, o histórico entra sem alertas."),
    ("Classificação", "Regras sobre o código TPU do movimento, palavras-chave e grau identificam sentença, acórdão, "
                      "liminar, audiência, intimação, citação, trânsito em julgado, decisões e arquivamento."),
    ("Prazos", "Para os eventos com prazo típico, o sistema estima o vencimento em dias úteis. O analista confirma ou "
               "corrige a data no painel."),
    ("Alertas", "O n8n envia por e-mail (Gmail) as movimentações relevantes e os prazos próximos, de hoje ou vencidos; "
                "tudo também aparece no painel."),
    ("Relatórios", "Resumo diário por e-mail às 7h30 e relatório semanal (PDF + Excel) às segundas, 8h. "
                   "O painel gera o mesmo relatório a qualquer momento."),
]


def renderizar() -> None:
    c.cabecalho("Como funciona", "O caminho de um processo, da planilha ao alerta e ao relatório.")

    estilo.secao("Fluxo / 10", "Etapas da automação")
    with st.container(border=True, key="cartao-passos"):
        estilo.html("".join(
            f'<div class="lm-passo"><div class="n">{i:02d}</div><div><div class="t">{escape(t)}</div>'
            f'<div class="d">{escape(d)}</div></div></div>' for i, (t, d) in enumerate(PASSOS, start=1)))

    st.write("")
    estilo.secao("Regras / 11", "Classificação das movimentações",
                 "Sentença ou acórdão é definido pelo grau: julgamento em 1º grau ou juizado é sentença; em 2º grau "
                 "ou turma recursal, acórdão.")
    with st.container(border=True, key="cartao-regras"):
        tom = {"Alta": "vermelho", "Média": "ambar", "Baixa": "neutro"}
        estilo.html('<ul class="lm-arquivos">' + "".join(
            f'<li><span class="n">{i}</span><div><div><b>{escape(cat.rotulo)}</b></div>'
            f'<div class="det">{escape(cat.providencia)}'
            f'{(" · Prazo: " + escape(cat.prazo_regra)) if cat.prazo_regra else ""}</div></div>'
            f'<span class="dir">{estilo.badge("Relevância " + cat.relevancia.lower(), tom[cat.relevancia])}</span></li>'
            for i, cat in enumerate(CATEGORIAS.values(), start=1)) + "</ul>")

    st.write("")
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        with st.container(border=True, key="cartao-prazos"):
            estilo.titulo_cartao(None, "Como o prazo é estimado")
            estilo.html("""<ul class="lm-lista">
              <li>Conta só dias úteis, a partir do dia útil seguinte ao evento (CPC, arts. 219 e 224).</li>
              <li>Disponibilização no DJe: a publicação é o dia útil seguinte e o prazo começa no próximo
                  (Lei nº 11.419/2006, art. 4º).</li>
              <li>Quando a publicação chega logo após a sentença, o acórdão ou a liminar, o prazo passa a contar dela.</li>
              <li>Exclui fins de semana, feriados nacionais, Carnaval, Sexta-feira Santa, Corpus Christi e o recesso de
                  20/12 a 20/01 (CPC, art. 220).</li>
              <li><b>Não</b> considera feriados locais nem suspensões de expediente: confirme sempre.</li>
              <li>Audiências: o DataJud não informa a data marcada — ela fica “a confirmar” até o analista registrar.</li>
            </ul>""")
    with col2:
        with st.container(border=True, key="cartao-alertas"):
            estilo.titulo_cartao(None, "Quando o e-mail é enviado")
            estilo.html(f"""<ul class="lm-lista">
              <li>{estilo.badge('Nova movimentação', 'azul')} uma vez, se a relevância for
                  {escape(config.relevancia_minima_alerta().lower())} ou maior.</li>
              <li>{estilo.badge('Prazo próximo', 'ambar')} uma vez, a {config.dias_alerta_prazo()} dia(s) ou menos do
                  vencimento (de novo se o prazo mudar).</li>
              <li>{estilo.badge('Vence hoje', 'vermelho')} uma vez, no dia.</li>
              <li>{estilo.badge('Prazo vencido', 'vermelho')} a cada {config.horas_repeticao_vencido()} h enquanto a
                  pendência estiver aberta.</li>
              <li>{estilo.badge('Resumo diário', 'neutro')} toda manhã, com os processos que exigem atenção.</li>
              <li>{estilo.badge('Relatório semanal', 'neutro')} às segundas, com links para o PDF e o Excel.</li>
            </ul>""")

    st.write("")
    estilo.secao("Fonte / 12", "Sobre a fonte de dados")
    with st.container(border=True, key="cartao-fonte"):
        estilo.html("""<ul class="lm-lista">
          <li><b>DataJud — API Pública do CNJ:</b> metadados e movimentos de processos públicos de todos os tribunais
              (exceto STF), com códigos da Tabela Processual Unificada. Acesso gratuito com a chave pública divulgada pelo CNJ.</li>
          <li>Não traz o teor das decisões, processos em segredo de justiça nem a data de audiências; a atualização
              pode ter alguns dias de atraso em relação ao sistema do tribunal.</li>
          <li><b>Modo demonstração:</b> movimentações fictícias que chegam a cada nova consulta, para conhecer o painel
              sem acesso à rede.</li>
        </ul>""")
