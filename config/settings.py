# =============================================================================
# config/settings.py — Fiscal Deadlines
# Constantes centralizadas do projeto.
#
# Todas as cores, caminhos, enums e parâmetros de negócio vivem aqui.
# Nenhum outro módulo deve definir constantes de configuração próprias.
#
# Uso:
#   from config.settings import PALETTE_STATUS, ALERTA_CRITICO_DIAS
# =============================================================================

from __future__ import annotations

from pathlib import Path

# =============================================================================
# CAMINHOS
# =============================================================================

ROOT_DIR = Path(__file__).parent.parent

# No Streamlit Cloud o único diretório gravável é /tmp.
# Em ambiente local usa data/ na raiz do projeto.
_STREAMLIT_CLOUD = Path("/mount/src").exists()
if _STREAMLIT_CLOUD:
    DATA_DIR = Path("/tmp/fiscal-deadlines")
else:
    DATA_DIR = ROOT_DIR / "data"

DB_PATH = DATA_DIR / "fiscal.db"

# =============================================================================
# BANCO DE DADOS
# =============================================================================

DATABASE_URL = f"sqlite:///{DB_PATH}"

# =============================================================================
# ENUMS DE NEGÓCIO
# =============================================================================

REGIMES_TRIBUTARIOS = [
    "Simples Nacional",
    "Lucro Presumido",
    "Lucro Real",
]

STATUS_PRAZO = [
    "pendente",
    "em_andamento",
    "entregue",
    "atrasado",
]

PERIODICIDADES = [
    "mensal",
    "anual",
]

# =============================================================================
# CATÁLOGO DE OBRIGAÇÕES (v1)
# Populado uma única vez na inicialização do banco.
# dia_vencimento = dia padrão do mês; ajuste de dia útil é feito em prazos.py
# =============================================================================

OBRIGACOES_V1 = [
    {
        "nome":            "DAS",
        "periodicidade":   "mensal",
        "dia_vencimento":  20,
        "descricao":       (
            "Documento de Arrecadação do Simples Nacional. "
            "Vence todo dia 20 do mês seguinte à competência."
        ),
    },
    {
        "nome":            "DCTF",
        "periodicidade":   "mensal",
        "dia_vencimento":  15,
        "descricao":       (
            "Declaração de Débitos e Créditos Tributários Federais. "
            "Vence todo dia 15 do segundo mês após a competência."
        ),
    },
    {
        "nome":            "SPED Fiscal",
        "periodicidade":   "mensal",
        "dia_vencimento":  15,
        "descricao":       (
            "Escrituração Fiscal Digital — ICMS/IPI. "
            "Vence todo dia 15 do mês seguinte à competência."
        ),
    },
    {
        "nome":            "eSocial",
        "periodicidade":   "mensal",
        "dia_vencimento":  7,
        "descricao":       (
            "Sistema de escrituração digital das obrigações fiscais, "
            "previdenciárias e trabalhistas. Vence dia 7 (optantes) "
            "ou dia 20 (demais empresas)."
        ),
    },
]

# =============================================================================
# ALERTAS DE PRAZO
# Limiares em dias para classificação de urgência no painel.
# =============================================================================

ALERTA_CRITICO_DIAS  = 3   # vermelho — vence em até 3 dias ou já venceu
ALERTA_ATENCAO_DIAS  = 7   # âmbar   — vence entre 4 e 7 dias
ALERTA_OK_DIAS       = 999 # verde   — vence em mais de 7 dias

# =============================================================================
# DESIGN SYSTEM
# Mesmo padrão semântico dos projetos anteriores.
# Verde = positivo/entregue | Âmbar = atenção | Vermelho = risco/atrasado
# =============================================================================

COR_ENTREGUE     = "#1D9E75"   # teal-400  — entregue no prazo
COR_PENDENTE     = "#378ADD"   # blue-400  — dentro do prazo, aguardando
COR_ATENCAO      = "#EF9F27"   # amber-400 — vence em breve
COR_ATRASADO     = "#E24B4A"   # red-400   — vencido sem entrega
COR_EM_ANDAMENTO = "#7F77DD"   # purple-400 — em processamento

PALETTE_STATUS = {
    "entregue":     COR_ENTREGUE,
    "pendente":     COR_PENDENTE,
    "em_andamento": COR_EM_ANDAMENTO,
    "atrasado":     COR_ATRASADO,
}

# Fundo e texto — dark theme para gráficos Plotly
BG      = "#0f1923"
BG2     = "#162030"
GRID    = "#1e2d3d"
TEXT    = "#c8d6e5"
MUTED   = "#4a6278"

# =============================================================================
# GERAÇÃO DE DADOS SINTÉTICOS
# =============================================================================

SEED_DADOS = 42
ANO_BASE   = 2026   # ano de referência para geração de prazos sintéticos
