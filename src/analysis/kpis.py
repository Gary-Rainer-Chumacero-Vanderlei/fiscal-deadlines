# =============================================================================
# src/analysis/kpis.py — Fiscal Deadlines
# Cálculo dos KPIs da carteira para exibição nos cards do painel.
#
# Responsabilidade única: agregar métricas a partir de um DataFrame de prazos.
# Nenhuma lógica de banco, nenhuma lógica de apresentação aqui.
#
# Funções disponíveis:
#   calcular_kpis          — retorna dict com todos os KPIs do painel
#   kpis_por_obrigacao     — resumo por tipo de obrigação (DAS, DCTF, etc.)
#   kpis_por_cliente       — ranking de clientes com mais prazos em risco
#
# Uso:
#   from src.analysis.kpis import calcular_kpis
# =============================================================================

from __future__ import annotations

from datetime import date
from typing import TypedDict

import pandas as pd

from src.analysis.prazos import enriquecer_prazos

# =============================================================================
# TIPOS
# =============================================================================

class KpisCarteira(TypedDict):
    """Estrutura de KPIs retornada por calcular_kpis()."""

    # Totais gerais
    total_clientes_ativos:  int
    total_prazos_mes:       int

    # Por status
    total_entregues:        int
    total_pendentes:        int
    total_em_andamento:     int
    total_atrasados:        int
    total_criticos:         int   # vence em até 3 dias (não entregues)
    total_atencao:          int   # vence entre 4 e 7 dias

    # Percentuais — 0.0 a 1.0 (retornam 0.0 se não houver prazos)
    pct_entregues:          float
    pct_em_risco:           float  # atrasados + criticos / total

    # Alerta principal do painel
    prazos_proximos_7_dias: int   # não entregues que vencem nos próximos 7 dias


# =============================================================================
# KPIs DA CARTEIRA
# =============================================================================

def calcular_kpis(
    df: pd.DataFrame,
    hoje: date | None = None,
) -> KpisCarteira:
    """
    Calcula os KPIs da carteira a partir de um DataFrame de prazos.

    Recebe o DataFrame bruto (sem enriquecimento) e aplica enriquecer_prazos()
    internamente — o chamador não precisa pré-processar.

    Args:
        df: DataFrame com colunas 'data_vencimento', 'status' e
            opcionalmente 'cliente_id'.
        hoje: data de referência (padrão: date.today()).

    Returns:
        KpisCarteira com todos os indicadores do painel.

    Raises:
        KeyError: se o DataFrame não contiver as colunas obrigatórias.
    """
    if hoje is None:
        hoje = date.today()

    # Caso sem dados — retorna zeros sem lançar exceção
    if df.empty:
        return _kpis_zerados()

    df = enriquecer_prazos(df, hoje)

    total = len(df)

    # --- contagens por status ---
    total_entregues    = int((df["status"] == "entregue").sum())
    total_em_andamento = int((df["status"] == "em_andamento").sum())
    total_atrasados    = int(df["atrasado"].sum())

    # pendentes = tudo que não é entregue, em_andamento nem atrasado
    total_pendentes = int(
        ((df["status"] == "pendente") & (~df["atrasado"])).sum()
    )

    # --- contagens por urgência ---
    total_criticos = int((df["urgencia"] == "critico").sum())
    total_atencao  = int((df["urgencia"] == "atencao").sum())

    # --- clientes únicos ---
    total_clientes_ativos = (
        int(df["cliente_id"].nunique())
        if "cliente_id" in df.columns
        else 0
    )

    # --- percentuais — protegidos contra divisão por zero ---
    pct_entregues = total_entregues / total if total > 0 else 0.0
    em_risco      = total_atrasados + total_criticos
    pct_em_risco  = em_risco / total if total > 0 else 0.0

    # --- alerta principal: vence nos próximos 7 dias (não entregues) ---
    prazos_proximos_7_dias = int(
        (
            (df["dias_restantes"] >= 0) &
            (df["dias_restantes"] <= 7) &
            (df["status"] != "entregue")
        ).sum()
    )

    return KpisCarteira(
        total_clientes_ativos=total_clientes_ativos,
        total_prazos_mes=total,
        total_entregues=total_entregues,
        total_pendentes=total_pendentes,
        total_em_andamento=total_em_andamento,
        total_atrasados=total_atrasados,
        total_criticos=total_criticos,
        total_atencao=total_atencao,
        pct_entregues=round(pct_entregues, 4),
        pct_em_risco=round(pct_em_risco, 4),
        prazos_proximos_7_dias=prazos_proximos_7_dias,
    )


def _kpis_zerados() -> KpisCarteira:
    """Retorna KpisCarteira com todos os valores zerados — usado quando o DataFrame está vazio."""
    return KpisCarteira(
        total_clientes_ativos=0,
        total_prazos_mes=0,
        total_entregues=0,
        total_pendentes=0,
        total_em_andamento=0,
        total_atrasados=0,
        total_criticos=0,
        total_atencao=0,
        pct_entregues=0.0,
        pct_em_risco=0.0,
        prazos_proximos_7_dias=0,
    )


# =============================================================================
# KPIs POR OBRIGAÇÃO
# =============================================================================

def kpis_por_obrigacao(
    df: pd.DataFrame,
    hoje: date | None = None,
) -> pd.DataFrame:
    """
    Retorna um resumo agregado por tipo de obrigação.

    Requer colunas 'tipo_obrigacao' (nome), 'data_vencimento' e 'status'.

    Args:
        df: DataFrame de prazos com coluna 'tipo_obrigacao'.
        hoje: data de referência (padrão: date.today()).

    Returns:
        DataFrame com colunas:
            tipo_obrigacao | total | entregues | atrasados | pct_entregues
        Ordenado por total descrescente.
    """
    if df.empty or "tipo_obrigacao" not in df.columns:
        return pd.DataFrame(
            columns=["tipo_obrigacao", "total", "entregues", "atrasados", "pct_entregues"]
        )

    if hoje is None:
        hoje = date.today()

    df = enriquecer_prazos(df, hoje)

    resumo = (
        df.groupby("tipo_obrigacao")
        .agg(
            total=("status", "count"),
            entregues=("status", lambda s: (s == "entregue").sum()),
            atrasados=("atrasado", "sum"),
        )
        .reset_index()
    )

    # Percentual de entregues — protegido contra divisão por zero
    resumo["pct_entregues"] = resumo.apply(
        lambda r: round(r["entregues"] / r["total"], 4) if r["total"] > 0 else 0.0,
        axis=1,
    )

    return resumo.sort_values("total", ascending=False).reset_index(drop=True)


# =============================================================================
# KPIs POR CLIENTE
# =============================================================================

def kpis_por_cliente(
    df: pd.DataFrame,
    hoje: date | None = None,
    top_n: int = 10,
) -> pd.DataFrame:
    """
    Retorna o ranking de clientes com mais prazos em risco (atrasados + críticos).

    Requer colunas 'cliente_id', 'nome_cliente' (opcional),
    'data_vencimento' e 'status'.

    Args:
        df: DataFrame de prazos.
        hoje: data de referência (padrão: date.today()).
        top_n: número máximo de clientes no ranking (padrão: 10).

    Returns:
        DataFrame com colunas:
            cliente_id | nome_cliente | total | entregues | em_risco | pct_entregues
        Ordenado por em_risco descrescente.
    """
    if df.empty or "cliente_id" not in df.columns:
        return pd.DataFrame(
            columns=["cliente_id", "nome_cliente", "total", "entregues", "em_risco", "pct_entregues"]
        )

    if hoje is None:
        hoje = date.today()

    df = enriquecer_prazos(df, hoje)

    # Define colunas de agrupamento — nome_cliente é opcional
    group_cols = ["cliente_id"]
    if "nome_cliente" in df.columns:
        group_cols.append("nome_cliente")

    resumo = (
        df.groupby(group_cols)
        .agg(
            total=("status", "count"),
            entregues=("status", lambda s: (s == "entregue").sum()),
            em_risco=("urgencia", lambda u: ((u == "critico") | (u == "atrasado")).sum()),
        )
        .reset_index()
    )

    resumo["pct_entregues"] = resumo.apply(
        lambda r: round(r["entregues"] / r["total"], 4) if r["total"] > 0 else 0.0,
        axis=1,
    )

    # Adiciona nome_cliente vazio se não existia no DataFrame original
    if "nome_cliente" not in resumo.columns:
        resumo["nome_cliente"] = ""

    return (
        resumo
        .sort_values("em_risco", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
