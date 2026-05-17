# =============================================================================
# src/data/loader.py — Fiscal Deadlines
# Funções de acesso ao banco de dados (CRUD).
#
# Responsabilidade única: ler e escrever dados no banco SQLite.
# Nenhuma lógica de análise, nenhuma lógica de apresentação aqui.
#
# Funções disponíveis:
#   Clientes   — criar_cliente, listar_clientes, buscar_cliente, atualizar_cliente
#   Obrigações — listar_tipos_obrigacao
#   Prazos     — criar_prazo, listar_prazos, buscar_prazo,
#                atualizar_prazo, deletar_prazo
#
# Uso:
#   from src.data.loader import criar_cliente, listar_prazos
# =============================================================================

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError

from src.data.database import ClienteDB, PrazoDB, TipoObrigacaoDB, get_session
from src.data.models import (
    Cliente,
    ClienteCreate,
    ClienteUpdate,
    Prazo,
    PrazoCreate,
    PrazoUpdate,
    TipoObrigacao,
)

logger = logging.getLogger(__name__)


# =============================================================================
# EXCEÇÕES CUSTOMIZADAS
# =============================================================================

class ClienteNotFoundError(Exception):
    """Lançada quando um cliente não é encontrado pelo id informado."""


class PrazoNotFoundError(Exception):
    """Lançada quando um prazo não é encontrado pelo id informado."""


class PrazoDuplicadoError(Exception):
    """
    Lançada quando já existe um prazo para a combinação
    (cliente_id, tipo_obrigacao_id, competencia).
    """


class SchemaValidationError(Exception):
    """Lançada quando os dados recebidos falham na validação Pydantic."""


# =============================================================================
# CLIENTES
# =============================================================================

def criar_cliente(dados: ClienteCreate) -> Cliente:
    """
    Cadastra um novo cliente na carteira do escritório.

    Args:
        dados: ClienteCreate com nome, CNPJ, regime tributário e flag ativo.

    Returns:
        Cliente persistido com id e timestamp de criação.

    Raises:
        PrazoDuplicadoError: se já existir cliente com o mesmo CNPJ.
    """
    with get_session() as session:
        registro = ClienteDB(
            nome=dados.nome,
            cnpj=dados.cnpj,
            regime_tributario=dados.regime_tributario,
            ativo=dados.ativo,
            criado_em=datetime.now(timezone.utc),
        )
        session.add(registro)
        try:
            session.commit()
            session.refresh(registro)
            logger.info("Cliente criado: id=%s nome=%r", registro.id, registro.nome)
            return Cliente.model_validate(registro)
        except IntegrityError:
            session.rollback()
            raise PrazoDuplicadoError(
                f"Já existe um cliente com o CNPJ '{dados.cnpj}'."
            )


def listar_clientes(apenas_ativos: bool = True) -> list[Cliente]:
    """
    Retorna todos os clientes da carteira.

    Args:
        apenas_ativos: se True (padrão), retorna somente clientes com ativo=True.

    Returns:
        Lista de Cliente ordenada por nome.
    """
    with get_session() as session:
        query = session.query(ClienteDB)
        if apenas_ativos:
            query = query.filter(ClienteDB.ativo == True)  # noqa: E712
        registros = query.order_by(ClienteDB.nome).all()
        return [Cliente.model_validate(r) for r in registros]


def buscar_cliente(cliente_id: int) -> Cliente:
    """
    Busca um cliente pelo id.

    Args:
        cliente_id: identificador único do cliente.

    Returns:
        Cliente encontrado.

    Raises:
        ClienteNotFoundError: se nenhum cliente com o id informado existir.
    """
    with get_session() as session:
        registro = session.get(ClienteDB, cliente_id)
        if registro is None:
            raise ClienteNotFoundError(
                f"Cliente id={cliente_id} não encontrado."
            )
        return Cliente.model_validate(registro)


def atualizar_cliente(cliente_id: int, dados: ClienteUpdate) -> Cliente:
    """
    Atualiza parcialmente um cliente (PATCH).
    Apenas os campos informados em dados são alterados.

    Args:
        cliente_id: identificador único do cliente.
        dados: ClienteUpdate com os campos a alterar.

    Returns:
        Cliente atualizado.

    Raises:
        ClienteNotFoundError: se o cliente não existir.
    """
    with get_session() as session:
        registro = session.get(ClienteDB, cliente_id)
        if registro is None:
            raise ClienteNotFoundError(
                f"Cliente id={cliente_id} não encontrado."
            )
        alteracoes = dados.model_dump(exclude_none=True)
        for campo, valor in alteracoes.items():
            setattr(registro, campo, valor)
        session.commit()
        session.refresh(registro)
        logger.info("Cliente atualizado: id=%s campos=%s", cliente_id, list(alteracoes))
        return Cliente.model_validate(registro)


# =============================================================================
# TIPOS DE OBRIGAÇÃO (somente leitura — catálogo fixo)
# =============================================================================

def listar_tipos_obrigacao() -> list[TipoObrigacao]:
    """
    Retorna o catálogo completo de tipos de obrigação fiscal.
    Ordenado por nome.

    Returns:
        Lista de TipoObrigacao disponíveis para vinculação a clientes.
    """
    with get_session() as session:
        registros = (
            session.query(TipoObrigacaoDB)
            .order_by(TipoObrigacaoDB.nome)
            .all()
        )
        return [TipoObrigacao.model_validate(r) for r in registros]


# =============================================================================
# PRAZOS
# =============================================================================

def criar_prazo(dados: PrazoCreate) -> Prazo:
    """
    Registra uma ocorrência de obrigação fiscal para um cliente e competência.

    A combinação (cliente_id, tipo_obrigacao_id, competencia) deve ser única.

    Args:
        dados: PrazoCreate com cliente, tipo de obrigação, competência e vencimento.

    Returns:
        Prazo persistido com id e timestamps.

    Raises:
        PrazoDuplicadoError: se já existir prazo para a mesma combinação.
        ClienteNotFoundError: se o cliente_id não existir.
    """
    agora = datetime.now(timezone.utc)

    with get_session() as session:
        # Valida existência do cliente antes de inserir
        if session.get(ClienteDB, dados.cliente_id) is None:
            raise ClienteNotFoundError(
                f"Cliente id={dados.cliente_id} não encontrado."
            )

        registro = PrazoDB(
            cliente_id=dados.cliente_id,
            tipo_obrigacao_id=dados.tipo_obrigacao_id,
            competencia=dados.competencia,
            data_vencimento=dados.data_vencimento,
            status=dados.status,
            entregue_em=dados.entregue_em,
            observacao=dados.observacao,
            criado_em=agora,
            atualizado_em=agora,
        )
        session.add(registro)
        try:
            session.commit()
            session.refresh(registro)
            logger.info(
                "Prazo criado: id=%s cliente=%s tipo=%s competencia=%r",
                registro.id, dados.cliente_id, dados.tipo_obrigacao_id, dados.competencia,
            )
            return Prazo.model_validate(registro)
        except IntegrityError:
            session.rollback()
            raise PrazoDuplicadoError(
                f"Já existe prazo para cliente_id={dados.cliente_id}, "
                f"tipo_obrigacao_id={dados.tipo_obrigacao_id}, "
                f"competencia='{dados.competencia}'."
            )


def listar_prazos(
    cliente_id: Optional[int] = None,
    tipo_obrigacao_id: Optional[int] = None,
    status: Optional[str] = None,
    competencia: Optional[str] = None,
    apenas_ativos: bool = True,
) -> list[Prazo]:
    """
    Retorna prazos com filtros opcionais combinados.

    Args:
        cliente_id: filtra por cliente específico.
        tipo_obrigacao_id: filtra por tipo de obrigação.
        status: filtra por status ('pendente', 'em_andamento', 'entregue', 'atrasado').
        competencia: filtra por competência no formato AAAA-MM.
        apenas_ativos: se True (padrão), exclui prazos de clientes inativos.

    Returns:
        Lista de Prazo ordenada por data_vencimento ascendente.
    """
    with get_session() as session:
        query = session.query(PrazoDB)

        if apenas_ativos:
            query = query.join(ClienteDB).filter(ClienteDB.ativo == True)  # noqa: E712
        if cliente_id is not None:
            query = query.filter(PrazoDB.cliente_id == cliente_id)
        if tipo_obrigacao_id is not None:
            query = query.filter(PrazoDB.tipo_obrigacao_id == tipo_obrigacao_id)
        if status is not None:
            query = query.filter(PrazoDB.status == status)
        if competencia is not None:
            query = query.filter(PrazoDB.competencia == competencia)

        registros = query.order_by(PrazoDB.data_vencimento).all()
        return [Prazo.model_validate(r) for r in registros]


def buscar_prazo(prazo_id: int) -> Prazo:
    """
    Busca um prazo pelo id.

    Args:
        prazo_id: identificador único do prazo.

    Returns:
        Prazo encontrado.

    Raises:
        PrazoNotFoundError: se nenhum prazo com o id informado existir.
    """
    with get_session() as session:
        registro = session.get(PrazoDB, prazo_id)
        if registro is None:
            raise PrazoNotFoundError(
                f"Prazo id={prazo_id} não encontrado."
            )
        return Prazo.model_validate(registro)


def atualizar_prazo(prazo_id: int, dados: PrazoUpdate) -> Prazo:
    """
    Atualiza parcialmente um prazo existente (PATCH).

    Uso principal: marcar como entregue, adicionar observação ou corrigir status.
    Quando status='entregue' e entregue_em não for informado, preenche com hoje.

    Args:
        prazo_id: identificador único do prazo.
        dados: PrazoUpdate com os campos a alterar.

    Returns:
        Prazo atualizado.

    Raises:
        PrazoNotFoundError: se o prazo não existir.
    """
    with get_session() as session:
        registro = session.get(PrazoDB, prazo_id)
        if registro is None:
            raise PrazoNotFoundError(
                f"Prazo id={prazo_id} não encontrado."
            )

        alteracoes = dados.model_dump(exclude_none=True)

        # Conveniência: se marcar como entregue sem informar a data, usa hoje
        if alteracoes.get("status") == "entregue" and "entregue_em" not in alteracoes:
            alteracoes["entregue_em"] = date.today()

        for campo, valor in alteracoes.items():
            setattr(registro, campo, valor)

        registro.atualizado_em = datetime.now(timezone.utc)
        session.commit()
        session.refresh(registro)
        logger.info("Prazo atualizado: id=%s campos=%s", prazo_id, list(alteracoes))
        return Prazo.model_validate(registro)


def deletar_prazo(prazo_id: int) -> None:
    """
    Remove um prazo do banco permanentemente.

    Uso: correção de lançamento incorreto. Para prazos entregues,
    prefira atualizar o status em vez de deletar.

    Args:
        prazo_id: identificador único do prazo.

    Raises:
        PrazoNotFoundError: se o prazo não existir.
    """
    with get_session() as session:
        registro = session.get(PrazoDB, prazo_id)
        if registro is None:
            raise PrazoNotFoundError(
                f"Prazo id={prazo_id} não encontrado."
            )
        session.delete(registro)
        session.commit()
        logger.info("Prazo deletado: id=%s", prazo_id)
