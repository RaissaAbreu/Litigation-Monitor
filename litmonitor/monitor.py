"""Regras de negócio: importação da carteira, consulta às fontes, prazos, atenção e alertas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from . import banco, classificacao, config, fontes, mensagens
from .classificacao import PESO_RELEVANCIA
from .planilha import LeituraPlanilha

STATUS_MOV = ["Pendente", "Em andamento", "Concluída", "Sem providência", "Informativa", "Histórico"]
STATUS_ABERTOS = banco.STATUS_ABERTOS
NIVEIS = ["Crítica", "Alta", "Média", "Verificar", "Em dia"]
SITUACOES_CONSULTA = {"pendente": "Aguardando 1ª consulta", "ok": "Consultado", "nao_localizado": "Não localizado",
                      "erro": "Falha na consulta"}
TIPOS_NOTIFICACAO = {
    "movimentacao_relevante": "Nova movimentação relevante",
    "prazo_proximo": "Prazo próximo",
    "prazo_hoje": "Prazo vence hoje",
    "prazo_vencido": "Prazo vencido",
    "resumo_diario": "Resumo diário",
    "relatorio_semanal": "Relatório semanal",
}
SITUACOES_NOTIFICACAO = ("enviada", "sem_canal", "falha")


def hoje() -> date:
    return date.today()


def formatar_data(valor: str | date | None) -> str:
    if not valor:
        return "—"
    if isinstance(valor, str):
        valor = date.fromisoformat(valor[:10])
    return valor.strftime("%d/%m/%Y")


def fonte_ativa() -> str:
    return banco.obter_config("fonte", config.fonte_padrao())


def definir_fonte(nome: str) -> None:
    if nome not in fontes.FONTES:
        raise ValueError(f"Fonte desconhecida: {nome}")
    banco.salvar_config("fonte", nome)


# --------------------------------------------------------------------------- importação


@dataclass
class ResultadoImportacao:
    incluidos: int = 0
    atualizados: int = 0
    reativados: int = 0
    desativados: int = 0
    invalidos: list[dict[str, Any]] = field(default_factory=list)
    duplicados: int = 0


def importar(leitura: LeituraPlanilha, desativar_ausentes: bool = False, autor: str = "Planilha") -> ResultadoImportacao:
    """Inclui processos novos, atualiza dados cadastrais e (opcionalmente) desativa os que saíram da planilha."""
    banco.inicializar()
    resultado = ResultadoImportacao(duplicados=leitura.duplicadas,
                                    invalidos=[{"linha": l.linha, "numero": l.numero_informado, "erro": l.erro}
                                               for l in leitura.invalidas])
    presentes = set()
    for linha in leitura.validas:
        dados = linha.dados or {}
        presentes.add(dados["numero_limpo"])
        existente = banco.obter_processo_por_numero(dados["numero_limpo"])
        if existente is None:
            pid = banco.inserir_processo(dados)
            banco.registrar_historico(pid, "Processo incluído no monitoramento", f"Linha {linha.linha} da planilha", autor)
            resultado.incluidos += 1
            continue
        campos = {c: dados[c] for c in ("cliente", "parte_contraria", "responsavel", "observacoes")
                  if dados.get(c) and dados[c] != existente[c]}
        if not existente["ativo"]:
            campos["ativo"] = 1
            resultado.reativados += 1
            banco.registrar_historico(existente["id"], "Processo reativado", "Voltou a constar na planilha", autor)
        elif campos:
            resultado.atualizados += 1
        banco.atualizar_processo(existente["id"], campos)

    if desativar_ausentes:
        for p in banco.listar_processos(apenas_ativos=True):
            if p["numero_limpo"] not in presentes:
                banco.atualizar_processo(p["id"], {"ativo": 0})
                banco.registrar_historico(p["id"], "Processo desativado", "Não consta mais na planilha", autor)
                resultado.desativados += 1
    return resultado


def definir_ativo(processo_id: int, ativo: bool, autor: str = "Analista") -> None:
    banco.atualizar_processo(processo_id, {"ativo": int(ativo)})
    banco.registrar_historico(processo_id, "Processo reativado" if ativo else "Monitoramento pausado", "", autor)


# --------------------------------------------------------------------------- consulta


@dataclass
class ResumoConsulta:
    consulta_id: int
    fonte: str
    processos: int = 0
    sucesso: int = 0
    nao_localizados: int = 0
    erros: int = 0
    novas: int = 0
    relevantes: int = 0
    falhas: list[dict[str, str]] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _status_inicial(cl: classificacao.Classificacao, nova: bool) -> str:
    if not nova:
        return "Histórico"
    return "Informativa" if cl.relevancia == "Baixa" else "Pendente"


def sincronizar_processo(processo: dict[str, Any], fonte: fontes.Fonte, consulta_id: int | None = None,
                         referencia: date | None = None) -> tuple[int, int]:
    """Consulta um processo, grava movimentações novas e devolve (novas, relevantes).

    Na primeira consulta do processo, o histórico é gravado sem gerar alertas; só as movimentações
    relevantes dos últimos LM_DIAS_RETROATIVOS dias contam como novas.
    """
    referencia = referencia or hoje()
    resultado = fonte.consultar(processo)
    primeira = int(processo.get("consultas_realizadas") or 0) == 0
    limite_retroativo = referencia - timedelta(days=config.dias_retroativos())
    existentes = banco.movimentacoes_por_chave(processo["id"])
    novas = relevantes = 0

    for mov, cl in classificacao.classificar_lote(resultado.movimentos):
        chave = classificacao.chave_movimento(mov)
        prazo = cl.prazo.isoformat() if cl.prazo else None
        if chave in existentes:
            atual = existentes[chave]
            # Reajusta só o que ainda é estimativa automática (nunca o que o analista confirmou)
            if atual["prazo_situacao"] in ("estimado", None) and atual["status"] in STATUS_ABERTOS \
                    and (atual["prazo"] != prazo or atual["vinculada_a"] != cl.vinculada_a):
                banco.atualizar_movimentacao(atual["id"], {
                    "prazo": prazo, "prazo_situacao": cl.prazo_situacao, "prazo_regra": cl.prazo_regra,
                    "prazo_definido_em": banco.agora_iso(), "vinculada_a": cl.vinculada_a})
            continue
        data_mov = classificacao.data_do_movimento(mov)
        nova = not primeira or (data_mov >= limite_retroativo and cl.relevancia != "Baixa")
        banco.inserir_movimentacao({
            "processo_id": processo["id"], "chave": chave, "codigo": mov.get("codigo"), "nome": mov.get("nome", ""),
            "descricao": classificacao.descrever(mov), "complementos": mov.get("complementos", []),
            "grau": mov.get("grau", ""), "orgao": mov.get("orgao", ""), "data_hora": mov["data_hora"],
            "categoria": cl.categoria, "rotulo": cl.rotulo, "relevancia": cl.relevancia,
            "providencia": cl.providencia, "vinculada_a": cl.vinculada_a, "nova": nova,
            "status": _status_inicial(cl, nova), "prazo": prazo, "prazo_situacao": cl.prazo_situacao,
            "prazo_regra": cl.prazo_regra, "consulta_id": consulta_id,
        })
        if nova:
            novas += 1
            relevantes += cl.relevancia != "Baixa"

    banco.atualizar_processo(processo["id"], {
        **{k: v for k, v in resultado.capa.items() if v is not None},
        "ultima_consulta_em": banco.agora_iso(), "situacao_consulta": "ok", "erro_consulta": "",
        "consultas_realizadas": int(processo.get("consultas_realizadas") or 0) + 1, "fonte": fonte.nome,
    })
    if primeira:
        banco.registrar_historico(processo["id"], "Primeira consulta",
                                  f"{len(resultado.movimentos)} movimentação(ões) no histórico · {novas} recente(s)")
    elif novas:
        banco.registrar_historico(processo["id"], "Novas movimentações",
                                  f"{novas} nova(s), {relevantes} relevante(s)")
    return novas, relevantes


def sincronizar(origem: str = "painel", fonte: fontes.Fonte | None = None,
                processo_ids: list[int] | None = None, referencia: date | None = None) -> ResumoConsulta:
    """Consulta todos os processos ativos (ou os indicados) na fonte configurada."""
    banco.inicializar()
    fonte = fonte or fontes.obter_fonte(fonte_ativa())
    consulta_id = banco.iniciar_consulta(fonte.nome, origem)
    resumo = ResumoConsulta(consulta_id, fonte.nome)
    processos = banco.listar_processos(apenas_ativos=True)
    if processo_ids is not None:
        processos = [p for p in processos if p["id"] in processo_ids]
    for processo in processos:
        resumo.processos += 1
        try:
            novas, relevantes = sincronizar_processo(processo, fonte, consulta_id, referencia)
        except fontes.ProcessoNaoEncontrado as erro:
            resumo.nao_localizados += 1
            resumo.falhas.append({"numero": processo["numero"], "erro": str(erro)})
            banco.atualizar_processo(processo["id"], {"situacao_consulta": "nao_localizado", "erro_consulta": str(erro),
                                                      "ultima_consulta_em": banco.agora_iso(), "fonte": fonte.nome})
        except (fontes.ErroFonte, ValueError) as erro:
            resumo.erros += 1
            resumo.falhas.append({"numero": processo["numero"], "erro": str(erro)})
            banco.atualizar_processo(processo["id"], {"situacao_consulta": "erro", "erro_consulta": str(erro),
                                                      "ultima_consulta_em": banco.agora_iso(), "fonte": fonte.nome})
        else:
            resumo.sucesso += 1
            resumo.novas += novas
            resumo.relevantes += relevantes
    banco.finalizar_consulta(consulta_id, resumo.como_dict())
    return resumo


# --------------------------------------------------------------------------- prazos e atenção


def dias_ate(prazo: str | None, referencia: date | None = None) -> int | None:
    if not prazo:
        return None
    return (date.fromisoformat(prazo[:10]) - (referencia or hoje())).days


def situacao_prazo(mov: dict[str, Any], referencia: date | None = None) -> str | None:
    """vencido | hoje | proximo | no_prazo | a_confirmar | None (sem prazo ou movimentação encerrada)."""
    if mov["status"] not in STATUS_ABERTOS:
        return None
    if mov.get("prazo_situacao") == "a_confirmar" and not mov.get("prazo"):
        return "a_confirmar"
    dias = dias_ate(mov.get("prazo"), referencia)
    if dias is None:
        return None
    if dias < 0:
        return "vencido"
    if dias == 0:
        return "hoje"
    return "proximo" if dias <= config.dias_alerta_prazo() else "no_prazo"


def texto_prazo(mov: dict[str, Any], referencia: date | None = None) -> str:
    if mov.get("prazo_situacao") == "a_confirmar" and not mov.get("prazo"):
        return "Data a confirmar"
    if not mov.get("prazo"):
        return "Sem prazo"
    dias = dias_ate(mov["prazo"], referencia)
    data = formatar_data(mov["prazo"])
    tipo = {"estimado": " (estimado)", "confirmado": "", "a_confirmar": ""}.get(mov.get("prazo_situacao") or "", "")
    if mov["status"] not in STATUS_ABERTOS:
        return f"Prazo {data}{tipo}"
    if dias < 0:
        return f"Vencido há {-dias} dia(s) · {data}{tipo}"
    if dias == 0:
        return f"Vence hoje · {data}{tipo}"
    return f"{dias} dia(s) · {data}{tipo}"


def nivel_atencao(movs_abertas: list[dict[str, Any]], referencia: date | None = None) -> str:
    """Crítica: prazo vencido ou em até 2 dias · Alta: evento de alta relevância ou prazo em até 5 dias ·
    Média: evento de média relevância pendente · Em dia: nada pendente."""
    nivel = "Em dia"
    for mov in movs_abertas:
        dias = dias_ate(mov.get("prazo"), referencia)
        if dias is not None and dias <= 2:
            return "Crítica"
        if (dias is not None and dias <= 5) or mov["relevancia"] == "Alta" or mov.get("prazo_situacao") == "a_confirmar":
            nivel = "Alta"
        elif mov["relevancia"] == "Média" and nivel == "Em dia":
            nivel = "Média"
    return nivel


def painel_processos(referencia: date | None = None, incluir_inativos: bool = False) -> list[dict[str, Any]]:
    """Processos com nível de atenção, pendências e próximo prazo — base do painel e dos relatórios."""
    abertas = banco.listar_movimentacoes(apenas_abertas=True)
    por_processo: dict[int, list[dict[str, Any]]] = {}
    for m in abertas:
        por_processo.setdefault(m["processo_id"], []).append(m)
    linhas = []
    for p in banco.listar_processos(apenas_ativos=not incluir_inativos):
        movs = por_processo.get(p["id"], [])
        prazos = sorted((m for m in movs if m.get("prazo")), key=lambda m: m["prazo"])
        nivel = nivel_atencao(movs, referencia)
        problema = p["situacao_consulta"] in ("erro", "nao_localizado")
        if nivel == "Em dia" and problema:
            nivel = "Verificar"
        linhas.append({
            **p,
            "nivel": nivel,
            "pendencias": movs,
            "qtd_pendencias": len(movs),
            "proximo_prazo": prazos[0] if prazos else None,
            "problema_consulta": problema,
            "exige_atencao": nivel != "Em dia",
        })
    ordem = {n: i for i, n in enumerate(NIVEIS)}
    linhas.sort(key=lambda l: (ordem[l["nivel"]], l["proximo_prazo"]["prazo"] if l["proximo_prazo"] else "9999",
                               not l["problema_consulta"], l["cliente"]))
    return linhas


def indicadores(referencia: date | None = None) -> dict[str, Any]:
    processos = painel_processos(referencia)
    abertas = [m for p in processos for m in p["pendencias"]]
    situacoes = [situacao_prazo(m, referencia) for m in abertas]
    desde = (datetime.combine(referencia or hoje(), datetime.min.time()) - timedelta(days=7)).isoformat()
    return {
        "processos": len(processos),
        "exigem_atencao": sum(p["exige_atencao"] for p in processos),
        "pendencias": len(abertas),
        "vencidos": situacoes.count("vencido"),
        "vencem_breve": situacoes.count("hoje") + situacoes.count("proximo"),
        "a_confirmar": situacoes.count("a_confirmar"),
        "novas_7_dias": len(banco.listar_movimentacoes(desde=desde, apenas_novas=True)),
        "problemas_consulta": sum(p["problema_consulta"] for p in processos),
        "por_nivel": {n: sum(p["nivel"] == n for p in processos) for n in NIVEIS},
    }


# --------------------------------------------------------------------------- ações do analista


def atualizar_movimentacao(mov_id: int, status: str, observacoes: str = "", prazo: date | None = None,
                           prazo_alterado: bool = False, autor: str = "Analista") -> None:
    mov = banco.obter_movimentacao(mov_id)
    if mov is None:
        raise ValueError("Movimentação não encontrada")
    if status not in STATUS_MOV:
        raise ValueError(f"Status inválido: {status}")
    campos: dict[str, Any] = {"status": status, "observacoes": observacoes, "atualizado_por": autor}
    detalhes = []
    if status != mov["status"]:
        detalhes.append(f"{mov['status']} → {status}")
    if prazo_alterado:
        novo = prazo.isoformat() if prazo else None
        campos.update(prazo=novo, prazo_situacao="confirmado" if novo else None, prazo_definido_em=banco.agora_iso())
        detalhes.append(f"prazo {'confirmado em ' + formatar_data(novo) if novo else 'removido'}")
    if observacoes != mov["observacoes"] and observacoes:
        detalhes.append("observação registrada")
    banco.atualizar_movimentacao(mov_id, campos)
    if detalhes:
        banco.registrar_historico(mov["processo_id"], f"{mov['rotulo']} de {formatar_data(mov['data_hora'])}",
                                  " · ".join(detalhes), autor)


# --------------------------------------------------------------------------- alertas (consumidos pelo n8n)


def _peso(relevancia: str) -> int:
    return PESO_RELEVANCIA.get(relevancia, 0)


def montar_notificacao(mov: dict[str, Any], tipo: str, referencia: date | None = None) -> dict[str, Any]:
    return {
        "processo_id": mov["processo_id"],
        "movimentacao_id": mov["id"],
        "numero": mov["numero"],
        "tipo": tipo,
        "tipo_descricao": TIPOS_NOTIFICACAO[tipo],
        "destinatario": mov.get("responsavel") or "Equipe",
        "email": mensagens.email_movimentacao(mov, tipo, texto_prazo(mov, referencia)),
    }


def alertas_pendentes(agora: datetime | None = None) -> list[dict[str, Any]]:
    """Alertas ainda não enviados.

    - movimentacao_relevante: uma vez por movimentação nova com relevância ≥ LM_RELEVANCIA_ALERTA;
    - prazo_proximo / prazo_hoje: uma vez por movimentação e por definição de prazo;
    - prazo_vencido: repete a cada LM_HORAS_REPETICAO_VENCIDO horas enquanto a pendência estiver aberta.
    """
    banco.inicializar()
    agora = agora or datetime.now()
    referencia = agora.date()
    minimo = _peso(config.relevancia_minima_alerta())
    alertas = []
    for mov in sorted(banco.listar_movimentacoes(apenas_abertas=True), key=lambda m: m["data_hora"]):
        if mov["nova"] and _peso(mov["relevancia"]) >= minimo \
                and not banco.ultima_notificacao(mov["id"], "movimentacao_relevante"):
            alertas.append(montar_notificacao(mov, "movimentacao_relevante", referencia))

        situacao = situacao_prazo(mov, referencia)
        tipo = {"vencido": "prazo_vencido", "hoje": "prazo_hoje", "proximo": "prazo_proximo"}.get(situacao or "")
        if not tipo:
            continue
        ultima = banco.ultima_notificacao(mov["id"], tipo)
        ultima_dt = datetime.fromisoformat(ultima) if ultima else None
        if tipo == "prazo_vencido":
            devido = ultima_dt is None or agora - ultima_dt >= timedelta(hours=config.horas_repeticao_vencido())
        else:
            definido = mov.get("prazo_definido_em") or mov["detectada_em"]
            devido = ultima_dt is None or ultima_dt < datetime.fromisoformat(definido)
        if devido:
            alertas.append(montar_notificacao(mov, tipo, referencia))
    return alertas


def registrar_notificacao(tipo: str, situacao: str, movimentacao_id: int | None = None,
                          processo_id: int | None = None, destino: str = "E-mail") -> int:
    if tipo not in TIPOS_NOTIFICACAO:
        raise ValueError(f"Tipo de notificação inválido: {tipo}")
    if situacao not in SITUACOES_NOTIFICACAO:
        raise ValueError(f"Situação inválida: {situacao}")
    if movimentacao_id is not None and processo_id is None:
        mov = banco.obter_movimentacao(movimentacao_id)
        if mov is None:
            raise ValueError("Movimentação não encontrada")
        processo_id = mov["processo_id"]
    return banco.inserir_notificacao(processo_id, movimentacao_id, tipo, situacao, destino)
