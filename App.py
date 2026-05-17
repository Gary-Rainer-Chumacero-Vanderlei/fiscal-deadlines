# =============================================================================
# App.py — Fiscal Deadlines
# Interface principal do painel de controle de prazos fiscais.
#
# Responsabilidade única: apresentação e interação com o usuário.
# Toda lógica de negócio e acesso ao banco vivem em src/.
#
# Páginas:
#   Painel        — visão geral da carteira com KPIs e alertas
#   Prazos        — tabela completa com filtros e atualização de status
#   Clientes      — cadastro e gestão da carteira
#
# Uso:
#   streamlit run App.py
# =============================================================================

from __future__ import annotations

import sys
from pathlib import Path

# Garante que src/ e config/ são encontrados independente de onde o app é rodado
_ROOT = Path(__file__).parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from datetime import date

import pandas as pd
import streamlit as st

from config.settings import (
    COR_ATRASADO,
    COR_ATENCAO,
    COR_ENTREGUE,
    COR_PENDENTE,
    COR_EM_ANDAMENTO,
    PALETTE_STATUS,
    REGIMES_TRIBUTARIOS,
    STATUS_PRAZO,
)
from src.analysis.kpis import calcular_kpis, kpis_por_cliente, kpis_por_obrigacao
from src.analysis.prazos import enriquecer_prazos
from src.data.database import init_db
from src.data.loader import (
    ClienteNotFoundError,
    PrazoDuplicadoError,
    atualizar_cliente,
    atualizar_prazo,
    buscar_cliente,
    criar_cliente,
    listar_clientes,
    listar_prazos,
    listar_tipos_obrigacao,
)
from src.data.models import ClienteCreate, ClienteUpdate, PrazoUpdate
from src.analysis.prazos import calcular_vencimento

# =============================================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================================

st.set_page_config(
    page_title="Fiscal Deadlines",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# ESTILOS CUSTOMIZADOS
# Complementa o design system de settings.py com ajustes visuais do Streamlit.
# =============================================================================

st.markdown("""
<style>
    /* --- Tipografia e base --- */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    /* --- Cards de KPI --- */
    .kpi-card {
        background: #0d1b2a;
        border: 1px solid #1e2d3d;
        border-radius: 8px;
        padding: 1.1rem 1.25rem;
        min-height: 90px;
    }
    .kpi-label {
        font-size: 11px;
        font-weight: 500;
        letter-spacing: .08em;
        text-transform: uppercase;
        color: #4a6278;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 28px;
        font-weight: 500;
        line-height: 1;
        color: #c8d6e5;
    }
    .kpi-value.critico  { color: #E24B4A; }
    .kpi-value.atencao  { color: #EF9F27; }
    .kpi-value.positivo { color: #1D9E75; }
    .kpi-sub {
        font-size: 11px;
        color: #4a6278;
        margin-top: 4px;
    }

    /* --- Badges de status --- */
    .badge {
        display: inline-block;
        font-size: 11px;
        font-weight: 500;
        padding: 2px 8px;
        border-radius: 20px;
        letter-spacing: .03em;
    }
    .badge-entregue     { background: #0d2b1f; color: #1D9E75; }
    .badge-pendente     { background: #0d1e2e; color: #378ADD; }
    .badge-em_andamento { background: #1a1730; color: #7F77DD; }
    .badge-atrasado     { background: #2b0d0d; color: #E24B4A; }

    /* --- Linha de alerta --- */
    .alerta-row {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 12px;
        border-radius: 6px;
        margin-bottom: 6px;
        font-size: 13px;
    }
    .alerta-critico { background: #1a0a0a; border-left: 3px solid #E24B4A; }
    .alerta-atencao { background: #1a1200; border-left: 3px solid #EF9F27; }
    .alerta-nome    { color: #c8d6e5; font-weight: 500; flex: 1; }
    .alerta-obr     { color: #4a6278; font-size: 12px; }
    .alerta-dias    { font-family: 'IBM Plex Mono', monospace; font-size: 12px; }

    /* --- Sidebar --- */
    [data-testid="stSidebar"] {
        background: #0a1520;
        border-right: 1px solid #1e2d3d;
    }

    /* --- Caption sidebar --- */
    .sidebar-caption { font-size: 11px; color: #4a5068; line-height: 1.6; }

    /* --- Header da página --- */
    .page-header {
        border-bottom: 1px solid #1e2d3d;
        padding-bottom: 12px;
        margin-bottom: 24px;
    }
    .page-title {
        font-size: 20px;
        font-weight: 600;
        color: #c8d6e5;
        margin: 0;
    }
    .page-sub {
        font-size: 13px;
        color: #4a6278;
        margin-top: 2px;
    }

    /* --- Ajustes gerais Streamlit --- */
    .stDataFrame { border: 1px solid #1e2d3d; border-radius: 8px; }
    div[data-testid="stMetric"] { background: transparent; }
    .stSelectbox label, .stTextInput label { font-size: 12px; color: #4a6278; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# INICIALIZAÇÃO
# =============================================================================

@st.cache_resource
def inicializar_banco():
    """Inicializa o banco uma única vez por sessão."""
    init_db()

inicializar_banco()


# =============================================================================
# HELPERS
# =============================================================================

def badge_html(status: str) -> str:
    label_map = {
        "entregue":     "Entregue",
        "pendente":     "Pendente",
        "em_andamento": "Em andamento",
        "atrasado":     "Atrasado",
    }
    return (
        f'<span class="badge badge-{status}">'
        f'{label_map.get(status, status)}</span>'
    )


def _prazos_para_df() -> pd.DataFrame:
    """
    Carrega todos os prazos do banco, enriquece com colunas de análise
    e une com nomes de clientes e tipos de obrigação.
    """
    prazos  = listar_prazos(apenas_ativos=True)
    clientes = {c.id: c.nome for c in listar_clientes(apenas_ativos=True)}
    tipos    = {t.id: t.nome for t in listar_tipos_obrigacao()}

    if not prazos:
        return pd.DataFrame()

    rows = []
    for p in prazos:
        rows.append({
            "id":              p.id,
            "cliente_id":      p.cliente_id,
            "nome_cliente":    clientes.get(p.cliente_id, "—"),
            "tipo_obrigacao":  tipos.get(p.tipo_obrigacao_id, "—"),
            "competencia":     p.competencia,
            "data_vencimento": p.data_vencimento,
            "status":          p.status,
            "entregue_em":     p.entregue_em,
            "observacao":      p.observacao or "",
        })

    df = pd.DataFrame(rows)
    return enriquecer_prazos(df)


def _render_kpi(label: str, valor: str, classe: str = "", sub: str = "") -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value {classe}">{valor}</div>
        {sub_html}
    </div>
    """


# =============================================================================
# SIDEBAR — navegação e filtros globais
# =============================================================================

with st.sidebar:

    # ── Ícones de contato ──
    st.markdown("""
    <div style="display:flex; gap:10px; padding: 4px 0 12px;">
        <a href="https://www.linkedin.com/in/garyrainercv/" target="_blank"
           style="display:flex; align-items:center; justify-content:center;
                  width:32px; height:32px; background:#0a66c2;
                  border-radius:6px; text-decoration:none;">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
                 viewBox="0 0 24 24" fill="white">
                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037
                         -1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046
                         c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286z
                         M5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063
                         2.065zm1.782 13.019H3.555V9h3.564v11.452z"/>
            </svg>
        </a>
        <a href="https://github.com/gary-rainer-chumacero-vanderlei" target="_blank"
           style="display:flex; align-items:center; justify-content:center;
                  width:32px; height:32px; background:#24292e;
                  border-radius:6px; text-decoration:none;">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
                 viewBox="0 0 24 24" fill="white">
                <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205
                         11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04
                         -3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755
                         -1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838
                         1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776
                         .417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93
                         0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176
                         0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006
                         2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653
                         .24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805
                         5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896
                         -.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24
                         12.297c0-6.627-5.373-12-12-12"/>
            </svg>
        </a>
    </div>
    """, unsafe_allow_html=True)

    # ── Identidade ──
    st.markdown("""
    <div style="padding: 4px 0 16px;">
        <div style="font-size:11px; font-weight:700; letter-spacing:0.12em;
                    color:#4a5068; text-transform:uppercase; margin-bottom:6px;">
            Gary Rainer Chumacero Vanderlei<br>Portfólio · Tecnologia Contábil
        </div>
        <div style="font-size:18px; font-weight:700; color:#c8d6e5;">
            📋 Fiscal Deadlines
        </div>
        <div style="font-size:12px; color:#4a6278; margin-top:2px;">
            Painel de Prazos Fiscais
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── Navegação ──
    pagina = st.radio(
        "Navegação",
        ["Painel", "Prazos", "Clientes"],
        label_visibility="collapsed",
    )

    st.divider()

    # ── Rodapé ──
    st.markdown(
        '<div class="sidebar-caption">'
        'Jan 2026 · Dez 2026<br><br>'
        'Stack: Python · SQLAlchemy · Pydantic<br>'
        'Streamlit · SQLite · pytest'
        '</div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# PÁGINA: PAINEL
# =============================================================================

if pagina == "Painel":

    st.markdown("""
    <div class="page-header">
        <div class="page-title">Painel da Carteira</div>
        <div class="page-sub">Visão consolidada de prazos e alertas</div>
    </div>
    """, unsafe_allow_html=True)

    df = _prazos_para_df()

    if df.empty:
        st.info("Nenhum prazo cadastrado. Execute `python gerar_dados.py` ou cadastre clientes na aba Clientes.")
        st.stop()

    kpis = calcular_kpis(df)

    # --- KPIs principais ---
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.markdown(_render_kpi(
            "Clientes ativos",
            str(kpis["total_clientes_ativos"]),
        ), unsafe_allow_html=True)

    with c2:
        st.markdown(_render_kpi(
            "Prazos no período",
            str(kpis["total_prazos_mes"]),
        ), unsafe_allow_html=True)

    with c3:
        st.markdown(_render_kpi(
            "Entregues",
            str(kpis["total_entregues"]),
            classe="positivo",
            sub=f"{kpis['pct_entregues']:.0%} do total",
        ), unsafe_allow_html=True)

    with c4:
        st.markdown(_render_kpi(
            "Atenção (≤ 7 dias)",
            str(kpis["prazos_proximos_7_dias"]),
            classe="atencao" if kpis["prazos_proximos_7_dias"] > 0 else "",
        ), unsafe_allow_html=True)

    with c5:
        st.markdown(_render_kpi(
            "Atrasados",
            str(kpis["total_atrasados"]),
            classe="critico" if kpis["total_atrasados"] > 0 else "",
            sub=f"{kpis['pct_em_risco']:.0%} em risco",
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Alertas e resumo por obrigação ---
    col_alertas, col_obr = st.columns([1.2, 1])

    with col_alertas:
        st.markdown("**Alertas — próximos 7 dias e atrasados**")

        df_alertas = df[
            ((df["urgencia"].isin(["critico", "atencao"])) & (df["status"] != "entregue"))
        ].sort_values("data_vencimento")

        if df_alertas.empty:
            st.success("Nenhum prazo crítico ou em atenção no momento.")
        else:
            for _, row in df_alertas.iterrows():
                classe = "alerta-critico" if row["urgencia"] == "critico" else "alerta-atencao"
                cor    = COR_ATRASADO if row["urgencia"] == "critico" else COR_ATENCAO
                st.markdown(f"""
                <div class="alerta-row {classe}">
                    <span style="color:{cor};font-size:16px;">●</span>
                    <span class="alerta-nome">{row['nome_cliente']}</span>
                    <span class="alerta-obr">{row['tipo_obrigacao']} · {row['competencia']}</span>
                    <span class="alerta-dias" style="color:{cor};">{row['label_dias']}</span>
                </div>
                """, unsafe_allow_html=True)

    with col_obr:
        st.markdown("**Resumo por obrigação**")
        df_obr = kpis_por_obrigacao(df)

        if not df_obr.empty:
            for _, row in df_obr.iterrows():
                pct = row["pct_entregues"]
                cor_barra = COR_ENTREGUE if pct >= 0.8 else (COR_ATENCAO if pct >= 0.5 else COR_ATRASADO)
                st.markdown(f"""
                <div style="margin-bottom:12px;">
                    <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px;">
                        <span style="color:#c8d6e5;font-weight:500;">{row['tipo_obrigacao']}</span>
                        <span style="font-family:'IBM Plex Mono',monospace;color:#4a6278;">
                            {row['entregues']}/{row['total']}
                        </span>
                    </div>
                    <div style="background:#1e2d3d;border-radius:4px;height:6px;">
                        <div style="background:{cor_barra};width:{pct*100:.0f}%;height:6px;border-radius:4px;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    # --- Ranking de clientes em risco ---
    st.markdown("**Clientes com mais prazos em risco**")
    df_cli = kpis_por_cliente(df, top_n=5)

    if not df_cli.empty:
        cols = st.columns(min(len(df_cli), 5))
        for i, (_, row) in enumerate(df_cli.iterrows()):
            with cols[i]:
                em_risco = int(row["em_risco"])
                classe   = "critico" if em_risco > 1 else ("atencao" if em_risco == 1 else "")
                st.markdown(_render_kpi(
                    row["nome_cliente"].split()[0],  # Primeiro nome da empresa
                    str(em_risco),
                    classe=classe,
                    sub=f"{row['pct_entregues']:.0%} entregues",
                ), unsafe_allow_html=True)


# =============================================================================
# PÁGINA: PRAZOS
# =============================================================================

elif pagina == "Prazos":

    st.markdown("""
    <div class="page-header">
        <div class="page-title">Gestão de Prazos</div>
        <div class="page-sub">Visualize, filtre e atualize o status das obrigações</div>
    </div>
    """, unsafe_allow_html=True)

    df = _prazos_para_df()

    if df.empty:
        st.info("Nenhum prazo cadastrado.")
        st.stop()

    # --- Filtros ---
    with st.expander("Filtros", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns(4)

        clientes_opcoes = ["Todos"] + sorted(df["nome_cliente"].unique().tolist())
        tipos_opcoes    = ["Todos"] + sorted(df["tipo_obrigacao"].unique().tolist())
        status_opcoes   = ["Todos"] + STATUS_PRAZO
        comp_opcoes     = ["Todas"] + sorted(df["competencia"].unique().tolist(), reverse=True)

        with fc1:
            filtro_cliente = st.selectbox("Cliente", clientes_opcoes)
        with fc2:
            filtro_tipo = st.selectbox("Obrigação", tipos_opcoes)
        with fc3:
            filtro_status = st.selectbox("Status", status_opcoes)
        with fc4:
            filtro_comp = st.selectbox("Competência", comp_opcoes)

    # Aplica filtros
    df_filtrado = df.copy()
    if filtro_cliente != "Todos":
        df_filtrado = df_filtrado[df_filtrado["nome_cliente"] == filtro_cliente]
    if filtro_tipo != "Todos":
        df_filtrado = df_filtrado[df_filtrado["tipo_obrigacao"] == filtro_tipo]
    if filtro_status != "Todos":
        df_filtrado = df_filtrado[df_filtrado["status"] == filtro_status]
    if filtro_comp != "Todas":
        df_filtrado = df_filtrado[df_filtrado["competencia"] == filtro_comp]

    st.markdown(f"**{len(df_filtrado)} prazo(s) encontrado(s)**")

    # --- Tabela ---
    if df_filtrado.empty:
        st.warning("Nenhum prazo encontrado com os filtros aplicados.")
    else:
        for _, row in df_filtrado.iterrows():
            cor_linha = (
                "#1a0a0a" if row["urgencia"] == "critico" and row["status"] != "entregue"
                else "#1a1200" if row["urgencia"] == "atencao" and row["status"] != "entregue"
                else "transparent"
            )
            st.markdown(f"""
            <div style="
                display:flex; align-items:center; gap:16px;
                padding:10px 14px; border-radius:6px;
                background:{cor_linha};
                border:1px solid #1e2d3d;
                margin-bottom:4px; font-size:13px;
            ">
                <span style="color:#c8d6e5;font-weight:500;flex:2;">{row['nome_cliente']}</span>
                <span style="color:#4a6278;flex:1;">{row['tipo_obrigacao']}</span>
                <span style="font-family:'IBM Plex Mono',monospace;color:#4a6278;flex:0 0 70px;">{row['competencia']}</span>
                <span style="font-family:'IBM Plex Mono',monospace;color:#c8d6e5;flex:0 0 90px;">
                    {row['data_vencimento'].strftime('%d/%m/%Y')}
                </span>
                {badge_html(row['status'])}
                <span style="color:#4a6278;flex:1;text-align:right;">{row['label_dias']}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # --- Atualizar status de um prazo ---
    st.markdown("**Atualizar status de um prazo**")

    col_sel, col_status, col_obs, col_btn = st.columns([2, 1, 2, 1])

    with col_sel:
        if not df_filtrado.empty:
            opcoes_prazo = {
                f"{r['nome_cliente']} · {r['tipo_obrigacao']} · {r['competencia']}": r["id"]
                for _, r in df_filtrado.iterrows()
            }
            prazo_selecionado_label = st.selectbox("Prazo", list(opcoes_prazo.keys()))
            prazo_id_sel = opcoes_prazo[prazo_selecionado_label]
        else:
            st.selectbox("Prazo", ["—"], disabled=True)
            prazo_id_sel = None

    with col_status:
        novo_status = st.selectbox("Novo status", STATUS_PRAZO)

    with col_obs:
        observacao = st.text_input("Observação (opcional)")

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Atualizar", use_container_width=True) and prazo_id_sel:
            try:
                atualizar_prazo(
                    prazo_id_sel,
                    PrazoUpdate(
                        status=novo_status,
                        observacao=observacao or None,
                    ),
                )
                st.success("Status atualizado.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")


# =============================================================================
# PÁGINA: CLIENTES
# =============================================================================

elif pagina == "Clientes":

    st.markdown("""
    <div class="page-header">
        <div class="page-title">Gestão de Clientes</div>
        <div class="page-sub">Cadastre e gerencie a carteira do escritório</div>
    </div>
    """, unsafe_allow_html=True)

    # --- Cadastro ---
    with st.expander("Cadastrar novo cliente", expanded=False):
        cc1, cc2, cc3, cc4 = st.columns([2, 1.5, 1.5, 1])

        with cc1:
            novo_nome = st.text_input("Razão social")
        with cc2:
            novo_cnpj = st.text_input("CNPJ (somente números)")
        with cc3:
            novo_regime = st.selectbox("Regime tributário", REGIMES_TRIBUTARIOS)
        with cc4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Cadastrar", use_container_width=True):
                if not novo_nome or not novo_cnpj:
                    st.error("Nome e CNPJ são obrigatórios.")
                else:
                    try:
                        criar_cliente(ClienteCreate(
                            nome=novo_nome,
                            cnpj=novo_cnpj,
                            regime_tributario=novo_regime,
                        ))
                        st.success(f"Cliente '{novo_nome}' cadastrado.")
                        st.rerun()
                    except PrazoDuplicadoError:
                        st.error("Já existe um cliente com este CNPJ.")
                    except Exception as e:
                        st.error(f"Erro de validação: {e}")

    # --- Lista de clientes ---
    clientes = listar_clientes(apenas_ativos=False)

    if not clientes:
        st.info("Nenhum cliente cadastrado.")
        st.stop()

    st.markdown(f"**{len(clientes)} cliente(s) cadastrado(s)**")

    for cliente in clientes:
        status_cor  = COR_ENTREGUE if cliente.ativo else COR_ATRASADO
        status_txt  = "Ativo" if cliente.ativo else "Inativo"

        with st.container():
            cl1, cl2, cl3, cl4, cl5 = st.columns([3, 1.5, 1.5, 0.8, 0.8])

            with cl1:
                st.markdown(
                    f'<span style="color:#c8d6e5;font-weight:500;">{cliente.nome}</span>',
                    unsafe_allow_html=True,
                )
            with cl2:
                st.markdown(
                    f'<span style="font-family:IBM Plex Mono,monospace;font-size:12px;color:#4a6278;">'
                    f'{cliente.cnpj}</span>',
                    unsafe_allow_html=True,
                )
            with cl3:
                st.markdown(
                    f'<span style="font-size:12px;color:#4a6278;">{cliente.regime_tributario}</span>',
                    unsafe_allow_html=True,
                )
            with cl4:
                st.markdown(
                    f'<span style="font-size:12px;color:{status_cor};">{status_txt}</span>',
                    unsafe_allow_html=True,
                )
            with cl5:
                novo_ativo = not cliente.ativo
                label_btn  = "Ativar" if not cliente.ativo else "Inativar"
                if st.button(label_btn, key=f"toggle_{cliente.id}"):
                    atualizar_cliente(cliente.id, ClienteUpdate(ativo=novo_ativo))
                    st.rerun()

            st.divider()
