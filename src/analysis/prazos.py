# =============================================================================
# src/analysis/prazos.py — Fiscal Deadlines
# Lógica pura de cálculo de urgência e classificação de alertas de prazo.
#
# Responsabilidade única: calcular dias restantes, classificar urgência
# e ajustar vencimentos para dias úteis.
# Nenhuma lógica de banco, nenhuma lógica de apresentação aqui.
#
# Funções disponíveis:
#   dias_ate_vencimento    — dias corridos entre hoje e o vencimento
#   classificar_urgencia   — retorna nível de alerta pelo prazo restante
#   prazo_esta_atrasado    — True se vencido sem entrega
#   proximo_dia_util       — ajusta data para o próximo dia útil se cair em FDS
#   calcular_vencimento    — data de vencimento correta para uma competência
#   enriquecer_prazos      — adiciona colunas de análise a um DataFrame de prazos
#
# Uso:
#   from src.analysis.prazos import enriquecer_prazos, classificar_urgencia
# =============================================================================

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

import pandas as pd

from config.settings import (
    ALERTA_ATENCAO_DIAS,
    ALERTA_CRITICO_DIAS,
    COR_ATENCAO,
    COR_ATRASADO,
    COR_ENTREGUE,
    COR_PENDENTE,
    COR_EM_ANDAMENTO,
    PALETTE_STATUS,
)

# =============================================================================
# TIPOS
# =============================================================================

NivelUrgencia = Literal["critico", "atencao", "ok", "entregue"]


# =============================================================================
# FERIADOS NACIONAIS FIXOS (v1)
# Apenas feriados de data fixa — sem cálculo de Páscoa ou Carnaval.
# Expandir para feriados móveis na v2.
# =============================================================================

def _feriados_nacionais(ano: int) -> set[date]:
    """
    Retorna o conjunto de feriados nacionais de data fixa para o ano informado.

    Args:
        ano: ano de referência (ex: 2025).

    Returns:
        Conjunto de datas de feriados fixos.
    """
    return {
        date(ano, 1, 1),   # Confraternização Universal
        date(ano, 4, 21),  # Tiradentes
        date(ano, 5, 1),   # Dia do Trabalho
        date(ano, 9, 7),   # Independência do Brasil
        date(ano, 10, 12), # Nossa Senhora Aparecida
        date(ano, 11, 2),  # Finados
        date(ano, 11, 15), # Proclamação da República
        date(ano, 12, 25), # Natal
    }


# =============================================================================
# DIAS ÚTEIS
# =============================================================================

def proximo_dia_util(data: date) -> date:
    """
    Retorna a data informada se for dia útil, ou avança para o próximo
    dia útil caso caia em sábado, domingo ou feriado nacional fixo.

    Args:
        data: data base a verificar.

    Returns:
        Data ajustada para o próximo dia útil.

    Exemplos:
        >>> proximo_dia_util(date(2025, 1, 1))  # feriado → avança
        date(2025, 1, 2)
        >>> proximo_dia_util(date(2025, 1, 4))  # sábado → avança para segunda
        date(2025, 1, 6)
    """
    feriados = _feriados_nacionais(data.year)
    while data.weekday() >= 5 or data in feriados:  # 5=sábado, 6=domingo
        data += timedelta(days=1)
        # Atualiza feriados se virar ano durante o avanço
        feriados = _feriados_nacionais(data.year)
    return data


def eh_dia_util(data: date) -> bool:
    """
    Verifica se a data é um dia útil (não é FDS nem feriado nacional fixo).

    Args:
        data: data a verificar.

    Returns:
        True se for dia útil, False caso contrário.
    """
    feriados = _feriados_nacionais(data.year)
    return data.weekday() < 5 and data not in feriados


# =============================================================================
# CÁLCULO DE VENCIMENTO
# =============================================================================

def calcular_vencimento(competencia: str, dia_padrao: int) -> date:
    """
    Calcula a data de vencimento real de uma obrigação para uma competência,
    ajustando para o próximo dia útil se o dia padrão cair em FDS ou feriado.

    Args:
        competencia: período no formato AAAA-MM (ex: '2025-01').
        dia_padrao: dia do mês definido para vencimento (ex: 20 para DAS).

    Returns:
        Data de vencimento ajustada para dia útil.

    Raises:
        ValueError: se a competência não estiver no formato AAAA-MM.

    Exemplos:
        >>> calcular_vencimento("2025-01", 20)  # 20/01 é segunda — sem ajuste
        date(2025, 1, 20)
        >>> calcular_vencimento("2025-11", 15)  # 15/11 é feriado — avança
        date(2025, 11, 17)
    """
    try:
        ano, mes = int(competencia[:4]), int(competencia[5:7])
    except (ValueError, IndexError):
        raise ValueError(
            f"Competência inválida: '{competencia}'. Use o formato AAAA-MM."
        )

    # Garante que o dia não ultrapasse o último dia do mês (ex: fevereiro)
    import calendar
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    dia = min(dia_padrao, ultimo_dia)

    data_base = date(ano, mes, dia)
    return proximo_dia_util(data_base)


# =============================================================================
# URGÊNCIA
# =============================================================================

def dias_ate_vencimento(
    data_vencimento: date,
    hoje: date | None = None,
) -> int:
    """
    Calcula os dias corridos entre hoje e o vencimento.

    Valores negativos indicam prazo vencido.

    Args:
        data_vencimento: data limite da obrigação.
        hoje: data de referência (padrão: date.today()).

    Returns:
        Inteiro com os dias restantes (negativo se vencido).
    """
    if hoje is None:
        hoje = date.today()
    return (data_vencimento - hoje).days


def classificar_urgencia(
    data_vencimento: date,
    status: str,
    hoje: date | None = None,
) -> NivelUrgencia:
    """
    Classifica o nível de urgência de um prazo com base nos dias restantes
    e no status atual.

    Níveis:
        'entregue' — obrigação já cumprida (independe do prazo)
        'critico'  — vencido ou vence em até ALERTA_CRITICO_DIAS dias
        'atencao'  — vence entre ALERTA_CRITICO_DIAS+1 e ALERTA_ATENCAO_DIAS dias
        'ok'       — vence em mais de ALERTA_ATENCAO_DIAS dias

    Args:
        data_vencimento: data limite da obrigação.
        status: status atual do prazo.
        hoje: data de referência (padrão: date.today()).

    Returns:
        NivelUrgencia: 'entregue' | 'critico' | 'atencao' | 'ok'.
    """
    if status == "entregue":
        return "entregue"

    dias = dias_ate_vencimento(data_vencimento, hoje)

    if dias <= ALERTA_CRITICO_DIAS:
        return "critico"
    if dias <= ALERTA_ATENCAO_DIAS:
        return "atencao"
    return "ok"


def prazo_esta_atrasado(data_vencimento: date, status: str, hoje: date | None = None) -> bool:
    """
    Retorna True se o prazo está vencido e não foi entregue.

    Usado para sincronizar automaticamente o status 'atrasado'
    no painel sem precisar de atualização manual.

    Args:
        data_vencimento: data limite da obrigação.
        status: status atual do prazo.
        hoje: data de referência (padrão: date.today()).

    Returns:
        True se vencido sem entrega, False caso contrário.
    """
    if status == "entregue":
        return False
    return dias_ate_vencimento(data_vencimento, hoje) < 0


def cor_por_urgencia(urgencia: NivelUrgencia) -> str:
    """
    Retorna a cor do design system correspondente ao nível de urgência.

    Args:
        urgencia: nível calculado por classificar_urgencia().

    Returns:
        Código hexadecimal da cor.
    """
    mapa = {
        "entregue": COR_ENTREGUE,
        "ok":       COR_PENDENTE,
        "atencao":  COR_ATENCAO,
        "critico":  COR_ATRASADO,
    }
    return mapa.get(urgencia, COR_PENDENTE)


# =============================================================================
# ENRIQUECIMENTO DE DATAFRAME
# =============================================================================

def enriquecer_prazos(df: pd.DataFrame, hoje: date | None = None) -> pd.DataFrame:
    """
    Adiciona colunas de análise a um DataFrame de prazos para uso no painel.

    Colunas adicionadas:
        dias_restantes  — int: dias até o vencimento (negativo se vencido)
        urgencia        — str: 'entregue' | 'critico' | 'atencao' | 'ok'
        cor_urgencia    — str: código hex do design system
        atrasado        — bool: True se vencido e não entregue
        label_dias      — str: texto legível ('Hoje', 'Amanhã', '3 dias', 'Vencido há 2 dias')

    Args:
        df: DataFrame com colunas 'data_vencimento' (date) e 'status' (str).
        hoje: data de referência (padrão: date.today()).

    Returns:
        DataFrame original com as novas colunas adicionadas.

    Raises:
        KeyError: se o DataFrame não contiver as colunas obrigatórias.
    """
    colunas_obrigatorias = {"data_vencimento", "status"}
    ausentes = colunas_obrigatorias - set(df.columns)
    if ausentes:
        raise KeyError(
            f"DataFrame não contém as colunas obrigatórias: {ausentes}"
        )

    if df.empty:
        df = df.copy()
        for col in ["dias_restantes", "urgencia", "cor_urgencia", "atrasado", "label_dias"]:
            df[col] = pd.Series(dtype="object")
        return df

    if hoje is None:
        hoje = date.today()

    df = df.copy()

    df["dias_restantes"] = df["data_vencimento"].apply(
        lambda d: dias_ate_vencimento(d, hoje)
    )
    df["urgencia"] = df.apply(
        lambda r: classificar_urgencia(r["data_vencimento"], r["status"], hoje),
        axis=1,
    )
    df["cor_urgencia"] = df["urgencia"].apply(cor_por_urgencia)
    df["atrasado"] = df.apply(
        lambda r: prazo_esta_atrasado(r["data_vencimento"], r["status"], hoje),
        axis=1,
    )
    df["label_dias"] = df.apply(
        lambda r: _label_dias(r["dias_restantes"], r["status"]),
        axis=1,
    )

    return df


def _label_dias(dias: int, status: str) -> str:
    """
    Gera um texto legível para exibição no painel.

    Args:
        dias: dias restantes (pode ser negativo).
        status: status atual do prazo.

    Returns:
        Texto formatado para o usuário final.
    """
    if status == "entregue":
        return "Entregue"
    if status == "em_andamento":
        return "Em andamento"
    if dias < 0:
        qtd = abs(dias)
        return f"Vencido há {qtd} dia{'s' if qtd > 1 else ''}"
    if dias == 0:
        return "Vence hoje"
    if dias == 1:
        return "Vence amanhã"
    return f"{dias} dias"
