# =============================================================================
# src/data/models.py — Fiscal Deadlines
# Modelos Pydantic v2 para as três entidades do domínio.
#
# Responsabilidade única: validação e tipagem dos dados.
# Nenhuma lógica de banco, nenhuma lógica de negócio aqui.
#
# Entidades:
#   ClienteCreate / Cliente      — cadastro de clientes da carteira
#   TipoObrigacao                — catálogo fixo de obrigações fiscais
#   PrazoCreate   / Prazo        — ocorrência concreta de uma obrigação
#   PrazoUpdate   / ClienteUpdate — modelos de atualização parcial (PATCH)
#
# Uso:
#   from src.data.models import ClienteCreate, PrazoCreate, PrazoUpdate
# =============================================================================

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from config.settings import REGIMES_TRIBUTARIOS, STATUS_PRAZO, PERIODICIDADES

# =============================================================================
# TIPOS LITERAIS — derivados das constantes de settings
# =============================================================================

RegimeTributario = Literal[
    "Simples Nacional",
    "Lucro Presumido",
    "Lucro Real",
]

StatusPrazo = Literal[
    "pendente",
    "em_andamento",
    "entregue",
    "atrasado",
]

Periodicidade = Literal[
    "mensal",
    "anual",
]

# =============================================================================
# CLIENTE
# =============================================================================

class ClienteCreate(BaseModel):
    """
    Dados necessários para cadastrar um novo cliente na carteira.
    Usado na criação — sem id, sem timestamps.
    """

    nome:               str             = Field(..., min_length=2, max_length=120)
    cnpj:               str             = Field(..., min_length=14, max_length=18)
    regime_tributario:  RegimeTributario
    ativo:              bool            = True

    @field_validator("cnpj")
    @classmethod
    def cnpj_apenas_digitos_ou_formatado(cls, v: str) -> str:
        """Aceita CNPJ cru (14 dígitos) ou formatado (XX.XXX.XXX/XXXX-XX)."""
        digitos = v.replace(".", "").replace("/", "").replace("-", "")
        if not digitos.isdigit() or len(digitos) != 14:
            raise ValueError(
                f"CNPJ inválido: '{v}'. Informe 14 dígitos ou no formato XX.XXX.XXX/XXXX-XX."
            )
        return digitos  # armazena sempre sem formatação


class Cliente(ClienteCreate):
    """
    Cliente já persistido — inclui id e data de criação.
    Retornado pelas queries de leitura.
    """

    id:        int
    criado_em: datetime

    model_config = {"from_attributes": True}


# =============================================================================
# TIPO DE OBRIGAÇÃO
# =============================================================================

class TipoObrigacao(BaseModel):
    """
    Entrada do catálogo fixo de obrigações fiscais (DAS, DCTF, SPED, eSocial).
    Populado na inicialização do banco — o contador não cadastra, apenas seleciona.
    """

    id:              int
    nome:            str          = Field(..., min_length=2, max_length=60)
    periodicidade:   Periodicidade
    dia_vencimento:  int          = Field(..., ge=1, le=31)
    descricao:       Optional[str] = None

    model_config = {"from_attributes": True}


# =============================================================================
# PRAZO
# =============================================================================

class PrazoCreate(BaseModel):
    """
    Dados necessários para registrar uma ocorrência de obrigação fiscal.
    A combinação (cliente_id, tipo_obrigacao_id, competencia) deve ser única.
    """

    cliente_id:         int
    tipo_obrigacao_id:  int
    competencia:        str  = Field(
        ...,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Formato AAAA-MM. Ex: 2025-01",
    )
    data_vencimento:    date
    status:             StatusPrazo = "pendente"
    entregue_em:        Optional[date] = None
    observacao:         Optional[str]  = Field(None, max_length=500)

    @field_validator("entregue_em")
    @classmethod
    def entregue_em_exige_status_entregue(
        cls, v: Optional[date], info
    ) -> Optional[date]:
        """
        Garante consistência: data de entrega só pode existir
        quando o status é 'entregue'.
        """
        status = info.data.get("status")
        if v is not None and status != "entregue":
            raise ValueError(
                "Campo 'entregue_em' só pode ser preenchido quando status='entregue'."
            )
        return v


class Prazo(PrazoCreate):
    """
    Prazo já persistido — inclui id e timestamps de criação e atualização.
    Retornado pelas queries de leitura.
    """

    id:           int
    criado_em:    datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}


# =============================================================================
# MODELOS DE ATUALIZAÇÃO (PATCH)
# Todos os campos opcionais — atualiza só o que foi enviado.
# =============================================================================

class PrazoUpdate(BaseModel):
    """
    Atualização parcial de um prazo existente.
    Usado ao marcar como entregue, adicionar observação ou corrigir status.
    """

    status:       Optional[StatusPrazo] = None
    entregue_em:  Optional[date]        = None
    observacao:   Optional[str]         = Field(None, max_length=500)


class ClienteUpdate(BaseModel):
    """Atualização parcial de um cliente — nome, regime ou flag ativo."""

    nome:              Optional[str]              = Field(None, min_length=2, max_length=120)
    regime_tributario: Optional[RegimeTributario] = None
    ativo:             Optional[bool]             = None
