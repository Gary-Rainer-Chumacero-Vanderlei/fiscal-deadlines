# =============================================================================
# tests/test_loader.py — Fiscal Deadlines
# Testes automatizados da camada de acesso ao banco de dados (CRUD).
#
# Cobre:
#   criar_cliente      — sucesso, CNPJ duplicado, validação Pydantic
#   listar_clientes    — filtro ativo/inativo, ordenação por nome
#   buscar_cliente     — encontrado, não encontrado
#   atualizar_cliente  — PATCH parcial, cliente inexistente
#   listar_tipos       — catálogo fixo populado
#   criar_prazo        — sucesso, duplicado, cliente inexistente
#   listar_prazos      — filtros combinados
#   buscar_prazo       — encontrado, não encontrado
#   atualizar_prazo    — PATCH, entregue_em automático
#   deletar_prazo      — sucesso, não encontrado
#
# Uso:
#   pytest tests/test_loader.py -v
#   pytest tests/test_loader.py -v --cov=src/data/loader
# =============================================================================

from datetime import date

import pytest

from src.data.database import Base, engine, init_db
from src.data.loader import (
    ClienteNotFoundError,
    PrazoDuplicadoError,
    PrazoNotFoundError,
    atualizar_cliente,
    atualizar_prazo,
    buscar_cliente,
    buscar_prazo,
    criar_cliente,
    criar_prazo,
    deletar_prazo,
    listar_clientes,
    listar_prazos,
    listar_tipos_obrigacao,
)
from src.data.models import (
    ClienteCreate,
    ClienteUpdate,
    PrazoCreate,
    PrazoUpdate,
)

# =============================================================================
# SETUP — banco isolado por teste
# =============================================================================

@pytest.fixture(autouse=True)
def banco_limpo():
    """
    Recria todas as tabelas antes de cada teste.
    Garante isolamento total — nenhum teste depende de outro.
    """
    Base.metadata.drop_all(engine)
    init_db()
    yield
    Base.metadata.drop_all(engine)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def cliente_padaria():
    return ClienteCreate(
        nome="Padaria São João",
        cnpj="11222333000181",
        regime_tributario="Simples Nacional",
    )


@pytest.fixture
def cliente_construtora():
    return ClienteCreate(
        nome="Construtora Alfa",
        cnpj="22333444000192",
        regime_tributario="Lucro Presumido",
    )


@pytest.fixture
def cliente_criado(cliente_padaria):
    return criar_cliente(cliente_padaria)


@pytest.fixture
def tipo_das():
    """Retorna o TipoObrigacao DAS do catálogo."""
    tipos = listar_tipos_obrigacao()
    return next(t for t in tipos if t.nome == "DAS")


@pytest.fixture
def prazo_criado(cliente_criado, tipo_das):
    return criar_prazo(PrazoCreate(
        cliente_id=cliente_criado.id,
        tipo_obrigacao_id=tipo_das.id,
        competencia="2025-01",
        data_vencimento=date(2025, 1, 20),
        status="pendente",
    ))


# =============================================================================
# CLIENTES — criar
# =============================================================================

class TestCriarCliente:

    def test_cria_com_sucesso(self, cliente_padaria):
        cliente = criar_cliente(cliente_padaria)
        assert cliente.id is not None
        assert cliente.nome == "Padaria São João"
        assert cliente.cnpj == "11222333000181"
        assert cliente.ativo is True

    def test_cnpj_normalizado(self):
        """CNPJ formatado deve ser armazenado sem pontuação."""
        cliente = criar_cliente(ClienteCreate(
            nome="Empresa X",
            cnpj="11.222.333/0001-81",
            regime_tributario="Simples Nacional",
        ))
        assert cliente.cnpj == "11222333000181"

    def test_cnpj_duplicado_levanta_erro(self, cliente_padaria):
        criar_cliente(cliente_padaria)
        with pytest.raises(PrazoDuplicadoError, match="CNPJ"):
            criar_cliente(cliente_padaria)

    def test_cnpj_invalido_levanta_erro(self):
        with pytest.raises(Exception):
            criar_cliente(ClienteCreate(
                nome="Empresa Y",
                cnpj="123",
                regime_tributario="Simples Nacional",
            ))

    def test_regime_invalido_levanta_erro(self):
        with pytest.raises(Exception):
            criar_cliente(ClienteCreate(
                nome="Empresa Z",
                cnpj="11222333000181",
                regime_tributario="Regime Inexistente",
            ))


# =============================================================================
# CLIENTES — listar
# =============================================================================

class TestListarClientes:

    def test_retorna_clientes_ativos(self, cliente_padaria, cliente_construtora):
        criar_cliente(cliente_padaria)
        criar_cliente(cliente_construtora)
        lista = listar_clientes(apenas_ativos=True)
        assert len(lista) == 2

    def test_exclui_clientes_inativos(self, cliente_padaria):
        cliente = criar_cliente(cliente_padaria)
        atualizar_cliente(cliente.id, ClienteUpdate(ativo=False))
        lista = listar_clientes(apenas_ativos=True)
        assert len(lista) == 0

    def test_inclui_inativos_quando_solicitado(self, cliente_padaria):
        cliente = criar_cliente(cliente_padaria)
        atualizar_cliente(cliente.id, ClienteUpdate(ativo=False))
        lista = listar_clientes(apenas_ativos=False)
        assert len(lista) == 1

    def test_ordenado_por_nome(self, cliente_padaria, cliente_construtora):
        criar_cliente(cliente_padaria)    # "Padaria..."
        criar_cliente(cliente_construtora)  # "Construtora..."
        lista = listar_clientes()
        assert lista[0].nome == "Construtora Alfa"
        assert lista[1].nome == "Padaria São João"

    def test_lista_vazia_sem_excecao(self):
        lista = listar_clientes()
        assert lista == []


# =============================================================================
# CLIENTES — buscar e atualizar
# =============================================================================

class TestBuscarAtualizarCliente:

    def test_busca_por_id(self, cliente_criado):
        encontrado = buscar_cliente(cliente_criado.id)
        assert encontrado.id == cliente_criado.id
        assert encontrado.nome == cliente_criado.nome

    def test_nao_encontrado_levanta_erro(self):
        with pytest.raises(ClienteNotFoundError):
            buscar_cliente(9999)

    def test_atualiza_nome(self, cliente_criado):
        atualizado = atualizar_cliente(cliente_criado.id, ClienteUpdate(nome="Novo Nome"))
        assert atualizado.nome == "Novo Nome"
        assert atualizado.regime_tributario == cliente_criado.regime_tributario

    def test_atualiza_apenas_campo_enviado(self, cliente_criado):
        """PATCH parcial — campos não enviados permanecem inalterados."""
        atualizado = atualizar_cliente(cliente_criado.id, ClienteUpdate(ativo=False))
        assert atualizado.ativo is False
        assert atualizado.nome == cliente_criado.nome

    def test_atualiza_cliente_inexistente_levanta_erro(self):
        with pytest.raises(ClienteNotFoundError):
            atualizar_cliente(9999, ClienteUpdate(nome="Nome Valido"))


# =============================================================================
# TIPOS DE OBRIGAÇÃO
# =============================================================================

class TestListarTiposObrigacao:

    def test_retorna_4_tipos(self):
        tipos = listar_tipos_obrigacao()
        assert len(tipos) == 4

    def test_contem_obrigacoes_esperadas(self):
        nomes = {t.nome for t in listar_tipos_obrigacao()}
        assert nomes == {"DAS", "DCTF", "SPED Fiscal", "eSocial"}

    def test_ordenado_por_nome(self):
        nomes = [t.nome for t in listar_tipos_obrigacao()]
        assert nomes == sorted(nomes)


# =============================================================================
# PRAZOS — criar
# =============================================================================

class TestCriarPrazo:

    def test_cria_com_sucesso(self, prazo_criado):
        assert prazo_criado.id is not None
        assert prazo_criado.competencia == "2025-01"
        assert prazo_criado.status == "pendente"

    def test_duplicado_levanta_erro(self, cliente_criado, tipo_das):
        dados = PrazoCreate(
            cliente_id=cliente_criado.id,
            tipo_obrigacao_id=tipo_das.id,
            competencia="2025-01",
            data_vencimento=date(2025, 1, 20),
        )
        criar_prazo(dados)
        with pytest.raises(PrazoDuplicadoError):
            criar_prazo(dados)

    def test_cliente_inexistente_levanta_erro(self, tipo_das):
        with pytest.raises(ClienteNotFoundError):
            criar_prazo(PrazoCreate(
                cliente_id=9999,
                tipo_obrigacao_id=tipo_das.id,
                competencia="2025-01",
                data_vencimento=date(2025, 1, 20),
            ))

    def test_mesma_obrigacao_competencias_diferentes(self, cliente_criado, tipo_das):
        """Mesmo cliente e obrigação em competências distintas são permitidos."""
        p1 = criar_prazo(PrazoCreate(
            cliente_id=cliente_criado.id,
            tipo_obrigacao_id=tipo_das.id,
            competencia="2025-01",
            data_vencimento=date(2025, 1, 20),
        ))
        p2 = criar_prazo(PrazoCreate(
            cliente_id=cliente_criado.id,
            tipo_obrigacao_id=tipo_das.id,
            competencia="2025-02",
            data_vencimento=date(2025, 2, 20),
        ))
        assert p1.id != p2.id


# =============================================================================
# PRAZOS — listar e buscar
# =============================================================================

class TestListarBuscarPrazo:

    def test_listar_por_cliente(self, cliente_criado, prazo_criado):
        prazos = listar_prazos(cliente_id=cliente_criado.id)
        assert len(prazos) == 1
        assert prazos[0].id == prazo_criado.id

    def test_listar_por_status(self, prazo_criado):
        prazos_pendentes  = listar_prazos(status="pendente")
        prazos_entregues  = listar_prazos(status="entregue")
        assert len(prazos_pendentes) == 1
        assert len(prazos_entregues) == 0

    def test_listar_por_competencia(self, prazo_criado):
        prazos = listar_prazos(competencia="2025-01")
        assert len(prazos) == 1
        prazos_outro = listar_prazos(competencia="2025-02")
        assert len(prazos_outro) == 0

    def test_listar_vazio_sem_excecao(self):
        prazos = listar_prazos()
        assert prazos == []

    def test_buscar_por_id(self, prazo_criado):
        encontrado = buscar_prazo(prazo_criado.id)
        assert encontrado.id == prazo_criado.id

    def test_buscar_nao_encontrado(self):
        with pytest.raises(PrazoNotFoundError):
            buscar_prazo(9999)


# =============================================================================
# PRAZOS — atualizar e deletar
# =============================================================================

class TestAtualizarDeletarPrazo:

    def test_atualiza_status(self, prazo_criado):
        atualizado = atualizar_prazo(prazo_criado.id, PrazoUpdate(status="em_andamento"))
        assert atualizado.status == "em_andamento"

    def test_marca_entregue_preenche_data_automaticamente(self, prazo_criado):
        """Ao marcar como entregue sem informar a data, deve preencher com hoje."""
        atualizado = atualizar_prazo(prazo_criado.id, PrazoUpdate(status="entregue"))
        assert atualizado.status == "entregue"
        assert atualizado.entregue_em is not None

    def test_atualiza_apenas_campo_enviado(self, prazo_criado):
        """PATCH parcial — campos não enviados permanecem inalterados."""
        atualizado = atualizar_prazo(
            prazo_criado.id,
            PrazoUpdate(observacao="Aguardando retorno do cliente"),
        )
        assert atualizado.observacao == "Aguardando retorno do cliente"
        assert atualizado.status == prazo_criado.status

    def test_atualiza_prazo_inexistente_levanta_erro(self):
        with pytest.raises(PrazoNotFoundError):
            atualizar_prazo(9999, PrazoUpdate(status="entregue"))

    def test_deleta_prazo(self, prazo_criado):
        deletar_prazo(prazo_criado.id)
        with pytest.raises(PrazoNotFoundError):
            buscar_prazo(prazo_criado.id)

    def test_deleta_prazo_inexistente_levanta_erro(self):
        with pytest.raises(PrazoNotFoundError):
            deletar_prazo(9999)
