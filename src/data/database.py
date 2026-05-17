# =============================================================================
# src/data/database.py — Fiscal Deadlines
# Definição das tabelas SQLAlchemy e inicialização do banco SQLite.
#
# Responsabilidade única: estrutura do banco e sessão de conexão.
# Nenhuma lógica de negócio, nenhuma lógica de análise aqui.
#
# Tabelas:
#   ClienteDB        — cadastro de clientes da carteira
#   TipoObrigacaoDB  — catálogo fixo de obrigações fiscais
#   PrazoDB          — ocorrências concretas por cliente e competência
#
# Uso:
#   from src.data.database import get_session, init_db
#   init_db()   # cria tabelas e popula catálogo de obrigações
# =============================================================================

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship

from config.settings import DATABASE_URL, DATA_DIR, OBRIGACOES_V1

logger = logging.getLogger(__name__)

# =============================================================================
# ENGINE
# =============================================================================

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # necessário para SQLite + Streamlit
    echo=False,
)

# Habilita foreign keys no SQLite (desativadas por padrão)
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# =============================================================================
# BASE E MIXIN DE TIMESTAMPS
# =============================================================================

class Base(DeclarativeBase):
    pass


def _agora() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# TABELAS
# =============================================================================

class ClienteDB(Base):
    """
    Cadastro de clientes da carteira do escritório.
    Fonte de verdade para nome, CNPJ e regime tributário.
    """

    __tablename__ = "cliente"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    nome              = Column(String(120), nullable=False)
    cnpj              = Column(String(14), nullable=False, unique=True)
    regime_tributario = Column(String(30), nullable=False)
    ativo             = Column(Boolean, nullable=False, default=True)
    criado_em         = Column(DateTime, nullable=False, default=_agora)

    prazos = relationship("PrazoDB", back_populates="cliente", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Cliente id={self.id} nome={self.nome!r} regime={self.regime_tributario!r}>"


class TipoObrigacaoDB(Base):
    """
    Catálogo fixo de obrigações fiscais.
    Populado uma única vez em init_db() — o contador seleciona, não cadastra.
    """

    __tablename__ = "tipo_obrigacao"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    nome           = Column(String(60), nullable=False, unique=True)
    periodicidade  = Column(String(20), nullable=False)
    dia_vencimento = Column(Integer, nullable=False)
    descricao      = Column(Text, nullable=True)

    prazos = relationship("PrazoDB", back_populates="tipo_obrigacao")

    def __repr__(self) -> str:
        return f"<TipoObrigacao id={self.id} nome={self.nome!r}>"


class PrazoDB(Base):
    """
    Ocorrência concreta de uma obrigação fiscal para um cliente em uma competência.
    É a entidade central do sistema — cada linha representa uma entrega rastreável.

    A constraint única em (cliente_id, tipo_obrigacao_id, competencia) garante
    que não existam dois DAS de janeiro para o mesmo cliente.
    """

    __tablename__ = "prazo"

    __table_args__ = (
        UniqueConstraint(
            "cliente_id", "tipo_obrigacao_id", "competencia",
            name="uq_prazo_cliente_tipo_competencia",
        ),
    )

    id                = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id        = Column(Integer, ForeignKey("cliente.id", ondelete="CASCADE"), nullable=False)
    tipo_obrigacao_id = Column(Integer, ForeignKey("tipo_obrigacao.id"), nullable=False)
    competencia       = Column(String(7), nullable=False)   # formato AAAA-MM
    data_vencimento   = Column(Date, nullable=False)
    status            = Column(String(20), nullable=False, default="pendente")
    entregue_em       = Column(Date, nullable=True)
    observacao        = Column(Text, nullable=True)
    criado_em         = Column(DateTime, nullable=False, default=_agora)
    atualizado_em     = Column(DateTime, nullable=False, default=_agora, onupdate=_agora)

    cliente        = relationship("ClienteDB", back_populates="prazos")
    tipo_obrigacao = relationship("TipoObrigacaoDB", back_populates="prazos")

    def __repr__(self) -> str:
        return (
            f"<Prazo id={self.id} cliente_id={self.cliente_id} "
            f"tipo={self.tipo_obrigacao_id} competencia={self.competencia!r} "
            f"status={self.status!r}>"
        )


# =============================================================================
# SESSÃO
# =============================================================================

def get_session() -> Session:
    """
    Retorna uma sessão SQLAlchemy para uso manual.
    Prefira usar como context manager:

        with get_session() as session:
            ...

    A sessão faz commit automático ao sair do bloco sem exceção,
    e rollback em caso de erro.
    """
    return Session(engine)


# =============================================================================
# INICIALIZAÇÃO
# =============================================================================

def init_db() -> None:
    """
    Cria as tabelas no banco (se não existirem) e popula o catálogo
    de obrigações fiscais com os dados de OBRIGACOES_V1.

    Idempotente — pode ser chamada múltiplas vezes sem duplicar dados.
    """
    DATA_DIR.mkdir(exist_ok=True)
    Base.metadata.create_all(engine)
    logger.info("  ✓ Tabelas criadas/verificadas em %s", DATABASE_URL)

    _seed_tipo_obrigacao()


def _seed_tipo_obrigacao() -> None:
    """
    Popula o catálogo de tipos de obrigação com os dados de OBRIGACOES_V1.
    Ignora silenciosamente se o registro já existir (idempotente por nome).
    """
    with get_session() as session:
        existentes = {r.nome for r in session.query(TipoObrigacaoDB).all()}

        novos = [
            TipoObrigacaoDB(**obr)
            for obr in OBRIGACOES_V1
            if obr["nome"] not in existentes
        ]

        if novos:
            session.add_all(novos)
            session.commit()
            for n in novos:
                logger.info("  ✓ Obrigação inserida: %s", n.nome)
        else:
            logger.info("  · Catálogo de obrigações já populado — nenhuma inserção.")
