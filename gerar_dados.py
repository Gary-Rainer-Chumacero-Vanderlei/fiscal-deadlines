# =============================================================================
# gerar_dados.py — Fiscal Deadlines
# Script de geração de dados sintéticos reprodutíveis para demonstração.
#
# Popula o banco com clientes fictícios e prazos distribuídos ao longo
# do ano de referência, cobrindo todos os status e níveis de urgência.
#
# Características:
#   - Reprodutível via SEED_DADOS (seed=42 em settings.py)
#   - Idempotente — limpa e recria os dados a cada execução
#   - Cobre os 3 regimes tributários e as 4 obrigações da v1
#   - Distribui status de forma realista (entregues, pendentes, atrasados)
#
# Uso:
#   python gerar_dados.py              # popula com ANO_BASE de settings.py
#   python gerar_dados.py --ano 2024   # popula para ano específico
# =============================================================================

from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import date

from sqlalchemy import text

from config.settings import ANO_BASE, SEED_DADOS
from src.data.database import init_db
from src.data.loader import criar_cliente, criar_prazo, listar_tipos_obrigacao
from src.data.models import ClienteCreate, PrazoCreate
from src.analysis.prazos import calcular_vencimento
from src.data.database import engine

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# =============================================================================
# CLIENTES FICTÍCIOS
# Nomes e CNPJs gerados para fins de demonstração — não representam
# empresas reais. CNPJs não passam em validação da Receita Federal.
# =============================================================================

CLIENTES_FICTICIOS = [
    {"nome": "Padaria Pão Quente Ltda",         "cnpj": "11111111000101", "regime": "Simples Nacional"},
    {"nome": "Salão Beleza & Arte ME",           "cnpj": "22222222000102", "regime": "Simples Nacional"},
    {"nome": "Mercadinho Bom Preço Ltda",        "cnpj": "33333333000103", "regime": "Simples Nacional"},
    {"nome": "Oficina do João Reparos ME",       "cnpj": "44444444000104", "regime": "Simples Nacional"},
    {"nome": "Pet Shop Amigo Fiel Ltda",         "cnpj": "55555555000105", "regime": "Simples Nacional"},
    {"nome": "Farmácia Saúde Total ME",          "cnpj": "66666666000106", "regime": "Simples Nacional"},
    {"nome": "Construtora Alfa Engenharia Ltda", "cnpj": "77777777000107", "regime": "Lucro Presumido"},
    {"nome": "Clínica Médica Bem Estar S/S",     "cnpj": "88888888000108", "regime": "Lucro Presumido"},
    {"nome": "Transportadora Veloz Ltda",        "cnpj": "99999999000109", "regime": "Lucro Presumido"},
    {"nome": "Distribuidora Norte Sul Ltda",     "cnpj": "10101010000110", "regime": "Lucro Presumido"},
    {"nome": "Tech Solutions Brasil Ltda",       "cnpj": "12121212000111", "regime": "Lucro Real"},
    {"nome": "Indústria Metalúrgica Sul SA",     "cnpj": "13131313000112", "regime": "Lucro Real"},
]

OBRIGACOES_POR_REGIME: dict[str, list[str]] = {
    "Simples Nacional": ["DAS", "eSocial"],
    "Lucro Presumido":  ["DCTF", "SPED Fiscal", "eSocial"],
    "Lucro Real":       ["DCTF", "SPED Fiscal", "eSocial"],
}

PESOS_STATUS_PASSADO  = {"entregue": 0.75, "atrasado": 0.25}
PESOS_STATUS_PRESENTE = {"pendente": 0.45, "em_andamento": 0.35, "atrasado": 0.20}
PESOS_STATUS_FUTURO   = {"pendente": 0.80, "em_andamento": 0.20}


def _sortear_status(competencia_mes: int, mes_atual: int, rng: random.Random) -> str:
    if competencia_mes < mes_atual - 1:
        pesos = PESOS_STATUS_PASSADO
    elif competencia_mes <= mes_atual:
        pesos = PESOS_STATUS_PRESENTE
    else:
        pesos = PESOS_STATUS_FUTURO
    return rng.choices(list(pesos.keys()), weights=list(pesos.values()), k=1)[0]


def limpar_banco() -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM prazo"))
        conn.execute(text("DELETE FROM cliente"))
    logger.info("  . Banco limpo (prazos e clientes removidos)")


def gerar(ano: int = ANO_BASE) -> None:
    rng     = random.Random(SEED_DADOS)
    hoje    = date.today()
    mes_ref = hoje.month if hoje.year == ano else 12

    logger.info("\n%s", "=" * 60)
    logger.info("  Fiscal Deadlines — Geracao de Dados Sinteticos")
    logger.info("  Ano: %d | Seed: %d", ano, SEED_DADOS)
    logger.info("%s\n", "=" * 60)

    init_db()
    limpar_banco()

    tipos        = {t.nome: t for t in listar_tipos_obrigacao()}
    total_prazos = 0

    logger.info("  Criando clientes...")
    clientes_criados = []
    for dados in CLIENTES_FICTICIOS:
        cliente = criar_cliente(ClienteCreate(
            nome=dados["nome"],
            cnpj=dados["cnpj"],
            regime_tributario=dados["regime"],
        ))
        clientes_criados.append((cliente, dados["regime"]))
        logger.info("    + %-40s [%s]", cliente.nome, dados["regime"])

    logger.info("\n  Gerando prazos para %d...", ano)
    for mes in range(1, 13):
        competencia = f"{ano}-{mes:02d}"
        for cliente, regime in clientes_criados:
            for nome_obr in OBRIGACOES_POR_REGIME.get(regime, []):
                tipo = tipos.get(nome_obr)
                if tipo is None:
                    continue
                data_vencimento = calcular_vencimento(competencia, tipo.dia_vencimento)
                status          = _sortear_status(mes, mes_ref, rng)
                entregue_em     = data_vencimento if status == "entregue" else None
                criar_prazo(PrazoCreate(
                    cliente_id=cliente.id,
                    tipo_obrigacao_id=tipo.id,
                    competencia=competencia,
                    data_vencimento=data_vencimento,
                    status=status,
                    entregue_em=entregue_em,
                ))
                total_prazos += 1

    logger.info("\n%s", "=" * 60)
    logger.info("  Concluido com sucesso!")
    logger.info("  Clientes criados : %d", len(clientes_criados))
    logger.info("  Prazos gerados   : %d", total_prazos)
    logger.info("  Seed utilizado   : %d", SEED_DADOS)
    logger.info("%s\n", "=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera dados sinteticos reprodutiveis para o Fiscal Deadlines."
    )
    parser.add_argument(
        "--ano", type=int, default=ANO_BASE,
        help=f"Ano de referencia para os prazos (padrao: {ANO_BASE})",
    )
    args = parser.parse_args()
    try:
        gerar(ano=args.ano)
    except Exception as exc:
        logger.error("Erro durante a geracao: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
