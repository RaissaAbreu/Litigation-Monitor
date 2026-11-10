"""Fontes de dados processuais.

- FonteDataJud: API Pública do DataJud (CNJ) — fonte oficial, gratuita e autorizada, com dados de capa e
  movimentos (códigos da TPU). Não traz o teor das decisões nem a data marcada para audiências.
- FonteDemo: movimentações fictícias, sem rede, que vão "chegando" a cada nova consulta.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from hashlib import sha1
from typing import Any, Protocol

import httpx

from . import calendario, cnj, config

FONTES = {
    "demo": "Modo demonstração (sem API)",
    "datajud": "DataJud · API Pública CNJ",
}


class ErroFonte(Exception):
    """Falha temporária ou de configuração ao consultar a fonte."""


class ProcessoNaoEncontrado(ErroFonte):
    """A fonte respondeu, mas não tem o processo (sigilo, número errado ou ainda não indexado)."""


@dataclass
class ResultadoConsulta:
    capa: dict[str, Any]
    movimentos: list[dict[str, Any]] = field(default_factory=list)


class Fonte(Protocol):
    nome: str

    def consultar(self, processo: dict[str, Any]) -> ResultadoConsulta: ...


# --------------------------------------------------------------------------- DataJud


def _data_iso(valor: Any) -> str | None:
    """O DataJud usa '2026-07-27T09:21:10.000Z' nos movimentos e '20260727092110' no ajuizamento."""
    if not valor:
        return None
    texto = str(valor).strip()
    try:
        if texto.isdigit() and len(texto) >= 8:
            return datetime.strptime(texto[:14].ljust(14, "0"), "%Y%m%d%H%M%S").isoformat()
        return datetime.fromisoformat(texto.replace("Z", "")[:19]).isoformat()
    except ValueError:
        return None


def interpretar_resposta_datajud(dados: dict[str, Any]) -> ResultadoConsulta:
    """Junta os registros do processo (um por grau: G1, G2, JE...) em uma capa e uma lista de movimentos."""
    hits = [h.get("_source", {}) for h in dados.get("hits", {}).get("hits", [])]
    if not hits:
        raise ProcessoNaoEncontrado("Processo não localizado no DataJud.")
    hits.sort(key=lambda s: str(s.get("dataHoraUltimaAtualizacao") or ""), reverse=True)
    recente = hits[0]
    movimentos, vistos = [], set()
    for registro in hits:
        grau = registro.get("grau") or ""
        for m in registro.get("movimentos") or []:
            data_hora = _data_iso(m.get("dataHora"))
            if not data_hora:
                continue
            mov = {
                "codigo": m.get("codigo"),
                "nome": (m.get("nome") or "").strip(),
                "data_hora": data_hora,
                "complementos": [{"descricao": c.get("descricao"), "nome": c.get("nome")}
                                 for c in m.get("complementosTabelados") or []],
                "grau": grau,
                "orgao": (m.get("orgaoJulgador") or {}).get("nome") or (registro.get("orgaoJulgador") or {}).get("nome", ""),
            }
            identidade = (mov["codigo"], mov["data_hora"], mov["grau"], str(mov["complementos"]))
            if identidade not in vistos:
                vistos.add(identidade)
                movimentos.append(mov)
    capa = {
        "classe": (recente.get("classe") or {}).get("nome", ""),
        "assuntos": ", ".join(a.get("nome", "") for a in recente.get("assuntos") or [] if isinstance(a, dict)),
        "orgao_julgador": (recente.get("orgaoJulgador") or {}).get("nome", ""),
        "graus": ", ".join(sorted({str(h.get("grau")) for h in hits if h.get("grau")})),
        "data_ajuizamento": (_data_iso(recente.get("dataAjuizamento")) or "")[:10] or None,
        "sistema": (recente.get("sistema") or {}).get("nome", ""),
        "ultima_atualizacao_fonte": _data_iso(recente.get("dataHoraUltimaAtualizacao")),
    }
    return ResultadoConsulta(capa, movimentos)


class FonteDataJud:
    nome = "datajud"

    def __init__(self, cliente: httpx.Client | None = None, pausa: float = 2.0):
        self._cliente = cliente
        self._pausa = pausa

    def _cliente_http(self) -> httpx.Client:
        if self._cliente is None:
            self._cliente = httpx.Client(timeout=config.datajud_timeout())
        return self._cliente

    def consultar(self, processo: dict[str, Any]) -> ResultadoConsulta:
        numero = cnj.interpretar(processo["numero"])
        url = f"{config.datajud_url()}/api_publica_{numero.alias}/_search"
        corpo = {"size": 10, "query": {"match": {"numeroProcesso": numero.limpo}}}
        cabecalhos = {"Authorization": f"APIKey {config.datajud_chave()}", "Content-Type": "application/json"}
        ultimo_erro = "sem resposta"
        for tentativa in range(1, config.datajud_tentativas() + 1):
            try:
                resposta = self._cliente_http().post(url, json=corpo, headers=cabecalhos)
            except httpx.HTTPError as erro:
                ultimo_erro = f"falha de conexão ({erro.__class__.__name__})"
            else:
                if resposta.status_code in (401, 403):
                    raise ErroFonte("Acesso negado pelo DataJud — verifique a DATAJUD_API_KEY.")
                if resposta.status_code == 404:
                    raise ErroFonte(f"Índice do tribunal {numero.tribunal} não encontrado no DataJud.")
                if resposta.status_code < 400:
                    try:
                        dados = resposta.json()
                    except ValueError:
                        dados = None
                    # O Elasticsearch do DataJud às vezes responde 200 com shards rejeitados e nenhum resultado.
                    shards = (dados or {}).get("_shards", {})
                    if dados is not None and not (shards.get("failed") and not dados.get("hits", {}).get("hits")):
                        return interpretar_resposta_datajud(dados)
                    ultimo_erro = "resposta incompleta do DataJud (sobrecarga)"
                elif resposta.status_code == 429:
                    ultimo_erro = "limite de requisições atingido (HTTP 429) — tente mais tarde"
                    if tentativa < config.datajud_tentativas():
                        espera = resposta.headers.get("Retry-After", "")
                        time.sleep(float(espera) if espera.isdigit() else self._pausa * 5 * tentativa)
                        continue
                else:
                    ultimo_erro = f"HTTP {resposta.status_code}"
            if tentativa < config.datajud_tentativas():
                time.sleep(self._pausa * tentativa)
        raise ErroFonte(f"DataJud indisponível: {ultimo_erro}.")


# --------------------------------------------------------------------------- Demonstração

# Cada movimento: (rodada, dias em relação à data de cadastro, hora, código, nome, complementos, grau)
# Rodada 0 aparece na 1ª consulta (histórico); rodada 1 na 2ª; rodada 2 na 3ª.
AUTO = "auto"  # dias calculados para que o prazo estimado vença no próximo dia útil

CENARIOS: dict[str, list[tuple]] = {
    "sentenca": [
        (0, -150, "10:12", 26, "Distribuição", [("tipo_de_distribuicao_redistribuicao", "sorteio")], "G1"),
        (0, -149, "15:40", 51, "Conclusão", [("tipo_de_conclusao", "para despacho")], "G1"),
        (0, -147, "11:03", 11010, "Mero expediente", [], "G1"),
        (0, -120, "09:30", 60, "Expedição de documento", [("tipo_de_documento", "Carta")], "G1"),
        (0, -88, "17:22", 85, "Petição", [("tipo_de_peticao", "Contestação")], "G1"),
        (0, -61, "14:05", 85, "Petição", [("tipo_de_peticao", "Replica")], "G1"),
        (0, -40, "16:31", 51, "Conclusão", [("tipo_de_conclusao", "para julgamento")], "G1"),
        (1, -3, "18:14", 221, "Procedência em Parte", [], "G1"),
        (1, -2, "02:20", 1061, "Disponibilização no Diário da Justiça Eletrônico", [], "G1"),
        (1, -1, "02:19", 92, "Publicação", [], "G1"),
        (2, 0, "13:47", 85, "Petição", [("tipo_de_peticao", "Embargos de declaração")], "G1"),
    ],
    "audiencia": [
        (0, -110, "08:55", 26, "Distribuição", [("tipo_de_distribuicao_redistribuicao", "sorteio")], "G1"),
        (0, -109, "09:10", 970, "Audiência", [("tipo_de_audiencia", "conciliação"), ("situacao_da_audiencia", "designada")], "G1"),
        (0, -62, "10:30", 970, "Audiência", [("tipo_de_audiencia", "conciliação"), ("situacao_da_audiencia", "realizada")], "G1"),
        (0, -62, "11:02", 85, "Petição", [("tipo_de_peticao", "Contestação")], "G1"),
        (0, -30, "15:20", 85, "Petição", [("tipo_de_peticao", "Replica")], "G1"),
        (1, -2, "16:45", 970, "Audiência", [("tipo_de_audiencia", "instrução e julgamento"), ("situacao_da_audiencia", "designada")], "G1"),
        (1, -1, "02:20", 1061, "Disponibilização no Diário da Justiça Eletrônico", [], "G1"),
    ],
    "acordao": [
        (0, -210, "12:00", 123, "Remessa", [("motivo_da_remessa", "em grau de recurso")], "G1"),
        (0, -205, "10:15", 26, "Distribuição", [("tipo_de_distribuicao_redistribuicao", "sorteio")], "G2"),
        (0, -204, "16:02", 51, "Conclusão", [("tipo_de_conclusao", "para julgamento")], "G2"),
        (0, -150, "09:41", 85, "Petição", [("tipo_de_peticao", "Contra-razões")], "G2"),
        (0, -35, "14:00", 417, "Inclusão em pauta", [], "G2"),
        (1, -4, "17:30", 239, "Não-Provimento", [], "G2"),
        (1, -3, "02:20", 1061, "Disponibilização no Diário da Justiça Eletrônico", [], "G2"),
        (2, 0, "09:12", 581, "Documento", [("tipo_de_documento", "Certidão")], "G2"),
    ],
    "tutela": [
        (0, -25, "11:11", 26, "Distribuição", [("tipo_de_distribuicao_redistribuicao", "sorteio")], "G1"),
        (0, -24, "11:40", 51, "Conclusão", [("tipo_de_conclusao", "para decisão")], "G1"),
        (1, -2, "19:05", 785, "Antecipação de tutela", [], "G1"),
        (1, -1, "10:22", 60, "Expedição de documento", [("tipo_de_documento", "Ofício")], "G1"),
    ],
    "rotina": [
        (0, -300, "10:00", 26, "Distribuição", [("tipo_de_distribuicao_redistribuicao", "sorteio")], "G1"),
        (0, -200, "14:10", 85, "Petição", [("tipo_de_peticao", "Petição (outras)")], "G1"),
        (0, -90, "09:00", 11010, "Mero expediente", [], "G1"),
        (1, -2, "16:20", 85, "Petição", [("tipo_de_peticao", "Petição (outras)")], "G1"),
        (1, -1, "08:47", 51, "Conclusão", [("tipo_de_conclusao", "para despacho")], "G1"),
        (2, 0, "15:33", 11010, "Mero expediente", [], "G1"),
    ],
    "transito": [
        (0, -400, "10:00", 26, "Distribuição", [("tipo_de_distribuicao_redistribuicao", "sorteio")], "G1"),
        (0, -95, "18:00", 219, "Procedência", [], "G1"),
        (0, -93, "02:20", 1061, "Disponibilização no Diário da Justiça Eletrônico", [], "G1"),
        (0, -50, "00:00", 1051, "Decurso de Prazo", [], "G1"),
        (1, -3, "13:20", 848, "Trânsito em julgado", [], "G1"),
        (1, -2, "13:25", 22, "Baixa Definitiva", [], "G1"),
        (1, -2, "13:26", 246, "Definitivo", [], "G1"),
    ],
    "intimacao": [
        (0, -70, "10:30", 26, "Distribuição", [("tipo_de_distribuicao_redistribuicao", "dependência")], "G1"),
        (0, -45, "17:12", 12164, "Outras Decisões", [], "G1"),
        (0, -44, "02:20", 1061, "Disponibilização no Diário da Justiça Eletrônico", [], "G1"),
        (0, -40, "16:00", 85, "Petição", [("tipo_de_peticao", "Petição (outras)")], "G1"),
        (1, AUTO, "02:20", 1061, "Disponibilização no Diário da Justiça Eletrônico", [], "G1"),
        (2, 0, "14:41", 51, "Conclusão", [("tipo_de_conclusao", "para decisão")], "G1"),
    ],
}

CAPAS = {
    "sentenca": ("Procedimento Comum Cível", "Cobrança de Aluguéis - Sem despejo", "G1"),
    "audiencia": ("Ação Trabalhista - Rito Ordinário", "Horas Extras, Adicional Noturno", "G1"),
    "acordao": ("Apelação Cível", "Indenização por Dano Moral", "G2"),
    "tutela": ("Mandado de Segurança Cível", "Tributário - Compensação", "G1"),
    "rotina": ("Procedimento Comum Cível", "Rescisão do contrato e devolução do dinheiro", "G1"),
    "transito": ("Cumprimento de Sentença", "Contratos Bancários", "G1"),
    "intimacao": ("Procedimento Comum Cível", "Obrigação de Fazer / Não Fazer", "G1"),
}

# Números da planilha de exemplo com cenário fixo (os demais recebem um cenário pelo próprio número).
CENARIO_POR_NUMERO = {
    "10123459820258260100": "sentenca",
    "10008761520265020011": "audiencia",
    "08012343920248190001": "acordao",
    "50043219320264036100": "tutela",
    "50123452720258130024": "rotina",
    "07123457920238070001": "transito",
    "10234564520268260100": "intimacao",
}
NAO_LOCALIZADOS = {"00056785520255010005"}


def _dias_auto(ancora: date) -> int:
    """Dias antes da âncora para que uma intimação no DJe vença no próximo dia útil após a âncora."""
    alvo = calendario.proximo_dia_util(ancora)
    for dias in range(1, 60):
        d = ancora - timedelta(days=dias)
        if calendario.dia_util(d) and calendario.prazo_final(d, 15, disponibilizacao_dje=True) == alvo:
            return -dias
    return -18


class FonteDemo:
    nome = "demo"

    def cenario(self, numero_limpo: str) -> str:
        if numero_limpo in CENARIO_POR_NUMERO:
            return CENARIO_POR_NUMERO[numero_limpo]
        nomes = list(CENARIOS)
        return nomes[int(sha1(numero_limpo.encode()).hexdigest(), 16) % len(nomes)]

    def consultar(self, processo: dict[str, Any]) -> ResultadoConsulta:
        numero = cnj.interpretar(processo["numero"])
        if numero.limpo in NAO_LOCALIZADOS:
            raise ProcessoNaoEncontrado("Processo não localizado na fonte (demonstração).")
        nome = self.cenario(numero.limpo)
        ancora = datetime.fromisoformat(processo["criado_em"]).date()
        rodada_atual = int(processo.get("consultas_realizadas") or 0)
        orgao = f"{int(numero.limpo[16:20]):d}ª Vara · {numero.tribunal}"
        movimentos = []
        for rodada, dias, hora, codigo, nome_mov, comps, grau in CENARIOS[nome]:
            if rodada > rodada_atual:
                continue
            dias = _dias_auto(ancora) if dias == AUTO else dias
            quando = datetime.combine(ancora + timedelta(days=dias), datetime.strptime(hora, "%H:%M").time())
            movimentos.append({
                "codigo": codigo, "nome": nome_mov, "data_hora": quando.isoformat(), "grau": grau,
                "complementos": [{"descricao": d, "nome": n} for d, n in comps],
                "orgao": orgao if grau == "G1" else f"{numero.tribunal} · Câmara/Turma julgadora",
            })
        classe, assunto, grau = CAPAS[nome]
        primeiro = min((m["data_hora"] for m in movimentos), default=None)
        capa = {
            "classe": classe, "assuntos": assunto, "orgao_julgador": orgao, "graus": grau,
            "data_ajuizamento": primeiro[:10] if primeiro else None, "sistema": "PJe (fictício)",
            "ultima_atualizacao_fonte": max((m["data_hora"] for m in movimentos), default=None),
        }
        return ResultadoConsulta(capa, movimentos)


def obter_fonte(nome: str) -> Fonte:
    return FonteDataJud() if nome == "datajud" else FonteDemo()
