"""Classificação de movimentações processuais por regras (sem IA e sem envio de dados a terceiros).

1. Código do movimento na Tabela Processual Unificada (TPU) do CNJ, que o DataJud informa em cada movimento.
2. Se o código não estiver na tabela, palavras-chave no nome do movimento e nos complementos relevantes.
3. O grau define sentença x acórdão: julgamento em 1º grau/juizado é sentença; em 2º grau/turma, acórdão.
4. Intimações (disponibilização no DJe / publicação) logo após uma sentença, acórdão, liminar ou audiência
   são vinculadas a esse evento, e o prazo do evento passa a contar da publicação.

Os códigos abaixo foram conferidos em movimentos reais retornados pela API Pública do DataJud.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from hashlib import sha1
from typing import Any

from . import calendario

RELEVANCIAS = ["Alta", "Média", "Baixa"]
PESO_RELEVANCIA = {"Alta": 3, "Média": 2, "Baixa": 1}
GRAUS_RECURSAIS = {"G2", "TR", "SUP", "TRU", "TNU", "TRF", "TRT"}


@dataclass(frozen=True)
class Categoria:
    rotulo: str
    relevancia: str
    prazo_dias: int | None
    prazo_regra: str
    providencia: str


CATEGORIAS: dict[str, Categoria] = {
    "sentenca": Categoria(
        "Sentença", "Alta", 15, "Apelação — 15 dias úteis (CPC, art. 1.003, § 5º)",
        "Avaliar apelação ou embargos de declaração (5 dias úteis) e informar o cliente."),
    "acordao": Categoria(
        "Acórdão", "Alta", 15, "Recurso especial/extraordinário — 15 dias úteis (CPC, art. 1.003, § 5º)",
        "Avaliar embargos de declaração (5 dias úteis) ou recurso aos tribunais superiores."),
    "tutela": Categoria(
        "Liminar / tutela de urgência", "Alta", 15, "Agravo de instrumento — 15 dias úteis (CPC, art. 1.015, I)",
        "Verificar o cumprimento imediato da ordem e avaliar agravo de instrumento."),
    "transito": Categoria(
        "Trânsito em julgado", "Alta", None, "",
        "Verificar cumprimento de sentença, levantamento de valores ou encerramento do caso."),
    "audiencia": Categoria(
        "Audiência", "Alta", None, "Data da audiência — confirmar no processo",
        "Confirmar data, horário e formato da audiência; preparar cliente e testemunhas."),
    "citacao": Categoria(
        "Citação", "Alta", 15, "Contestação — 15 dias úteis (CPC, art. 335)",
        "Confirmar a data de juntada do mandado ou AR e preparar a defesa."),
    "intimacao": Categoria(
        "Intimação / publicação", "Média", 15, "Prazo geral estimado — 15 dias úteis",
        "Ler o teor da publicação no Diário da Justiça e confirmar o prazo aplicável."),
    "decisao": Categoria(
        "Decisão", "Média", None, "",
        "Analisar a decisão e avaliar a necessidade de recurso ou de providência."),
    "suspensao": Categoria(
        "Suspensão / sobrestamento", "Média", None, "",
        "Registrar o motivo da suspensão e a data prevista de retomada."),
    "arquivamento": Categoria(
        "Arquivamento / baixa", "Média", None, "",
        "Confirmar o encerramento e atualizar o controle do caso."),
    "expediente": Categoria(
        "Expediente", "Baixa", None, "", "Sem providência imediata — apenas acompanhar."),
}

# Ordem de exibição (da mais à menos relevante)
ORDEM_CATEGORIAS = list(CATEGORIAS)

JULGAMENTO = {193, 196, 218, 219, 220, 221, 385, 454, 457, 459, 460, 461, 466, 11876, 15162, 15164, 200}
ACORDAO = {235, 237, 238, 239, 230}
TUTELA = {332, 339, 785, 792, 889, 892}
TRANSITO = {848}
AUDIENCIA = {970, 12740, 12742, 12750, 12752}
INTIMACAO_DJE = {1061}
PUBLICACAO = {92}
COMUNICACAO = {12265, 12266}
DECISAO = {207, 941, 11378, 12164, 12185, 12307, 12387, 12444, 12455, 15086}
SUSPENSAO = {272, 898, 1015, 11025, 14975}
ARQUIVAMENTO = {22, 245, 246, 861, 12430}
EXPEDIENTE = {26, 36, 51, 85, 106, 118, 123, 132, 135, 137, 417, 493, 849, 893, 897, 978, 979, 980, 982, 985,
              1051, 10966, 11009, 11010, 12614, 12619, 12621, 14738, 14739, 15085}

CODIGOS: dict[int, str] = {}
for _codigos, _categoria in ((JULGAMENTO, "julgamento"), (ACORDAO, "acordao"), (TUTELA, "tutela"),
                             (TRANSITO, "transito"), (AUDIENCIA, "audiencia"), (INTIMACAO_DJE, "intimacao"),
                             (PUBLICACAO, "intimacao"), (COMUNICACAO, "intimacao"), (DECISAO, "decisao"),
                             (SUSPENSAO, "suspensao"), (ARQUIVAMENTO, "arquivamento"), (EXPEDIENTE, "expediente")):
    CODIGOS.update(dict.fromkeys(_codigos, _categoria))

# Palavras-chave (sem acento, minúsculas) usadas quando o código não está na tabela — em ordem de prioridade.
PALAVRAS: list[tuple[str, str]] = [
    (r"transito em julgado", "transito"),
    (r"acordao", "acordao"),
    (r"\b(sentenca|procedencia|improcedencia|extincao|homologacao|julgamento)\b", "julgamento"),
    (r"\b(liminar|tutela)\b", "tutela"),
    (r"\baudiencia\b", "audiencia"),
    (r"\bcitac", "citacao"),
    (r"\bintimac|diario da justica|\bpublicacao\b", "intimacao"),
    (r"\b(decisao|deferimento|indeferimento)\b", "decisao"),
    (r"\b(suspensao|sobrestamento)\b", "suspensao"),
    (r"\barquivamento\b|baixa definitiva", "arquivamento"),
]
# Complementos que descrevem o próprio ato (os demais, como tipo de petição, não indicam a natureza do movimento)
COMPLEMENTOS_DESCRITIVOS = {"tipo_de_documento", "tipo_de_audiencia", "situacao_da_audiencia"}

DIAS_VINCULO_INTIMACAO = 5
CATEGORIAS_VINCULAVEIS = {"sentenca", "acordao", "tutela", "audiencia"}


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def complemento(mov: dict[str, Any], descricao: str) -> str:
    for c in mov.get("complementos") or []:
        if c.get("descricao") == descricao:
            return str(c.get("nome") or "")
    return ""


def descrever(mov: dict[str, Any]) -> str:
    """Texto legível: nome do movimento e os complementos (ex.: 'Audiência — conciliação, designada')."""
    nomes = [str(c.get("nome")).strip() for c in mov.get("complementos") or [] if c.get("nome")]
    nome = str(mov.get("nome") or f"Movimento {mov.get('codigo')}").strip()
    return f"{nome} — {', '.join(nomes)}" if nomes else nome


def chave_movimento(mov: dict[str, Any]) -> str:
    """Identidade estável do movimento (para saber o que é novo entre uma consulta e outra)."""
    comps = sorted(f"{c.get('descricao')}={c.get('nome')}" for c in mov.get("complementos") or [])
    base = f"{mov.get('codigo')}|{mov.get('data_hora')}|{normalizar(mov.get('nome', ''))}|{'|'.join(comps)}|{mov.get('grau', '')}"
    return sha1(base.encode("utf-8")).hexdigest()[:20]


def _categoria_bruta(mov: dict[str, Any]) -> str:
    codigo = mov.get("codigo")
    try:
        codigo = int(codigo)
    except (TypeError, ValueError):
        codigo = None
    texto_complementos = " ".join(str(c.get("nome") or "") for c in mov.get("complementos") or []
                                  if c.get("descricao") in COMPLEMENTOS_DESCRITIVOS)

    # "Expedição de documento" e "Documento" dependem do tipo de documento informado no complemento
    if codigo in (60, 581, 12270):
        tipo = normalizar(texto_complementos)
        if "citac" in tipo:
            return "citacao"
        if "intimac" in tipo:
            return "intimacao"
        if "acordao" in tipo:
            return "acordao"
        if "sentenca" in tipo:
            return "julgamento"
        return "expediente"
    if codigo in CODIGOS:
        return CODIGOS[codigo]

    texto = normalizar(f"{mov.get('nome', '')} {texto_complementos}")
    for padrao, categoria in PALAVRAS:
        if re.search(padrao, texto):
            return categoria
    return "expediente"


@dataclass
class Classificacao:
    categoria: str
    rotulo: str
    relevancia: str
    providencia: str
    prazo: date | None = None
    prazo_situacao: str | None = None   # estimado | a_confirmar | None
    prazo_regra: str = ""
    vinculada_a: str = ""
    extras: dict[str, Any] = field(default_factory=dict)


def data_do_movimento(mov: dict[str, Any]) -> date:
    return datetime.fromisoformat(str(mov["data_hora"])[:19]).date()


def classificar(mov: dict[str, Any]) -> Classificacao:
    """Classifica um movimento isolado (sem considerar os vizinhos)."""
    categoria = _categoria_bruta(mov)
    grau = str(mov.get("grau") or "").upper()
    if categoria == "julgamento":
        categoria = "acordao" if grau in GRAUS_RECURSAIS else "sentenca"
    cat = CATEGORIAS[categoria]
    resultado = Classificacao(categoria, cat.rotulo, cat.relevancia, cat.providencia, prazo_regra=cat.prazo_regra)
    evento = data_do_movimento(mov)

    if categoria == "sentenca" and grau == "JE":
        resultado.prazo_regra = "Recurso inominado — 10 dias úteis (Lei nº 9.099/1995, art. 42)"
        resultado.providencia = "Avaliar recurso inominado ou embargos de declaração (5 dias úteis) e informar o cliente."
        resultado.extras["prazo_dias"] = 10

    if categoria == "audiencia":
        situacao = normalizar(complemento(mov, "situacao_da_audiencia"))
        if situacao in ("designada", "redesignada") or not situacao:
            resultado.prazo_situacao = "a_confirmar"
        else:
            resultado.relevancia = "Média"
            resultado.prazo_regra = ""
            resultado.providencia = {
                "realizada": "Registrar o resultado da audiência e os próximos passos.",
                "cancelada": "Confirmar se haverá nova data e avisar o cliente.",
                "nao-realizada": "Verificar o motivo e se haverá redesignação.",
                "adiada": "Acompanhar a nova data e avisar o cliente.",
            }.get(situacao, "Verificar a situação da audiência.")

    dias = resultado.extras.get("prazo_dias", cat.prazo_dias)
    if dias and resultado.prazo_situacao is None:
        dje = int(mov.get("codigo") or 0) in INTIMACAO_DJE
        resultado.prazo = calendario.prazo_final(evento, dias, disponibilizacao_dje=dje)
        resultado.prazo_situacao = "estimado"
        if categoria in ("sentenca", "acordao", "tutela"):
            resultado.prazo_regra += " · contado da data da decisão até a publicação ser identificada"
    return resultado


def classificar_lote(movimentos: list[dict[str, Any]]) -> list[tuple[dict[str, Any], Classificacao]]:
    """Classifica todos os movimentos de um processo, em ordem cronológica, aplicando o vínculo
    entre a intimação/publicação e a decisão ou audiência que ela comunica."""
    ordenados = sorted(movimentos, key=lambda m: str(m.get("data_hora")))
    resultado: list[tuple[dict[str, Any], Classificacao]] = []
    ultimo_evento: tuple[dict[str, Any], Classificacao] | None = None
    ultima_dje: date | None = None
    ultimo_encerramento: tuple[str, date] | None = None

    for mov in ordenados:
        cl = classificar(mov)
        evento = data_do_movimento(mov)
        codigo = int(mov.get("codigo") or 0)

        if cl.categoria == "intimacao" and codigo in PUBLICACAO and ultima_dje \
                and timedelta(0) <= evento - ultima_dje <= timedelta(days=DIAS_VINCULO_INTIMACAO):
            # "Publicação" que só confirma uma disponibilização no DJe já considerada
            cl = Classificacao("expediente", "Publicação", "Baixa",
                               "Publicação de conteúdo já disponibilizado no Diário da Justiça.",
                               vinculada_a="Disponibilização no DJe de " + ultima_dje.strftime("%d/%m/%Y"))
        elif cl.categoria == "intimacao" and ultimo_evento \
                and timedelta(0) <= evento - data_do_movimento(ultimo_evento[0]) <= timedelta(days=DIAS_VINCULO_INTIMACAO):
            mov_ev, cl_ev = ultimo_evento
            data_ev = data_do_movimento(mov_ev).strftime("%d/%m/%Y")
            if cl_ev.prazo_situacao == "estimado" and cl_ev.categoria in ("sentenca", "acordao", "tutela"):
                dias = cl_ev.extras.get("prazo_dias", CATEGORIAS[cl_ev.categoria].prazo_dias)
                cl_ev.prazo = calendario.prazo_final(evento, dias, disponibilizacao_dje=codigo in INTIMACAO_DJE)
                cl_ev.prazo_regra = cl_ev.prazo_regra.split(" · ")[0] + \
                    f" · contado da publicação de {evento.strftime('%d/%m/%Y')}"
            cl = Classificacao("expediente", f"Publicação · {cl_ev.rotulo.lower()}", "Baixa",
                               f"Intimação referente a {cl_ev.rotulo.lower()} de {data_ev}; o prazo está no próprio evento.",
                               vinculada_a=f"{cl_ev.rotulo} de {data_ev}")
            ultimo_evento = None
        elif cl.categoria == "arquivamento" and ultimo_encerramento \
                and timedelta(0) <= evento - ultimo_encerramento[1] <= timedelta(days=DIAS_VINCULO_INTIMACAO):
            # Baixa e arquivamento logo após o trânsito em julgado (ou outra baixa) são o mesmo encerramento
            cl = Classificacao("expediente", f"{cl.rotulo} · encerramento", "Baixa",
                               "Parte do mesmo encerramento; a providência está no evento principal.",
                               vinculada_a=f"{ultimo_encerramento[0]} de {ultimo_encerramento[1].strftime('%d/%m/%Y')}")

        if cl.categoria in ("transito", "arquivamento"):
            ultimo_encerramento = (cl.rotulo, evento)
        if codigo in INTIMACAO_DJE:
            ultima_dje = evento
        if cl.categoria in CATEGORIAS_VINCULAVEIS:
            ultimo_evento = (mov, cl)
        resultado.append((mov, cl))
    return resultado
