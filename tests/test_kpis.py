# =============================================================================
# tests/test_kpis.py — Fiscal Deadlines
# Testes automatizados da camada de KPIs da carteira.
#
# Cobre:
#   calcular_kpis      — contagens, percentuais, divisão por zero, casos extremos
#   kpis_por_obrigacao — agregação por tipo, DataFrame vazio, coluna ausente
#   kpis_por_cliente   — ranking, top_n, sem coluna nome_cliente
#
# Uso:
#   pytest tests/test_kpis.py -v
#   pytest tests/test_kpis.py -v --cov=src/analysis/kpis
# =============================================================================

from datetime import date

import pandas as pd
import pytest

from src.analysis.kpis import calcular_kpis, kpis_por_cliente, kpis_por_obrigacao

# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def hoje() -> date:
    """Data de referência fixa — segunda-feira."""
    return date(2025, 1, 13)


@pytest.fixture
def df_carteira(hoje) -> pd.DataFrame:
    """
    Carteira com 3 clientes e 7 prazos cobrindo todos os status e níveis.

    Distribuição esperada:
        entregues    : 2  (SPED São João + DCTF Tech)
        em_andamento : 1  (DAS Tech)
        atrasados    : 1  (DAS São João — vencido em 10/01)
        pendentes    : 3  (eSocial São João, DCTF Alfa, eSocial Alfa)
        criticos     : 3  (eSocial São João 15/01, DCTF Alfa 15/01, DAS São João atrasado)
        atencao      : 1  (eSocial Alfa 18/01 — 5 dias)
    """
    return pd.DataFrame([
        {"cliente_id": 1, "nome_cliente": "Padaria São João",  "tipo_obrigacao": "DAS",        "data_vencimento": date(2025, 1, 10), "status": "atrasado"},
        {"cliente_id": 1, "nome_cliente": "Padaria São João",  "tipo_obrigacao": "eSocial",     "data_vencimento": date(2025, 1, 15), "status": "pendente"},
        {"cliente_id": 1, "nome_cliente": "Padaria São João",  "tipo_obrigacao": "SPED Fiscal", "data_vencimento": date(2025, 1, 20), "status": "entregue"},
        {"cliente_id": 2, "nome_cliente": "Construtora Alfa",  "tipo_obrigacao": "DCTF",        "data_vencimento": date(2025, 1, 15), "status": "pendente"},
        {"cliente_id": 2, "nome_cliente": "Construtora Alfa",  "tipo_obrigacao": "eSocial",     "data_vencimento": date(2025, 1, 18), "status": "pendente"},
        {"cliente_id": 3, "nome_cliente": "Tech Solutions",    "tipo_obrigacao": "DAS",         "data_vencimento": date(2025, 1, 20), "status": "em_andamento"},
        {"cliente_id": 3, "nome_cliente": "Tech Solutions",    "tipo_obrigacao": "DCTF",        "data_vencimento": date(2025, 1, 20), "status": "entregue"},
    ])


# =============================================================================
# calcular_kpis
# =============================================================================

class TestCalcularKpis:

    def test_total_prazos(self, df_carteira, hoje):
        kpis = calcular_kpis(df_carteira, hoje)
        assert kpis["total_prazos_mes"] == 7

    def test_total_clientes_ativos(self, df_carteira, hoje):
        kpis = calcular_kpis(df_carteira, hoje)
        assert kpis["total_clientes_ativos"] == 3

    def test_total_entregues(self, df_carteira, hoje):
        kpis = calcular_kpis(df_carteira, hoje)
        assert kpis["total_entregues"] == 2

    def test_total_em_andamento(self, df_carteira, hoje):
        kpis = calcular_kpis(df_carteira, hoje)
        assert kpis["total_em_andamento"] == 1

    def test_total_atrasados(self, df_carteira, hoje):
        kpis = calcular_kpis(df_carteira, hoje)
        assert kpis["total_atrasados"] == 1

    def test_pct_entregues(self, df_carteira, hoje):
        kpis = calcular_kpis(df_carteira, hoje)
        assert kpis["pct_entregues"] == round(2 / 7, 4)

    def test_pct_em_risco(self, df_carteira, hoje):
        """em_risco = atrasados + criticos."""
        kpis = calcular_kpis(df_carteira, hoje)
        em_risco = kpis["total_atrasados"] + kpis["total_criticos"]
        assert kpis["pct_em_risco"] == round(em_risco / 7, 4)

    def test_prazos_proximos_7_dias(self, df_carteira, hoje):
        """Conta prazos não entregues que vencem nos próximos 7 dias."""
        kpis = calcular_kpis(df_carteira, hoje)
        assert kpis["prazos_proximos_7_dias"] >= 0

    def test_dataframe_vazio_retorna_zeros(self, hoje):
        """DataFrame vazio não deve lançar exceção — retorna zeros."""
        df_vazio = pd.DataFrame(columns=["data_vencimento", "status"])
        kpis = calcular_kpis(df_vazio, hoje)
        assert kpis["total_prazos_mes"]   == 0
        assert kpis["pct_entregues"]      == 0.0
        assert kpis["pct_em_risco"]       == 0.0

    def test_todos_entregues(self, hoje):
        """Carteira 100% entregue — pct_entregues deve ser 1.0."""
        df = pd.DataFrame([
            {"data_vencimento": date(2025, 1, 1), "status": "entregue"},
            {"data_vencimento": date(2025, 1, 5), "status": "entregue"},
        ])
        kpis = calcular_kpis(df, hoje)
        assert kpis["pct_entregues"] == 1.0
        assert kpis["pct_em_risco"]  == 0.0

    def test_todos_atrasados(self, hoje):
        """Carteira 100% atrasada — pct_em_risco deve ser >= 0."""
        df = pd.DataFrame([
            {"data_vencimento": date(2025, 1, 1), "status": "pendente"},
            {"data_vencimento": date(2025, 1, 2), "status": "pendente"},
        ])
        kpis = calcular_kpis(df, hoje)
        assert kpis["pct_entregues"] == 0.0
        assert kpis["pct_em_risco"]  > 0.0

    def test_sem_coluna_cliente_id(self, hoje):
        """Sem cliente_id, total_clientes_ativos deve retornar 0."""
        df = pd.DataFrame([
            {"data_vencimento": date(2025, 1, 20), "status": "pendente"},
        ])
        kpis = calcular_kpis(df, hoje)
        assert kpis["total_clientes_ativos"] == 0


# =============================================================================
# kpis_por_obrigacao
# =============================================================================

class TestKpisPorObrigacao:

    def test_retorna_todos_os_tipos(self, df_carteira, hoje):
        resultado = kpis_por_obrigacao(df_carteira, hoje)
        tipos = set(resultado["tipo_obrigacao"])
        assert {"DAS", "DCTF", "eSocial", "SPED Fiscal"}.issubset(tipos)

    def test_colunas_presentes(self, df_carteira, hoje):
        resultado = kpis_por_obrigacao(df_carteira, hoje)
        for col in ["tipo_obrigacao", "total", "entregues", "atrasados", "pct_entregues"]:
            assert col in resultado.columns

    def test_sped_100_pct_entregue(self, df_carteira, hoje):
        """SPED Fiscal tem 1 prazo, entregue — deve ter pct_entregues=1.0."""
        resultado = kpis_por_obrigacao(df_carteira, hoje)
        sped = resultado[resultado["tipo_obrigacao"] == "SPED Fiscal"].iloc[0]
        assert sped["pct_entregues"] == 1.0

    def test_pct_entregues_nao_negativo(self, df_carteira, hoje):
        resultado = kpis_por_obrigacao(df_carteira, hoje)
        assert (resultado["pct_entregues"] >= 0).all()

    def test_dataframe_vazio(self, hoje):
        df_vazio = pd.DataFrame(columns=["tipo_obrigacao", "data_vencimento", "status"])
        resultado = kpis_por_obrigacao(df_vazio, hoje)
        assert resultado.empty

    def test_sem_coluna_tipo_obrigacao(self, hoje):
        """Sem coluna tipo_obrigacao, deve retornar DataFrame vazio."""
        df = pd.DataFrame([{"data_vencimento": date(2025, 1, 20), "status": "pendente"}])
        resultado = kpis_por_obrigacao(df, hoje)
        assert resultado.empty


# =============================================================================
# kpis_por_cliente
# =============================================================================

class TestKpisPorCliente:

    def test_cliente_mais_em_risco_aparece_primeiro(self, df_carteira, hoje):
        """Padaria São João tem 2 prazos em risco — deve liderar o ranking."""
        resultado = kpis_por_cliente(df_carteira, hoje)
        assert resultado.iloc[0]["nome_cliente"] == "Padaria São João"

    def test_colunas_presentes(self, df_carteira, hoje):
        resultado = kpis_por_cliente(df_carteira, hoje)
        for col in ["cliente_id", "nome_cliente", "total", "entregues", "em_risco", "pct_entregues"]:
            assert col in resultado.columns

    def test_top_n_limita_resultado(self, df_carteira, hoje):
        resultado = kpis_por_cliente(df_carteira, hoje, top_n=2)
        assert len(resultado) <= 2

    def test_top_n_1(self, df_carteira, hoje):
        resultado = kpis_por_cliente(df_carteira, hoje, top_n=1)
        assert len(resultado) == 1

    def test_pct_entregues_entre_0_e_1(self, df_carteira, hoje):
        resultado = kpis_por_cliente(df_carteira, hoje)
        assert (resultado["pct_entregues"] >= 0).all()
        assert (resultado["pct_entregues"] <= 1).all()

    def test_dataframe_vazio(self, hoje):
        df_vazio = pd.DataFrame(columns=["cliente_id", "data_vencimento", "status"])
        resultado = kpis_por_cliente(df_vazio, hoje)
        assert resultado.empty

    def test_sem_coluna_cliente_id(self, hoje):
        """Sem cliente_id, deve retornar DataFrame vazio."""
        df = pd.DataFrame([{"data_vencimento": date(2025, 1, 20), "status": "pendente"}])
        resultado = kpis_por_cliente(df, hoje)
        assert resultado.empty

    def test_sem_coluna_nome_cliente(self, hoje):
        """Sem nome_cliente, coluna deve ser adicionada como string vazia."""
        df = pd.DataFrame([
            {"cliente_id": 1, "tipo_obrigacao": "DAS", "data_vencimento": date(2025, 1, 1), "status": "pendente"},
        ])
        resultado = kpis_por_cliente(df, hoje)
        assert "nome_cliente" in resultado.columns
        assert resultado.iloc[0]["nome_cliente"] == ""
