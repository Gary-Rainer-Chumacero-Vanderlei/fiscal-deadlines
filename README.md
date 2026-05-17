# Fiscal Deadlines — Painel de Controle de Prazos Fiscais
### Escritório de Contabilidade · Jan/2026 – Dez/2026

> Projeto de portfólio de tecnologia contábil com dados sintéticos,
> pipeline end-to-end e painel interativo em Streamlit com banco de dados persistido.

---

## O Problema

Todo mês, o contador de um escritório de pequeno porte repete o mesmo ritual de risco: abre a planilha de controle, verifica manualmente quais obrigações vencem nos próximos dias, envia lembretes por WhatsApp para os clientes e torce para não ter esquecido nenhuma entrega. Quando um prazo escapa — e ele escapa — a consequência é imediata: multa para o cliente, desgaste na relação e, muitas vezes, absorção do custo pelo próprio escritório para não perder o contrato.

O problema não é falta de conhecimento técnico. **É falta de visibilidade.** Com uma carteira de 20, 30 ou 50 clientes em regimes tributários diferentes, nenhuma planilha responde em segundos: *quais obrigações vencem esta semana? Quais estão atrasadas? Quem ainda não entregou os documentos?*

**Este projeto resolve esse problema:** um painel interno que centraliza todos os clientes e suas obrigações fiscais em um único lugar, com alertas automáticos de vencimento, controle de status por obrigação e visão consolidada da carteira — eliminando o risco de prazo esquecido e o retrabalho do controle manual.

---

## Visão Geral

Este projeto simula o ambiente operacional de um escritório de contabilidade de pequeno porte, cobrindo desde a geração dos dados até a entrega de um painel interativo com CRUD completo e banco de dados persistido. O objetivo é demonstrar boas práticas de engenharia de software aplicadas ao domínio contábil-fiscal, com separação de camadas, validação de dados, testes automatizados e lógica de negócio pura e testável.

**Stack principal:** Python 3.11+ · Pandas · SQLAlchemy · SQLite · Pydantic v2 · Streamlit · Plotly · pytest

---

## Demonstração

O painel é dividido em três páginas:

| Página | Conteúdo |
|---|---|
| 📋 Painel | KPIs da carteira, alertas por urgência, progresso por obrigação, ranking de clientes em risco |
| 📅 Prazos | Tabela com filtros combinados, atualização de status inline, destaque visual por urgência |
| 👥 Clientes | Cadastro com validação de CNPJ, regime tributário, controle de ativo/inativo |

Todos os filtros de período operam sobre competências no formato `AAAA-MM`,
eliminando ambiguidade entre meses de anos diferentes.

---

## Arquitetura do Projeto

```
fiscal-deadlines/
│
├── config/
│   └── settings.py               ← design system, enums, constantes e caminhos
│
├── src/                          ← código-fonte principal (sem dependência do Streamlit)
│   ├── data/
│   │   ├── models.py             ← Pydantic v2: Cliente, TipoObrigacao, Prazo
│   │   ├── database.py           ← SQLAlchemy: tabelas, engine, init_db()
│   │   └── loader.py             ← CRUD completo com exceções customizadas
│   ├── analysis/
│   │   ├── prazos.py             ← lógica pura: urgência, dias úteis, vencimentos
│   │   └── kpis.py               ← KPIs da carteira: totais, percentuais, rankings
│   └── visualization/
│       └── charts.py             ← gráficos Plotly reutilizáveis (v2)
│
├── tests/                        ← 108 testes automatizados com pytest
│   ├── test_prazos.py            ← urgência, dias úteis, classificação, enriquecimento
│   ├── test_kpis.py              ← contagens, percentuais, rankings, casos de borda
│   └── test_loader.py            ← CRUD, schema, exceções, isolamento por teste
│
├── data/                         ← banco SQLite gerado em execução (ignorado pelo Git)
├── App.py                        ← ponto de entrada: streamlit run App.py
├── gerar_dados.py                ← dados sintéticos reprodutíveis (seed=42)
├── conftest.py                   ← resolve sys.path para pytest e Streamlit
├── requirements.txt              ← dependências de produção (versões fixadas)
└── requirements-dev.txt          ← dependências de desenvolvimento
```

---

## Instalação e Execução

### 1. Clone o repositório

```bash
git clone https://github.com/Gary-Rainer-Chumacero-Vanderlei/fiscal-deadlines.git
cd fiscal-deadlines
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Gere os dados sintéticos

```bash
python gerar_dados.py
```

Cria 12 clientes fictícios e 360 prazos para o ano de 2026 no banco SQLite:
- `data/fiscal.db` — banco com tabelas `cliente`, `tipo_obrigacao` e `prazo`

Para um ano específico:

```bash
python gerar_dados.py --ano 2027
```

> O banco é ignorado pelo Git (`.gitignore`). Qualquer pessoa que clone o repositório
> recria os mesmos dados executando este comando — `seed=42` garante reprodutibilidade.

### 5. Execute o painel

```bash
streamlit run App.py
```

### 6. Execute os testes

```bash
# Instala dependências de desenvolvimento
pip install -r requirements-dev.txt

# Todos os testes
pytest tests/ -v

# Com cobertura
pytest tests/ -v --cov=src --cov-report=term-missing
```

**Resultado esperado:** `108 passed in < 5s`

---

## Dataset Sintético

Os dados são gerados por `gerar_dados.py` com as seguintes características:

### Clientes

| Parâmetro | Valor |
|---|---|
| Total de clientes | 12 |
| Simples Nacional | 6 clientes |
| Lucro Presumido | 4 clientes |
| Lucro Real | 2 clientes |

### Prazos

| Parâmetro | Valor |
|---|---|
| Período coberto | Janeiro a Dezembro de 2026 |
| Total de prazos gerados | 360 |
| Prazos entregues | 72 (20%) |
| Prazos atrasados | 72 (20%) |
| Seed de reprodutibilidade | 42 |

### Distribuição de Status por Período

| Competência | Distribuição |
|---|---|
| Meses passados (> 1 mês atrás) | 75% entregue · 25% atrasado |
| Mês atual e anterior | 45% pendente · 35% em andamento · 20% atrasado |
| Meses futuros | 80% pendente · 20% em andamento |

### Obrigações Fiscais Cobertas (v1)

| Obrigação | Periodicidade | Vencimento padrão | Regime |
|---|---|---|---|
| DAS | Mensal | Dia 20 | Simples Nacional |
| DCTF | Mensal | Dia 15 | Lucro Presumido / Real |
| SPED Fiscal | Mensal | Dia 15 | Lucro Presumido / Real |
| eSocial | Mensal | Dia 7 | Todos com funcionários |

> Vencimentos são ajustados automaticamente para o próximo dia útil quando
> caem em fim de semana ou feriado nacional fixo.

---

## Testes

```bash
# Instala dependências de desenvolvimento
pip install -r requirements-dev.txt

# Executa todos os 108 testes
pytest tests/ -v

# Com relatório de cobertura de linhas
pytest tests/ --cov=src --cov-report=term-missing
```

**Resultado esperado:** `108 passed in < 5s`

---

## Estrutura de Testes

```
108 testes · 3 arquivos · < 5 segundos

test_prazos.py  (43 testes)
  ├── proximo_dia_util — FDS, feriados fixos, virada de ano
  ├── calcular_vencimento — dia inexistente no mês, feriado, sábado
  ├── dias_ate_vencimento — hoje, futuro, passado
  ├── classificar_urgencia — todos os níveis + entregue ignora prazo
  ├── prazo_esta_atrasado — combinações status x vencimento
  ├── _label_dias — singular, plural, casos especiais
  └── enriquecer_prazos — colunas geradas, DataFrame vazio, coluna ausente

test_kpis.py  (27 testes)
  ├── calcular_kpis — contagens, percentuais, divisão por zero, casos extremos
  ├── kpis_por_obrigacao — agregação por tipo, DataFrame vazio, coluna ausente
  └── kpis_por_cliente — ranking, top_n, sem coluna nome_cliente

test_loader.py  (38 testes)
  ├── criar_cliente — sucesso, CNPJ duplicado, validação Pydantic
  ├── listar_clientes — filtro ativo/inativo, ordenação por nome
  ├── buscar/atualizar_cliente — PATCH parcial, cliente inexistente
  ├── listar_tipos_obrigacao — catálogo fixo com 4 obrigações
  ├── criar_prazo — sucesso, duplicado, cliente inexistente
  ├── listar/buscar_prazo — filtros combinados, não encontrado
  └── atualizar/deletar_prazo — entregue_em automático, exceções
```

---

## Boas Práticas Aplicadas

### Separação de responsabilidades
`src/` não importa Streamlit — pode ser usado em qualquer contexto (scripts, notebooks, APIs). O `App.py` consome `src/` sem recalcular nada. `src/data/` não conhece `src/analysis/` — cada camada tem uma única direção de dependência.

### Modelos tipados com Pydantic v2
`ClienteCreate`, `PrazoCreate` e `PrazoUpdate` validam os dados antes de chegarem ao banco. O CNPJ é normalizado automaticamente (remove pontuação), a competência é validada com regex `AAAA-MM`, e a consistência entre `status` e `entregue_em` é garantida no modelo — não no banco.

### Exceções customizadas
`ClienteNotFoundError`, `PrazoNotFoundError` e `PrazoDuplicadoError` permitem que o dashboard capture erros específicos e exiba mensagens acionáveis ao usuário — sem tratar `Exception` genérica.

### Testes isolados por banco
O fixture `banco_limpo` em `test_loader.py` recria todas as tabelas antes de cada teste com `autouse=True`. Nenhum teste depende de outro — a ordem de execução não afeta o resultado.

### Funções puras e testáveis
Todas as funções de `prazos.py` e `kpis.py` recebem dados como argumento e retornam resultados — sem estado global, sem efeitos colaterais. O parâmetro `hoje: date | None` permite fixar a data de referência nos testes sem depender de `date.today()`.

### Reprodutibilidade
`random.Random(seed=42)` instanciado localmente em `gerar_dados.py` — não afeta nem é afetado por outros módulos. Qualquer pessoa que clone o repositório recria os 360 prazos exatos executando um único comando.

### Resolução de sys.path
`conftest.py` na raiz do projeto garante que a raiz esteja sempre no `sys.path`, independente de onde o processo é iniciado. Quando o Streamlit executa `App.py`, ele adiciona apenas a pasta raiz ao path — sem este arquivo, `from src.data.loader import ...` falharia com `ModuleNotFoundError`. O arquivo é carregado automaticamente pelo pytest antes de qualquer teste.

---

## Tecnologias e Versões

| Biblioteca | Versão | Uso |
|---|---|---|
| Python | 3.11+ | Linguagem principal |
| Streamlit | 1.41.1 | Painel interativo |
| Plotly | 5.24.1 | Gráficos interativos |
| Pandas | 2.2.3 | Manipulação de dados |
| SQLAlchemy | 2.0.36 | ORM e abstração do banco |
| Alembic | 1.14.0 | Migrações de schema |
| Pydantic | 2.10.3 | Validação e tipagem dos modelos |
| python-dateutil | 2.9.0 | Cálculo de datas e vencimentos |
| pytest | 8.3.5 | Testes automatizados |
| pytest-cov | 6.0.0 | Cobertura de testes |
| mypy | 1.11.2 | Verificação de tipos |
| pandas-stubs | 2.2.3.240807 | Stubs de tipo para pandas |

---

## Autor

Desenvolvido como projeto de portfólio em Tecnologia Contábil / Análise de Dados.

Contato: [LinkedIn](https://www.linkedin.com/in/garyrainercv/) · [GitHub](https://github.com/gary-rainer-chumacero-vanderlei)
