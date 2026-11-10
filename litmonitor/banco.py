"""Acesso ao SQLite: esquema e consultas."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from . import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS processos (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    numero                   TEXT NOT NULL,
    numero_limpo             TEXT NOT NULL UNIQUE,
    tribunal                 TEXT NOT NULL,
    cliente                  TEXT NOT NULL DEFAULT '',
    parte_contraria          TEXT NOT NULL DEFAULT '',
    responsavel              TEXT NOT NULL DEFAULT '',
    observacoes              TEXT NOT NULL DEFAULT '',
    ativo                    INTEGER NOT NULL DEFAULT 1,
    classe                   TEXT NOT NULL DEFAULT '',
    assuntos                 TEXT NOT NULL DEFAULT '',
    orgao_julgador           TEXT NOT NULL DEFAULT '',
    graus                    TEXT NOT NULL DEFAULT '',
    data_ajuizamento         TEXT,
    sistema                  TEXT NOT NULL DEFAULT '',
    ultima_atualizacao_fonte TEXT,
    ultima_consulta_em       TEXT,
    situacao_consulta        TEXT NOT NULL DEFAULT 'pendente',
    erro_consulta            TEXT NOT NULL DEFAULT '',
    consultas_realizadas     INTEGER NOT NULL DEFAULT 0,
    fonte                    TEXT NOT NULL DEFAULT '',
    criado_em                TEXT NOT NULL,
    atualizado_em            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS movimentacoes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    processo_id       INTEGER NOT NULL REFERENCES processos(id) ON DELETE CASCADE,
    chave             TEXT NOT NULL,
    codigo            INTEGER,
    nome              TEXT NOT NULL DEFAULT '',
    descricao         TEXT NOT NULL DEFAULT '',
    complementos_json TEXT NOT NULL DEFAULT '[]',
    grau              TEXT NOT NULL DEFAULT '',
    orgao             TEXT NOT NULL DEFAULT '',
    data_hora         TEXT NOT NULL,
    categoria         TEXT NOT NULL,
    rotulo            TEXT NOT NULL,
    relevancia        TEXT NOT NULL,
    providencia       TEXT NOT NULL DEFAULT '',
    vinculada_a       TEXT NOT NULL DEFAULT '',
    nova              INTEGER NOT NULL DEFAULT 1,
    status            TEXT NOT NULL,
    prazo             TEXT,
    prazo_situacao    TEXT,
    prazo_regra       TEXT NOT NULL DEFAULT '',
    prazo_definido_em TEXT,
    observacoes       TEXT NOT NULL DEFAULT '',
    atualizado_por    TEXT NOT NULL DEFAULT 'Automação',
    consulta_id       INTEGER REFERENCES consultas(id),
    detectada_em      TEXT NOT NULL,
    atualizado_em     TEXT NOT NULL,
    UNIQUE (processo_id, chave)
);

CREATE TABLE IF NOT EXISTS consultas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte           TEXT NOT NULL,
    origem          TEXT NOT NULL DEFAULT 'painel',
    iniciada_em     TEXT NOT NULL,
    finalizada_em   TEXT,
    processos       INTEGER NOT NULL DEFAULT 0,
    sucesso         INTEGER NOT NULL DEFAULT 0,
    nao_localizados INTEGER NOT NULL DEFAULT 0,
    erros           INTEGER NOT NULL DEFAULT 0,
    novas           INTEGER NOT NULL DEFAULT 0,
    relevantes      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS notificacoes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    processo_id      INTEGER REFERENCES processos(id) ON DELETE CASCADE,
    movimentacao_id  INTEGER REFERENCES movimentacoes(id) ON DELETE CASCADE,
    tipo             TEXT NOT NULL,
    situacao         TEXT NOT NULL,
    destino          TEXT NOT NULL DEFAULT 'E-mail',
    criado_em        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relatorios (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo              TEXT NOT NULL,
    origem            TEXT NOT NULL DEFAULT 'painel',
    periodo_inicio    TEXT NOT NULL,
    periodo_fim       TEXT NOT NULL,
    arquivo_pdf       TEXT NOT NULL,
    arquivo_xlsx      TEXT NOT NULL,
    processos_atencao INTEGER NOT NULL DEFAULT 0,
    criado_em         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS historico (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    processo_id  INTEGER NOT NULL REFERENCES processos(id) ON DELETE CASCADE,
    evento       TEXT NOT NULL,
    detalhe      TEXT NOT NULL DEFAULT '',
    autor        TEXT NOT NULL DEFAULT 'Automação',
    criado_em    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS configuracoes (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_mov_processo ON movimentacoes(processo_id, data_hora);
CREATE INDEX IF NOT EXISTS ix_mov_status ON movimentacoes(status);
CREATE INDEX IF NOT EXISTS ix_notif_mov ON notificacoes(movimentacao_id, tipo);
"""

STATUS_ABERTOS = ("Pendente", "Em andamento")


def agora_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


@contextmanager
def conexao() -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(config.caminho_banco(), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def inicializar() -> None:
    with conexao() as con:
        con.executescript(ESQUEMA)


# --------------------------------------------------------------------------- configurações


def obter_config(chave: str, padrao: str = "") -> str:
    with conexao() as con:
        linha = con.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,)).fetchone()
    return linha["valor"] if linha else padrao


def salvar_config(chave: str, valor: str) -> None:
    with conexao() as con:
        con.execute("INSERT INTO configuracoes (chave, valor) VALUES (?, ?) "
                    "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor", (chave, valor))


# --------------------------------------------------------------------------- processos


def obter_processo_por_numero(numero_limpo: str) -> dict[str, Any] | None:
    with conexao() as con:
        linha = con.execute("SELECT * FROM processos WHERE numero_limpo = ?", (numero_limpo,)).fetchone()
    return dict(linha) if linha else None


def obter_processo(processo_id: int) -> dict[str, Any] | None:
    with conexao() as con:
        linha = con.execute("SELECT * FROM processos WHERE id = ?", (processo_id,)).fetchone()
    return dict(linha) if linha else None


def listar_processos(apenas_ativos: bool = False) -> list[dict[str, Any]]:
    sql = """
        SELECT p.*,
               (SELECT COUNT(*) FROM movimentacoes m WHERE m.processo_id = p.id) AS qtd_movimentacoes,
               (SELECT MAX(m.data_hora) FROM movimentacoes m WHERE m.processo_id = p.id) AS ultima_movimentacao
        FROM processos p
    """
    if apenas_ativos:
        sql += " WHERE p.ativo = 1"
    sql += " ORDER BY p.cliente, p.numero"
    with conexao() as con:
        return [dict(l) for l in con.execute(sql)]


def inserir_processo(dados: dict[str, Any]) -> int:
    agora = agora_iso()
    with conexao() as con:
        cur = con.execute(
            """INSERT INTO processos (numero, numero_limpo, tribunal, cliente, parte_contraria, responsavel,
                   observacoes, ativo, criado_em, atualizado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (dados["numero"], dados["numero_limpo"], dados["tribunal"], dados.get("cliente", ""),
             dados.get("parte_contraria", ""), dados.get("responsavel", ""), dados.get("observacoes", ""),
             dados.get("criado_em", agora), agora))
        return int(cur.lastrowid)


def atualizar_processo(processo_id: int, campos: dict[str, Any]) -> None:
    if not campos:
        return
    campos = {**campos, "atualizado_em": agora_iso()}
    colunas = ", ".join(f"{c} = ?" for c in campos)
    with conexao() as con:
        con.execute(f"UPDATE processos SET {colunas} WHERE id = ?", (*campos.values(), processo_id))


def excluir_tudo() -> None:
    with conexao() as con:
        for tabela in ("notificacoes", "historico", "movimentacoes", "relatorios", "consultas", "processos"):
            con.execute(f"DELETE FROM {tabela}")


# --------------------------------------------------------------------------- movimentações

SELECT_MOV = """
    SELECT m.*, p.numero, p.cliente, p.responsavel, p.tribunal, p.classe, p.ativo AS processo_ativo
    FROM movimentacoes m JOIN processos p ON p.id = m.processo_id
"""


def _mov(linha: sqlite3.Row) -> dict[str, Any]:
    d = dict(linha)
    d["complementos"] = json.loads(d.pop("complementos_json") or "[]")
    d["nova"] = bool(d["nova"])
    return d


def movimentacoes_por_chave(processo_id: int) -> dict[str, dict[str, Any]]:
    with conexao() as con:
        linhas = con.execute("SELECT * FROM movimentacoes WHERE processo_id = ?", (processo_id,)).fetchall()
    return {l["chave"]: _mov(l) for l in linhas}


def inserir_movimentacao(dados: dict[str, Any]) -> int:
    agora = agora_iso()
    with conexao() as con:
        cur = con.execute(
            """INSERT INTO movimentacoes (processo_id, chave, codigo, nome, descricao, complementos_json, grau, orgao,
                   data_hora, categoria, rotulo, relevancia, providencia, vinculada_a, nova, status, prazo,
                   prazo_situacao, prazo_regra, prazo_definido_em, consulta_id, detectada_em, atualizado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (dados["processo_id"], dados["chave"], dados.get("codigo"), dados.get("nome", ""), dados.get("descricao", ""),
             json.dumps(dados.get("complementos", []), ensure_ascii=False), dados.get("grau", ""), dados.get("orgao", ""),
             dados["data_hora"], dados["categoria"], dados["rotulo"], dados["relevancia"], dados.get("providencia", ""),
             dados.get("vinculada_a", ""), int(dados.get("nova", True)), dados["status"], dados.get("prazo"),
             dados.get("prazo_situacao"), dados.get("prazo_regra", ""), dados.get("prazo") and agora,
             dados.get("consulta_id"), agora, agora))
        return int(cur.lastrowid)


def atualizar_movimentacao(mov_id: int, campos: dict[str, Any]) -> None:
    if not campos:
        return
    campos = {**campos, "atualizado_em": agora_iso()}
    colunas = ", ".join(f"{c} = ?" for c in campos)
    with conexao() as con:
        con.execute(f"UPDATE movimentacoes SET {colunas} WHERE id = ?", (*campos.values(), mov_id))


def obter_movimentacao(mov_id: int) -> dict[str, Any] | None:
    with conexao() as con:
        linha = con.execute(SELECT_MOV + " WHERE m.id = ?", (mov_id,)).fetchone()
    return _mov(linha) if linha else None


def listar_movimentacoes(processo_id: int | None = None, apenas_abertas: bool = False,
                         desde: str | None = None, apenas_novas: bool = False) -> list[dict[str, Any]]:
    filtros, params = ["p.ativo = 1"] if processo_id is None else [], []
    if processo_id is not None:
        filtros.append("m.processo_id = ?")
        params.append(processo_id)
    if apenas_abertas:
        filtros.append(f"m.status IN ({', '.join('?' * len(STATUS_ABERTOS))})")
        params.extend(STATUS_ABERTOS)
    if desde:
        filtros.append("m.detectada_em >= ?")
        params.append(desde)
    if apenas_novas:
        filtros.append("m.nova = 1")
    sql = SELECT_MOV + (" WHERE " + " AND ".join(filtros) if filtros else "") + " ORDER BY m.data_hora DESC, m.id DESC"
    with conexao() as con:
        return [_mov(l) for l in con.execute(sql, params)]


# --------------------------------------------------------------------------- consultas, notificações, histórico


def iniciar_consulta(fonte: str, origem: str) -> int:
    with conexao() as con:
        cur = con.execute("INSERT INTO consultas (fonte, origem, iniciada_em) VALUES (?, ?, ?)",
                          (fonte, origem, agora_iso()))
        return int(cur.lastrowid)


def finalizar_consulta(consulta_id: int, totais: dict[str, int]) -> None:
    with conexao() as con:
        con.execute(
            """UPDATE consultas SET finalizada_em = ?, processos = ?, sucesso = ?, nao_localizados = ?, erros = ?,
                   novas = ?, relevantes = ? WHERE id = ?""",
            (agora_iso(), totais["processos"], totais["sucesso"], totais["nao_localizados"], totais["erros"],
             totais["novas"], totais["relevantes"], consulta_id))


def listar_consultas(limite: int = 20) -> list[dict[str, Any]]:
    with conexao() as con:
        return [dict(l) for l in con.execute("SELECT * FROM consultas ORDER BY id DESC LIMIT ?", (limite,))]


def inserir_notificacao(processo_id: int | None, movimentacao_id: int | None, tipo: str, situacao: str,
                        destino: str = "E-mail") -> int:
    with conexao() as con:
        cur = con.execute(
            "INSERT INTO notificacoes (processo_id, movimentacao_id, tipo, situacao, destino, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?)", (processo_id, movimentacao_id, tipo, situacao, destino, agora_iso()))
        return int(cur.lastrowid)


def ultima_notificacao(movimentacao_id: int, tipo: str) -> str | None:
    with conexao() as con:
        linha = con.execute("SELECT MAX(criado_em) AS q FROM notificacoes WHERE movimentacao_id = ? AND tipo = ?",
                            (movimentacao_id, tipo)).fetchone()
    return linha["q"] if linha else None


def ultima_notificacao_geral(tipo: str) -> str | None:
    with conexao() as con:
        linha = con.execute("SELECT MAX(criado_em) AS q FROM notificacoes WHERE tipo = ?", (tipo,)).fetchone()
    return linha["q"] if linha else None


def listar_notificacoes(limite: int = 200, processo_id: int | None = None) -> list[dict[str, Any]]:
    sql = """SELECT n.*, p.numero, p.cliente, m.rotulo, m.descricao
             FROM notificacoes n LEFT JOIN processos p ON p.id = n.processo_id
             LEFT JOIN movimentacoes m ON m.id = n.movimentacao_id"""
    params: list[Any] = []
    if processo_id is not None:
        sql += " WHERE n.processo_id = ?"
        params.append(processo_id)
    sql += " ORDER BY n.id DESC LIMIT ?"
    params.append(limite)
    with conexao() as con:
        return [dict(l) for l in con.execute(sql, params)]


def registrar_historico(processo_id: int, evento: str, detalhe: str = "", autor: str = "Automação") -> None:
    with conexao() as con:
        con.execute("INSERT INTO historico (processo_id, evento, detalhe, autor, criado_em) VALUES (?, ?, ?, ?, ?)",
                    (processo_id, evento, detalhe, autor, agora_iso()))


def listar_historico(processo_id: int) -> list[dict[str, Any]]:
    with conexao() as con:
        return [dict(l) for l in con.execute(
            "SELECT * FROM historico WHERE processo_id = ? ORDER BY id DESC", (processo_id,))]


def inserir_relatorio(dados: dict[str, Any]) -> int:
    with conexao() as con:
        cur = con.execute(
            """INSERT INTO relatorios (tipo, origem, periodo_inicio, periodo_fim, arquivo_pdf, arquivo_xlsx,
                   processos_atencao, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (dados["tipo"], dados["origem"], dados["periodo_inicio"], dados["periodo_fim"], dados["arquivo_pdf"],
             dados["arquivo_xlsx"], dados["processos_atencao"], agora_iso()))
        return int(cur.lastrowid)


def obter_relatorio(relatorio_id: int) -> dict[str, Any] | None:
    with conexao() as con:
        linha = con.execute("SELECT * FROM relatorios WHERE id = ?", (relatorio_id,)).fetchone()
    return dict(linha) if linha else None


def listar_relatorios(limite: int = 30) -> list[dict[str, Any]]:
    with conexao() as con:
        return [dict(l) for l in con.execute("SELECT * FROM relatorios ORDER BY id DESC LIMIT ?", (limite,))]
