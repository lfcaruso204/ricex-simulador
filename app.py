"""
Simulador de Importação — Ricex
=================================
Aplicativo Streamlit para simular a importação de produtos variados,
com opções dinâmicas de frete (Fatura ou Quantidade), parâmetros de venda
(ICMS de Venda, Marketing e Outros), e roteiro analítico dos cálculos.
"""
import base64
import random
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from database import (
    init_db,
    listar_produtos,
    obter_parametros_gerais,
    salvar_parametros_gerais,
    adicionar_produto,
)
from calculations import ItemSimulacao, calcular_simulacao
from pdf_generator import gerar_pdf_orcamento

BASE_DIR = Path(__file__).parent
LOGO_PATH = BASE_DIR / "assets" / "Ricex_logo.png"

st.set_page_config(
    page_title="Ricex | Simulador de Importação Multiprojetos",
    page_icon="📊",
    layout="wide",
)

init_db()

# ----------------------------------------------------------------------------
# Cabeçalho com logo + Reservas vazias (Empty) para o dashboard superior direito
# ----------------------------------------------------------------------------
col_logo, col_title, col_chart, col_metric = st.columns([1.0, 3.5, 4.0, 1.5])

with col_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=140)
        
with col_title:
    st.markdown("<h2 style='margin:0; padding:0; font-size: 28px;'>Simulador de Importação Multiprojetos</h2>", unsafe_allow_html=True)
    st.caption("Ricex Importação — custos, impostos, rateio e precificação analítica")

# Containers vazios aguardando o cálculo da simulação
placeholder_chart = col_chart.empty()
placeholder_metric = col_metric.empty()

st.divider()


# Funções universais de formatação customizada
def _fmt_rs(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_usd(v: float) -> str:
    return "US$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_qtd(v: int) -> str:
    return f"{v:,}".replace(",", ".")


def _fmt_pct(v: float) -> str:
    return f"{v * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


# ----------------------------------------------------------------------------
# Barra Lateral: Parâmetros gerais da operação
# ----------------------------------------------------------------------------
params_db = obter_parametros_gerais()

with st.sidebar:
    st.header("⚙️ Parâmetros da Operação")
    st.caption("Altere os valores padrão da remessa e impostos abaixo:")
    
    cambio = st.number_input("Câmbio (R$/US$)", min_value=0.0, value=float(params_db.get("cambio", 5.00)), step=0.001, format="%.4f")
    frete_internacional = st.number_input("Frete internacional total (US$)", min_value=0.0, value=float(params_db.get("frete_internacional", 1000.0)), step=50.0)
    despesas_portuarias = st.number_input("Despesas portuárias (R$)", min_value=0.0, value=float(params_db.get("despesas_portuarias", 2000.0)), step=500.0)
    
    st.divider()
    st.subheader("Impostos de Importação")
    
    ii = st.number_input("II — Imposto de Importação (%)", min_value=0.0, max_value=200.0, value=float(params_db.get("ii", 0.20)) * 100, step=0.5) / 100
    ipi = st.number_input("IPI (%)", min_value=0.0, max_value=200.0, value=float(params_db.get("ipi", 0.10)) * 100, step=0.5) / 100
    pis = st.number_input("PIS-Importação (%)", min_value=0.0, max_value=100.0, value=float(params_db.get("pis", 0.021)) * 100, step=0.1) / 100
    cofins = st.number_input("COFINS-Importação (%)", min_value=0.0, max_value=100.0, value=float(params_db.get("cofins", 0.0965)) * 100, step=0.1) / 100
    icms = st.number_input("ICMS Importação (por dentro %)", min_value=0.0, max_value=99.0, value=float(params_db.get("icms", 0.18)) * 100, step=0.5) / 100
    afrmm = st.number_input("AFRMM (sobre frete %)", min_value=0.0, max_value=100.0, value=float(params_db.get("afrmm", 0.08)) * 100, step=0.5) / 100

    st.divider()
    st.subheader("📊 Parâmetros Comerciais e de Venda")
    icms_venda = st.number_input("ICMS da Venda Simulada (%)", min_value=0.0, max_value=100.0, value=18.0, step=0.5) / 100
    outros_custos_pct = st.number_input("Outros (Mkt, Propaganda, etc. %)", min_value=0.0, max_value=100.0, value=5.0, step=0.5) / 100

    st.sidebar.divider()
    if st.button("💾 Salvar como padrão", use_container_width=True):
        salvar_parametros_gerais(
            {
                "cambio": cambio,
                "frete_internacional": frete_internacional,
                "despesas_portuarias": despesas_portuarias,
                "ii": ii,
                "ipi": ipi,
                "pis": pis,
                "cofins": cofins,
                "afrmm": afrmm,
                "icms": icms,
                "markup": params_db.get("markup", 1.0),
            }
        )
        st.success("Parâmetros salvos com padrão!")


# ----------------------------------------------------------------------------
# 1. Catálogo de produtos (SQLite) + seleção de itens
# ----------------------------------------------------------------------------
st.header("1. Seleção de produtos da remessa")

from database import remover_produto

aba_adicionar, aba_remover = st.tabs(["➕ Adicionar Produto", "❌ Remover Produto"])

with aba_adicionar:
    nc1, nc2, nc3, nc4, nc5 = st.columns([1, 2, 2, 1, 1])
    with nc1:
        novo_ref = st.text_input("Ref. (Opcional)", key="novo_ref")
    with nc2:
        novo_nome = st.text_input("Produto", key="novo_nome")
    with nc3:
        novo_comp = st.text_input("Composição/Tipo", key="novo_comp")
    with nc4:
        novo_fob = st.number_input("FOB US$/un.", min_value=0.0, value=0.0, step=0.1, key="novo_fob")
    with nc5:
        novo_qtd = st.number_input("Qtd. padrão", min_value=1, value=1000, step=50, key="novo_qtd")
        if st.button("Adicionar produto"):
            if not novo_ref.strip():
                try:
                    produtos_existentes = listar_produtos()
                    refs_existentes = [int(p['ref']) for p in produtos_existentes if p['ref'].isdigit()]
                    novo_ref = str(max(refs_existentes) + 1) if refs_existentes else "1000"
                except:
                    novo_ref = str(random.randint(1000, 9999))
            
            if novo_nome and novo_fob > 0:
                try:
                    adicionar_produto(novo_ref, novo_nome, novo_comp, novo_fob, int(novo_qtd))
                    st.success(f"Produto '{novo_nome}' adicionado com a Ref: {novo_ref}")
                    st.rerun()
                except Exception as e:
                    if "UNIQUE constraint failed" in str(e):
                        st.error(f"❌ Erro: Já existe um produto cadastrado com a Ref. **'{novo_ref}'**.")
                    else:
                        st.error(f"Não foi possível adicionar: {e}")
            else:
                st.warning("Informe ao menos o nome do Produto e o preço FOB US$/un.")

with aba_remover:
    produtos_db_remover = listar_produtos(somente_ativos=True)
    
    if produtos_db_remover:
        opcoes_remover = {f"{p['ref']} — {p['produto']}": p['id'] for p in produtos_db_remover}
        
        produto_para_remover = st.selectbox(
            "Selecione o produto que deseja excluir do catálogo:",
            options=list(opcoes_remover.keys()),
            key="sb_remover_produto"
        )
        
        if st.button("Remover Produto Permanentemente", type="secondary"):
            id_para_remover = opcoes_remover[produto_para_remover]
            try:
                remover_produto(id_para_remover)
                st.success("Produto removido com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao remover produto: {e}")
    else:
        st.info("Não há produtos ativos no catálogo para remover.")

produtos_db = listar_produtos()
if not produtos_db:
    st.warning("Nenhum produto cadastrado no catálogo.")
    st.stop()

opcoes = {f"{p['ref']} — {p['produto']}": p for p in produtos_db}
selecionados_labels = st.multiselect(
    "Escolha os produtos que farão parte desta remessa",
    options=list(opcoes.keys()),
    default=list(opcoes.keys())[:7] if len(opcoes) >= 7 else list(opcoes.keys()),
)

if not selecionados_labels:
    st.info("Selecione ao menos um produto para simular a importação.")
    st.stop()

st.divider()


# ----------------------------------------------------------------------------
# 2. Definição de Quantidades, Itens e Tipo de Frete
# ----------------------------------------------------------------------------
st.header("2. Quantidades, preços e parametrização do Frete")

tipo_frete_global = st.radio(
    "Defina o método de distribuição do frete para toda a remessa:",
    options=["Por Fatura (Proporcional ao valor em US$)", "Por Quantidade / Peso (Proporcional ao quilo/volume)"],
    horizontal=True
)

is_frete_quantidade = "Quantidade" in tipo_frete_global

linhas_itens = []
for label in selecionados_labels:
    p = opcoes[label]
    item_dict = {
        "Ref.": p["ref"],
        "Produto": p["produto"],
        "Composição/Tipo": p["composicao"],
        "Qtd.": int(p["qtd_padrao"]),
        "FOB US$/un.": float(p["fob_usd"]),
    }
    if is_frete_quantidade:
        item_dict["Peso Unit. (kg)"] = 1.0  
    linhas_itens.append(item_dict)

df_itens_config = pd.DataFrame(linhas_itens)

col_config_itens = {
    "Qtd.": st.column_config.NumberColumn(min_value=1, step=1),
    "FOB US$/un.": st.column_config.NumberColumn(min_value=0.0, step=0.1, format="US$ %.2f"),
}
if is_frete_quantidade:
    col_config_itens["Peso Unit. (kg)"] = st.column_config.NumberColumn(min_value=0.01, step=0.1, format="%.2f kg")

df_itens_editado = st.data_editor(
    df_itens_config,
    column_config=col_config_itens,
    disabled=["Ref.", "Produto", "Composição/Tipo"],
    hide_index=True,
    use_container_width=True,
    key="editor_itens_frete"
)

total_qtd_t2 = df_itens_editado["Qtd."].sum()
total_fob_t2 = (df_itens_editado["Qtd."] * df_itens_editado["FOB US$/un."]).sum()

if is_frete_quantidade:
    # Correção da fórmula do peso total acumulado baseado nas edições em tempo real
    total_peso_t2 = (df_itens_editado["Qtd."] * df_itens_editado["Peso Unit. (kg)"]).sum()
    peso_formatado = f"{total_peso_t2:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    st.markdown(
        f"📊 **SOMA** — Quantidade Total: **{_fmt_qtd(int(total_qtd_t2))}** | "
        f"FOB Total: **{_fmt_usd(total_fob_t2)}** | "
        f"Peso Total: **{peso_formatado} kg**"
    )
else:
    st.markdown(
        f"📊 **SOMA** — Quantidade Total: **{_fmt_qtd(int(total_qtd_t2))}** | "
        f"FOB Total: **{_fmt_usd(total_fob_t2)}**"
    )

st.divider()


# ============================================================================
# 3. Processamento Inicial dos Custos de Importação (Nacionalização)
# ============================================================================
st.header("3. Custo geral da importação (Nacionalização)")

total_fob_fatura = 0.0
total_peso_acumulado = 0.0

for _, row in df_itens_editado.iterrows():
    total_fob_fatura += float(row["Qtd."]) * float(row["FOB US$/un."])
    if is_frete_quantidade:
        total_peso_acumulado += float(row["Qtd."]) * float(row["Peso Unit. (kg)"])

itens_pre_calculo = []
for _, row in df_itens_editado.iterrows():
    qtd = float(row["Qtd."])
    fob_unit = float(row["FOB US$/un."])
    fob_total_item = qtd * fob_unit
    
    # Correção crítica do motor de cálculo: vinculando o frete estrito à variável total de quilos correta
    if not is_frete_quantidade and total_fob_fatura > 0:
        fator_frete = fob_total_item / total_fob_fatura
    elif is_frete_quantidade and total_peso_acumulado > 0:
        item_peso_total = qtd * float(row["Peso Unit. (kg)"])
        fator_frete = item_peso_total / total_peso_acumulado
    else:
        fator_frete = 1.0 / len(df_itens_editado)
        
    frete_atribuido_usd = frete_internacional * fator_frete
    
    item = ItemSimulacao(
        ref=row["Ref."],
        produto=row["Produto"],
        composicao=row["Composição/Tipo"],
        qtd=qtd,
        fob_unit_usd=fob_unit,
        modo="markup" 
    )
    item.frete_customizado_usd = frete_atribuido_usd
    itens_pre_calculo.append(item)

resultado = calcular_simulacao(
    itens=itens_pre_calculo,
    cambio=cambio,
    frete_internacional_usd=frete_internacional,
    despesas_portuarias_rs=despesas_portuarias,
    ii=ii,
    ipi=ipi,
    pis=pis,
    cofins=cofins,
    afrmm=afrmm,
    icms=icms,
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total da invoice (US$)", _fmt_usd(resultado.total_invoice_usd))
m2.metric("Mercadoria (R$)", _fmt_rs(resultado.mercadoria_rs_total))
m3.metric("Valor aduaneiro (R$)", _fmt_rs(resultado.valor_aduaneiro_rs))
m4.metric("Custo de Importação (R$)", _fmt_rs(resultado.custo_geral_importacao_rs))

st.info(
    "💡 **Esclarecimento de Conceitos:**\n"
    "- **Valor Aduaneiro:** Base tributária regulamentar composta pelo preço da mercadoria + frete + seguro internacional (antes das taxas nacionais).\n"
    "- **Custo de Importação (Nacionalização):** Soma do Valor Aduaneiro convertido com *todos* os impostos (II, IPI, PIS, COFINS, ICMS) e taxas de infraestrutura (Porto/AFRMM)."
)

impostos_df = pd.DataFrame(
    {
        "Tributo/Encargo": [
            f"II ({_fmt_pct(ii)})", 
            f"IPI ({_fmt_pct(ipi)})", 
            f"PIS-Importação ({_fmt_pct(pis)})", 
            f"COFINS-Importação ({_fmt_pct(cofins)})", 
            f"AFRMM ({_fmt_pct(afrmm)})", 
            f"ICMS Importação ({_fmt_pct(icms)})", 
            "Despesas portuárias"
        ],
        "Valor (R$)": [
            resultado.ii_rs_total,
            resultado.ipi_rs_total,
            resultado.pis_rs_total,
            resultado.cofins_rs_total,
            resultado.afrmm_rs_total,
            resultado.icms_rs_total,
            resultado.despesas_portuarias_rs,
        ],
    }
)

soma_impostos = impostos_df["Valor (R$)"].sum()

df_impostos_render = impostos_df.copy()
df_impostos_render["Valor (R$)"] = df_impostos_render["Valor (R$)"].map(_fmt_rs)
st.dataframe(df_impostos_render, hide_index=True, use_container_width=True)

st.markdown(f"💰 **SOMA** — Total de Tributos/Encargos: **{_fmt_rs(soma_impostos)}**")

st.divider()


# ============================================================================
# 4. Precificação Final Comercial (Markup e Impostos de Venda)
# ============================================================================
st.header("4. Precificação Final Comercial (Markup e Impostos de Venda)")

modo_global = st.radio(
    "Modo de cálculo comercial",
    options=["Definir markup (%) e simular o preço de venda final", "Definir o preço de venda final e extrair o markup"],
    horizontal=True,
)
modo_calc = "markup" if modo_global.startswith("Definir markup") else "preco_final"

markup_global_pct = params_db.get("markup", 1.0) * 100
if modo_calc == "markup":
    markup_global_pct = st.slider("Markup padrão (%) aplicado aos itens", 0, 300, int(markup_global_pct), step=5)

linhas_precificacao = []
for item in resultado.itens:
    linha = {
        "Ref.": item.ref,
        "Produto": item.produto,
        "Custo Nacionalizado Unit.": round(item.custo_unit_rs, 2),
    }
    if modo_calc == "markup":
        linha["Markup (%)"] = float(markup_global_pct)
    else:
        linha["Preço Venda Final Requerido (R$)"] = round(item.custo_unit_rs * 2.0, 2)
    linhas_precificacao.append(linha)

df_precificacao = pd.DataFrame(linhas_precificacao)

col_config_PRECO = {
    "Custo Nacionalizado Unit.": st.column_config.NumberColumn(format="R$ %.2f", disabled=True),
}
if modo_calc == "markup":
    col_config_PRECO["Markup (%)"] = st.column_config.NumberColumn(min_value=0.0, max_value=500.0, step=5.0, format="%.1f")
else:
    col_config_PRECO["Preço Venda Final Requerido (R$)"] = st.column_config.NumberColumn(min_value=0.0, step=1.0, format="R$ %.2f")

df_prec_editado = st.data_editor(
    df_precificacao,
    column_config=col_config_PRECO,
    disabled=["Ref.", "Produto", "Custo Nacionalizado Unit."],
    hide_index=True,
    use_container_width=True,
    key="editor_precificacao"
)

soma_custo_nac_unit_t4 = df_prec_editado["Custo Nacionalizado Unit."].sum()
st.markdown(f"📊 **SOMA** — Custo Nacionalizado Unitário Total: **{_fmt_rs(soma_custo_nac_unit_t4)}**")

# ----------------------------------------------------------------------------
# Recálculo Comercial Pós-Importação (Tabela Única Consolidada)
# ----------------------------------------------------------------------------
det_rows = []
total_receita_simulada = 0.0
total_custo_comercial_total = 0.0

soma_qtd_t5 = 0
soma_custo_un_absoluto = 0.0
soma_icms_venda_total = 0.0
soma_mkt_total = 0.0
soma_preco_venda_un_total = 0.0

for idx, item in enumerate(resultado.itens):
    row_edit = df_prec_editado.iloc[idx]
    custo_base_unit = item.custo_unit_rs
    
    if modo_calc == "markup":
        mk_aplicado = float(row_edit["Markup (%)"]) / 100
        divisor = 1.0 - (icms_venda + outros_custos_pct)
        if divisor > 0:
            preco_venda_unit = (custo_base_unit * (1 + mk_aplicado)) / divisor
        else:
            preco_venda_unit = custo_base_unit * (1 + mk_aplicado)
    else:
        preco_venda_unit = float(row_edit["Preço Venda Final Requerido (R$)"])
        margem_liquida_rs = (preco_venda_unit * (1.0 - icms_venda - outros_custos_pct)) - custo_base_unit
        mk_aplicado = (margem_liquida_rs / custo_base_unit) if custo_base_unit > 0 else 0.0

    venda_total_item = preco_venda_unit * item.qtd
    icms_venda_rs = venda_total_item * icms_venda
    outros_custos_rs = venda_total_item * outros_custos_pct
    
    custo_total_comercial_item = item.custo_total_rs + icms_venda_rs + outros_custos_rs
    lucro_liquido_item = venda_total_item - custo_total_comercial_item
    
    total_receita_simulada += venda_total_item
    total_custo_comercial_total += custo_total_comercial_item
    
    soma_qtd_t5 += int(item.qtd)
    soma_custo_un_absoluto += custo_base_unit
    soma_icms_venda_total += (icms_venda_rs / item.qtd if item.qtd > 0 else 0)
    soma_mkt_total += (outros_custos_rs / item.qtd if item.qtd > 0 else 0)
    soma_preco_venda_un_total += preco_venda_unit
    
    det_rows.append({
        "Produto": f"{item.ref} — {item.produto}",
        "Qtd.": int(item.qtd),
        "Custo Nac. Un.": custo_base_unit,
        "Markup": mk_aplicado,
        "ICMS Venda": (icms_venda_rs / item.qtd if item.qtd > 0 else 0),
        "Outros/Mkt": (outros_custos_rs / item.qtd if item.qtd > 0 else 0),
        "Preço Venda Un.": preco_venda_unit,
        "Faturamento Esperado": venda_total_item,
        "Lucro Líquido": lucro_liquido_item
    })

df_detalhado_final = pd.DataFrame(det_rows)

df_det_render = pd.DataFrame()
df_det_render["Produto"] = df_detalhado_final["Produto"]
df_det_render["Qtd."] = df_detalhado_final["Qtd."]
df_det_render["Custo Nac. Un."] = df_detalhado_final["Custo Nac. Un."].map(_fmt_rs)
df_det_render["Markup"] = df_detalhado_final["Markup"].map(_fmt_pct)
df_det_render["ICMS Venda"] = df_detalhado_final["ICMS Venda"].map(_fmt_rs)
df_det_render["Outros/Mkt"] = df_detalhado_final["Outros/Mkt"].map(_fmt_rs)
df_det_render["Preço Venda Un."] = df_detalhado_final["Preço Venda Un."].map(_fmt_rs)
df_det_render["Faturamento Esperado"] = df_detalhado_final["Faturamento Esperado"].map(_fmt_rs)
df_det_render["Lucro Líquido"] = df_detalhado_final["Lucro Líquido"].map(_fmt_rs)

st.subheader("📋 Tabela Consolidada de Distribuição Comercial por Item")
st.dataframe(df_det_render, hide_index=True, use_container_width=True)

st.markdown(
    f"📊 **SOMA** — Quantidade Total: **{_fmt_qtd(soma_qtd_t5)}** | "
    f"Custo Nac. Unitário Total: **{_fmt_rs(soma_custo_un_absoluto)}** | "
    f"Faturamento Geral Esperado: **{_fmt_rs(total_receita_simulada)}** | "
    f"Lucro Líquido Geral: **{_fmt_rs(total_receita_simulada - total_custo_comercial_total)}**"
)

lucro_global_calculado = total_receita_simulada - total_custo_comercial_total
roi_global_calculado = (lucro_global_calculado / total_custo_comercial_total) if total_custo_comercial_total > 0 else 0.0

with placeholder_chart:
    labels_pie = ['Custo de Importação + Comercial', 'Lucro Líquido Estimado']
    values_pie = [total_custo_comercial_total, lucro_global_calculado]
    text_values_pie = [_fmt_rs(v) for v in values_pie]

    fig = go.Figure(data=[go.Pie(
        labels=labels_pie, 
        values=values_pie, 
        hole=.5,
        marker=dict(colors=['#FF4B4B', '#00D48A']),
        showlegend=True,
        text=text_values_pie,
        textinfo='label+text',
        textposition='outside',
        hoverinfo='label+text'
    )])
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        height=180,
        legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

with placeholder_metric:
    st.metric(
        label="ROI Real da Operação",
        value=f"{roi_global_calculado * 100:.2f}%",
        delta=f"Lucro: {_fmt_rs(lucro_global_calculado)}",
        delta_color="normal"
    )

st.divider()


# ============================================================================
# 5. Resumo Financeiro Consolidado da Remessa
# ============================================================================
st.header("5. Resumo Financeiro Consolidado da Remessa")

r1, r2, r3, r4 = st.columns(4)
r1.metric("Custo Total Acumulado (R\$)", _fmt_rs(total_custo_comercial_total))
r2.metric("Receita Total Bruta (R\$)", _fmt_rs(total_receita_simulada))
r3.metric("Lucro Líquido Final (R\$)", _fmt_rs(lucro_global_calculado))
r4.metric("ROI Líquido da Operação", _fmt_pct(roi_global_calculado))

st.subheader("💰 Preço Final Total da Remessa (Faturamento Estimado)")
st.markdown(
    f"<div style='background-color:#1b2a4a;color:white;padding:18px;border-radius:8px;"
    f"font-size:28px;font-weight:bold;text-align:center;'>{_fmt_rs(total_receita_simulada)}</div>",
    unsafe_allow_html=True,
)

st.divider()


# ----------------------------------------------------------------------------
# 6. Roteiro e Memorial de Cálculo (Explicação do Processo)
# ----------------------------------------------------------------------------
st.header("6. Roteiro e Memorial de Cálculo da Importação")
st.markdown("""
Este roteiro resume todo o fluxo regulatório e comercial executado pelo sistema para a composição do preço final dos seus produtos:

1. **Formação do Valor Aduaneiro e Rateio de Frete**: Para cada item, calcula-se o valor **FOB Unitário** nacionalizado (multiplicado pelo câmbio informado e pela quantidade). Soma-se a isso a cota correspondente do frete internacional conforme a modalidade escolhida para a tabela como um todo:
    * **Por Fatura**: Geralmente utilizado quando se tem a intenção de importar muitos itens variados. O sistema pega o valor total da nota fiscal (invoice final) e divide proporcionalmente pelo valor de cada item.
    * **Por Quantidade**: Configuração voltada para o cálculo baseado no peso bruto ou cubagem que a mercadoria possui. Ideal para cenários de estufagem pesada (como um contêiner de 25 Toneladas), onde calcula-se o custo pelo quilo individual de cada produto. Assim que definido, esse peso distribuído é incorporado diretamente ao custo do restante do projeto.
2. **Cálculo em Cadeia dos Impostos Federais**:
    * **II (Imposto de Importação)**: Incide diretamente sobre o Valor Aduaneiro.
    * **IPI (Imposto sobre Produtos Industrializados)**: Incide sobre a base composta pelo (Valor Aduaneiro + II).
    * **PIS e COFINS-Importação**: Calculados conforme alíquotas fixadas sobre o Valor Aduaneiro nacionalizado.
3. **Cálculo por Dentro do ICMS de Importação**: O ICMS de entrada integra sua própria base de cálculo, incorporando todos os impostos anteriores, o valor aduaneiro e despesas aduaneiras divididos pelo fator `(1 - Alíquota do ICMS)`.
4. **Custo Nacionalizado Unitário**: É o somatório final de todos os custos de nacionalização e encargos aduaneiros, divididos pela quantidade exata de cada item, refletindo o custo bruto real de entrada no estoque.
5. **Formação Comercial de Venda (Saída)**:
    * Se definido por **Markup**, a margem desejada é adicionada ao Custo Nacionalizado e o preço final é recalculado "por dentro" para absorver os impostos incidentes sobre o faturamento.
    * São deduzidos do preço bruto de saída o **ICMS de Venda (padrão 18%)** e a provisão para **Outros Custos Comerciais (Marketing, Propaganda, etc.)**, garantindo que as projeções de Lucro Líquido final e ROI representem as margens reais após a liquidação de obrigações tributárias e operacionais da empresa.
""")

st.divider()


# ============================================================================
# 7. Geração e Prévia de PDF
# ============================================================================
st.header("7. Gerar e Visualizar Orçamento em PDF")

if "pdf_bytes_gerado" not in st.session_state:
    st.session_state.pdf_bytes_gerado = None
if "pdf_gerado_sucesso" not in st.session_state:
    st.session_state.pdf_gerado_sucesso = False

pc1, pc2 = st.columns(2)
with pc1:
    cliente_nome = st.text_input("Nome do cliente (opcional)", key="pdf_cliente")
with pc2:
    numero_orcamento = st.text_input("Número do orçamento (opcional)", key="pdf_numero")
observacoes = st.text_area("Observações do Orçamento (opcional)", height=80, key="pdf_obs")

if st.button("📄 Gerar e Visualizar PDF", type="primary"):
    valores_comerciais = {
        "custo_total_rs": total_custo_comercial_total,
        "receita_total_rs": total_receita_simulada,
        "lucro_total_rs": lucro_global_calculado,
        "roi": roi_global_calculado
    }
    
    try:
        bytes_temp = gerar_pdf_orcamento(
            resultado=resultado,
            logo_path=str(LOGO_PATH),
            cliente=cliente_nome,
            numero_orcamento=numero_orcamento,
            observacoes=observacoes,
            valores_comerciais=valores_comerciais
        )
    except TypeError:
        bytes_temp = gerar_pdf_orcamento(
            resultado=resultado,
            logo_path=str(LOGO_PATH),
            cliente=cliente_nome,
            numero_orcamento=numero_orcamento,
            observacoes=observacoes,
        )
    
    st.session_state.pdf_bytes_gerado = bytes_temp
    st.session_state.pdf_gerado_sucesso = True

if st.session_state.pdf_gerado_sucesso and st.session_state.pdf_bytes_gerado is not None:
    st.success("PDF gerado com sucesso! Veja a prévia abaixo:")
    
    try:
        import fitz  
        doc = fitz.open(stream=st.session_state.pdf_bytes_gerado, filetype="pdf")
        for pagina_num in range(len(doc)):
            pagina = doc.load_page(pagina_num)
            pix = pagina.get_pixmap(dpi=130)  
            img_data = pix.tobytes("png")
            
            st.image(
                img_data, 
                caption=f"Página {pagina_num + 1} de {len(doc)}", 
                use_container_width=True
            )
            
    except ImportError:
        import base64
        base64_pdf = base64.b64encode(st.session_state.pdf_bytes_gerado).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600px" style="border:1px solid #ccc; border-radius:8px;"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    
    st.divider()
    st.download_button(
        label="⬇️ Baixar arquivo PDF Oficial",
        data=st.session_state.pdf_bytes_gerado,
        file_name=f"orcamento_ricex_{numero_orcamento or 'simulacao'}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

st.divider()
st.caption("Ricex Importação — Simulador interno. Valores sujeitos a variação cambial e condições comerciais no embarque.")
