# =============================================================================
# tests/test_prazos.py — Fiscal Deadlines
# Testes automatizados da camada de análise de prazos.
#
# Cobre:
#   proximo_dia_util   — FDS, feriados fixos, dia útil normal, virada de ano
#   calcular_vencimento — dia inexistente no mês, feriado, sábado, normal
#   dias_ate_vencimento — hoje, futuro, passado
#   classificar_urgencia — todos os níveis + entregue ignora prazo
#   prazo_esta_atrasado — combinações status x vencimento
#   _label_dias         — singular, plural, casos especiais
#   enriquecer_prazos   — colunas geradas, DataFrame vazio, coluna ausente
#
# Uso:
#   pytest tests/test_prazos.py -v
#   pytest tests/test_prazos.py -v --cov=src/analysis/prazos
# =============================================================================

from datetime import date

import pandas as pd
import pytest

from src.analysis.prazos import (
    _label_dias,
    calcular_vencimento,
    classificar_urgencia,
    dias_ate_vencimento,
    enriquecer_prazos,
    prazo_esta_atrasado,
    proximo_dia_util,
)

# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def hoje() -> date:
    """Data de referência fixa para todos os testes — segunda-feira."""
    return date(2025, 1, 13)


@pytest.fixture
def df_prazos_base(hoje) -> pd.DataFrame:
    """DataFrame com um prazo por nível de urgência + um entregue."""
    return pd.DataFrame([
        {"data_vencimento": date(2025, 1, 10), "status": "atrasado"},    # vencido
        {"data_vencimento": date(2025, 1, 15), "status": "pendente"},    # critico (2 dias)
        {"data_vencimento": date(2025, 1, 18), "status": "pendente"},    # atencao (5 dias)
        {"data_vencimento": date(2025, 2,  1), "status": "pendente"},    # ok (19 dias)
        {"data_vencimento": date(2025, 1, 10), "status": "entregue"},    # entregue
    ])


# =============================================================================
# proximo_dia_util
# =============================================================================

class TestProximoDiaUtil:

    def test_feriado_confraternizacao_avanca(self):
        """01/01 é feriado — deve avançar para o próximo dia útil."""
        resultado = proximo_dia_util(date(2025, 1, 1))
        assert resultado == date(2025, 1, 2)

    def test_sabado_avanca_para_segunda(self):
        """Sábado deve avançar dois dias para segunda-feira."""
        resultado = proximo_dia_util(date(2025, 1, 4))   # sábado
        assert resultado == date(2025, 1, 6)              # segunda

    def test_domingo_avanca_para_segunda(self):
        """Domingo deve avançar um dia para segunda-feira."""
        resultado = proximo_dia_util(date(2025, 1, 5))   # domingo
        assert resultado == date(2025, 1, 6)              # segunda

    def test_dia_util_sem_ajuste(self):
        """Dia útil normal não deve ser alterado."""
        resultado = proximo_dia_util(date(2025, 1, 13))  # segunda-feira
        assert resultado == date(2025, 1, 13)

    def test_feriado_proclamacao_republica(self):
        """15/11 (Proclamação da República) cai em sábado em 2025 — avança para segunda."""
        resultado = proximo_dia_util(date(2025, 11, 15))
        assert resultado == date(2025, 11, 17)

    def test_feriado_natal(self):
        """25/12 é feriado nacional — deve sempre avançar para o próximo dia útil."""
        resultado = proximo_dia_util(date(2025, 12, 25))  # quinta-feira em 2025
        assert resultado == date(2025, 12, 26)             # sexta — próximo dia útil

    def test_feriado_seguido_de_fds(self):
        """01/01/2023 é domingo — deve avançar para 02/01 (segunda)."""
        resultado = proximo_dia_util(date(2023, 1, 1))
        assert resultado == date(2023, 1, 2)

    def test_virada_de_mes(self):
        """Último dia do mês em FDS deve avançar para o mês seguinte."""
        resultado = proximo_dia_util(date(2025, 3, 29))  # sábado
        assert resultado == date(2025, 3, 31)             # segunda


# =============================================================================
# calcular_vencimento
# =============================================================================

class TestCalcularVencimento:

    def test_vencimento_normal(self):
        """DAS de janeiro — dia 20 é segunda, sem ajuste."""
        resultado = calcular_vencimento("2025-01", 20)
        assert resultado == date(2025, 1, 20)

    def test_vencimento_feriado_avanca(self):
        """SPED de novembro — dia 15 é feriado, avança para 17."""
        resultado = calcular_vencimento("2025-11", 15)
        assert resultado == date(2025, 11, 17)

    def test_dia_inexistente_fevereiro(self):
        """Dia 30 em fevereiro — deve usar o último dia do mês."""
        resultado = calcular_vencimento("2025-02", 30)
        assert resultado.month == 2
        assert resultado.day <= 28

    def test_dia_31_em_mes_de_30_dias(self):
        """Dia 31 em abril (30 dias) — deve usar o último dia do mês."""
        resultado = calcular_vencimento("2025-04", 31)
        assert resultado.month == 4
        assert resultado.day <= 30

    def test_competencia_invalida_levanta_erro(self):
        """Competência fora do formato AAAA-MM deve lançar ValueError."""
        with pytest.raises(ValueError, match="Competência inválida"):
            calcular_vencimento("01-2025", 20)

    def test_competencia_vazia_levanta_erro(self):
        """Competência vazia deve lançar ValueError."""
        with pytest.raises(ValueError):
            calcular_vencimento("", 20)

    def test_vencimento_sabado_avanca(self):
        """Vencimento que cai em sábado deve ser ajustado para segunda."""
        # 15/03/2025 é sábado
        resultado = calcular_vencimento("2025-03", 15)
        assert resultado == date(2025, 3, 17)  # segunda


# =============================================================================
# dias_ate_vencimento
# =============================================================================

class TestDiasAteVencimento:

    def test_vencimento_hoje(self, hoje):
        assert dias_ate_vencimento(hoje, hoje) == 0

    def test_vencimento_amanha(self, hoje):
        amanha = date(2025, 1, 14)
        assert dias_ate_vencimento(amanha, hoje) == 1

    def test_vencimento_ontem(self, hoje):
        ontem = date(2025, 1, 12)
        assert dias_ate_vencimento(ontem, hoje) == -1

    def test_vencimento_futuro_distante(self, hoje):
        futuro = date(2025, 2, 1)
        assert dias_ate_vencimento(futuro, hoje) == 19

    def test_vencimento_passado_distante(self, hoje):
        passado = date(2024, 12, 31)
        assert dias_ate_vencimento(passado, hoje) == -13


# =============================================================================
# classificar_urgencia
# =============================================================================

class TestClassificarUrgencia:

    def test_status_entregue_sempre_retorna_entregue(self, hoje):
        """Prazo entregue deve retornar 'entregue' independente da data."""
        # Entregue com prazo já vencido
        assert classificar_urgencia(date(2025, 1, 1), "entregue", hoje) == "entregue"
        # Entregue com prazo futuro
        assert classificar_urgencia(date(2025, 2, 1), "entregue", hoje) == "entregue"

    def test_vencido_retorna_critico(self, hoje):
        """Prazo vencido e não entregue deve retornar 'critico'."""
        assert classificar_urgencia(date(2025, 1, 10), "pendente", hoje) == "critico"

    def test_vence_hoje_retorna_critico(self, hoje):
        """Prazo que vence hoje deve retornar 'critico'."""
        assert classificar_urgencia(hoje, "pendente", hoje) == "critico"

    def test_vence_em_3_dias_retorna_critico(self, hoje):
        """Prazo que vence no limiar crítico (3 dias) deve retornar 'critico'."""
        assert classificar_urgencia(date(2025, 1, 16), "pendente", hoje) == "critico"

    def test_vence_em_4_dias_retorna_atencao(self, hoje):
        """Logo após o limiar crítico deve retornar 'atencao'."""
        assert classificar_urgencia(date(2025, 1, 17), "pendente", hoje) == "atencao"

    def test_vence_em_7_dias_retorna_atencao(self, hoje):
        """Prazo no limiar de atenção (7 dias) deve retornar 'atencao'."""
        assert classificar_urgencia(date(2025, 1, 20), "pendente", hoje) == "atencao"

    def test_vence_em_8_dias_retorna_ok(self, hoje):
        """Logo após o limiar de atenção deve retornar 'ok'."""
        assert classificar_urgencia(date(2025, 1, 21), "pendente", hoje) == "ok"

    def test_vence_em_andamento_critico(self, hoje):
        """Status em_andamento não protege do nível crítico."""
        assert classificar_urgencia(date(2025, 1, 14), "em_andamento", hoje) == "critico"


# =============================================================================
# prazo_esta_atrasado
# =============================================================================

class TestPrazoEstaAtrasado:

    def test_vencido_pendente_retorna_true(self, hoje):
        assert prazo_esta_atrasado(date(2025, 1, 12), "pendente", hoje) is True

    def test_vencido_entregue_retorna_false(self, hoje):
        """Prazo vencido mas entregue não é considerado atrasado."""
        assert prazo_esta_atrasado(date(2025, 1, 12), "entregue", hoje) is False

    def test_vencido_em_andamento_retorna_true(self, hoje):
        """Em andamento mas vencido ainda é atrasado."""
        assert prazo_esta_atrasado(date(2025, 1, 12), "em_andamento", hoje) is True

    def test_futuro_pendente_retorna_false(self, hoje):
        assert prazo_esta_atrasado(date(2025, 1, 20), "pendente", hoje) is False

    def test_vence_hoje_nao_e_atrasado(self, hoje):
        """Prazo que vence hoje ainda não está atrasado."""
        assert prazo_esta_atrasado(hoje, "pendente", hoje) is False


# =============================================================================
# _label_dias
# =============================================================================

class TestLabelDias:

    def test_vence_hoje(self):
        assert _label_dias(0, "pendente") == "Vence hoje"

    def test_vence_amanha(self):
        assert _label_dias(1, "pendente") == "Vence amanhã"

    def test_vence_em_dias(self):
        assert _label_dias(5, "pendente") == "5 dias"

    def test_vencido_ha_1_dia_singular(self):
        assert _label_dias(-1, "pendente") == "Vencido há 1 dia"

    def test_vencido_ha_3_dias_plural(self):
        assert _label_dias(-3, "pendente") == "Vencido há 3 dias"

    def test_status_entregue(self):
        assert _label_dias(10, "entregue") == "Entregue"

    def test_status_em_andamento(self):
        assert _label_dias(10, "em_andamento") == "Em andamento"

    def test_status_entregue_vencido(self):
        """Mesmo vencido, se status for entregue, label deve ser 'Entregue'."""
        assert _label_dias(-5, "entregue") == "Entregue"


# =============================================================================
# enriquecer_prazos
# =============================================================================

class TestEnriquecerPrazos:

    def test_colunas_geradas(self, df_prazos_base, hoje):
        """Deve gerar todas as colunas de análise esperadas."""
        df = enriquecer_prazos(df_prazos_base, hoje)
        for col in ["dias_restantes", "urgencia", "cor_urgencia", "atrasado", "label_dias"]:
            assert col in df.columns, f"Coluna ausente: {col}"

    def test_urgencias_corretas(self, df_prazos_base, hoje):
        df = enriquecer_prazos(df_prazos_base, hoje)
        assert list(df["urgencia"]) == ["critico", "critico", "atencao", "ok", "entregue"]

    def test_atrasados_corretos(self, df_prazos_base, hoje):
        df = enriquecer_prazos(df_prazos_base, hoje)
        assert list(df["atrasado"]) == [True, False, False, False, False]

    def test_nao_modifica_original(self, df_prazos_base, hoje):
        """enriquecer_prazos não deve alterar o DataFrame original."""
        colunas_antes = set(df_prazos_base.columns)
        enriquecer_prazos(df_prazos_base, hoje)
        assert set(df_prazos_base.columns) == colunas_antes

    def test_dataframe_vazio_sem_excecao(self, hoje):
        """DataFrame vazio deve retornar sem lançar exceção."""
        df_vazio = pd.DataFrame(columns=["data_vencimento", "status"])
        resultado = enriquecer_prazos(df_vazio, hoje)
        assert resultado.empty

    def test_coluna_ausente_levanta_keyerror(self, hoje):
        """DataFrame sem coluna obrigatória deve lançar KeyError."""
        df_invalido = pd.DataFrame([{"data_vencimento": date(2025, 1, 1)}])
        with pytest.raises(KeyError):
            enriquecer_prazos(df_invalido, hoje)

    def test_todos_entregues(self, hoje):
        """DataFrame onde todos os prazos estão entregues."""
        df = pd.DataFrame([
            {"data_vencimento": date(2025, 1, 1), "status": "entregue"},
            {"data_vencimento": date(2025, 1, 5), "status": "entregue"},
        ])
        resultado = enriquecer_prazos(df, hoje)
        assert all(resultado["urgencia"] == "entregue")
        assert not any(resultado["atrasado"])
