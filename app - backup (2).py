"""
Simulador de Importação — Ricex
=================================
Aplicativo Streamlit para simular a importação de peças de vestuário,
replicando os cálculos e fórmulas das planilhas Fatto_a_Mano_1.xlsx e
Fatto_a_Mano_2.xlsx (câmbio, frete, II, IPI, PIS, COFINS, AFRMM, ICMS,
rateio proporcional por item, mark-up e cálculo reverso a partir do
preço de venda final).
"""
import plotly.graph_objects as go  # <-- ADICIONE ESTA LINHA NO TOPO DO SEU CODIGO
from pathlib import Path
import pandas as pd
import streamlit as st

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
    page_title="Ricex | Simulador de Importação",
    page_icon="📊",
    layout="wide",
)

init_db()


# ----------------------------------------------------------------------------
# Cabeçalho com logo + Reservas vazias (Empty) para o dashboard superior direito
# ----------------------------------------------------------------------------
# Ajustamos a proporção [1.0, 3.5, 4.0, 1.5] para dar mais espaço ao gráfico maior
col_logo, col_title, col_chart, col_metric = st.columns([1.0, 3.5, 4.0, 1.5])

with col_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=140)
        
with col_title:
    # Título reduzido para 28px para não quebrar a linha
    st.markdown("<h2 style='margin:0; padding:0; font-size: 28px;'>Simulador de Importação de Roupas</h2>", unsafe_allow_html=True)
    st.caption("Ricex Importação — custos, impostos, rateio e precificação da remessa")

# Containers vazios aguardando o cálculo da simulação
placeholder_chart = col_chart.empty()
placeholder_metric = col_metric.empty()

st.divider()


st.divider()


def _fmt_rs(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_pct(v: float) -> str:
    return f"{v * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


# ----------------------------------------------------------------------------
# 1. Parâmetros gerais da operação (câmbio, frete, impostos...)
# ----------------------------------------------------------------------------
st.header("1. Parâmetros gerais da operação")

params_db = obter_parametros_gerais()

with st.expander("Parâmetros de origem, frete e impostos", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        cambio = st.number_input("Câmbio (R$/US$)", min_value=0.0, value=float(params_db["cambio"]), step=0.001, format="%.4f")
        ii = st.number_input("II — Imposto de Importação (%)", min_value=0.0, max_value=200.0, value=float(params_db["ii"]) * 100, step=0.5) / 100
    with c2:
        frete_internacional = st.number_input("Frete internacional (US$) — total da remessa", min_value=0.0, value=float(params_db["frete_internacional"]), step=50.0)
        ipi = st.number_input("IPI (%)", min_value=0.0, max_value=200.0, value=float(params_db["ipi"]) * 100, step=0.5) / 100
    with c3:
        despesas_portuarias = st.number_input("Despesas portuárias (R$) — total da remessa", min_value=0.0, value=float(params_db["despesas_portuarias"]), step=500.0)
        pis = st.number_input("PIS-Importação (%)", min_value=0.0, max_value=100.0, value=float(params_db["pis"]) * 100, step=0.1) / 100
    with c4:
        icms = st.number_input("ICMS Importação (%, cálculo por dentro)", min_value=0.0, max_value=99.0, value=float(params_db["icms"]) * 100, step=0.5) / 100
        cofins = st.number_input("COFINS-Importação (%)", min_value=0.0, max_value=100.0, value=float(params_db["cofins"]) * 100, step=0.1) / 100

    afrmm = st.number_input("AFRMM — sobre o frete internacional (%)", min_value=0.0, max_value=100.0, value=float(params_db["afrmm"]) * 100, step=0.5) / 100

    bt_col1, bt_col2 = st.columns([1, 4])
    with bt_col1:
        if st.button("💾 Salvar como padrão"):
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
            st.success("Parâmetros salvos como padrão no banco de dados.")

st.divider()

# ----------------------------------------------------------------------------
# 2. Catálogo de produtos (SQLite) + seleção de itens
# ----------------------------------------------------------------------------
st.header("2. Seleção de produtos da remessa")

with st.expander("➕ Adicionar novo produto ao catálogo"):
    nc1, nc2, nc3, nc4, nc5 = st.columns([1, 2, 2, 1, 1])
    with nc1:
        novo_ref = st.text_input("Ref.", key="novo_ref")
    with nc2:
        novo_nome = st.text_input("Produto", key="novo_nome")
    with nc3:
        novo_comp = st.text_input("Composição", key="novo_comp")
    with nc4:
        novo_fob = st.number_input("FOB US$/un.", min_value=0.0, value=0.0, step=0.1, key="novo_fob")
    with nc5:
        novo_qtd = st.number_input("Qtd. padrão", min_value=1, value=1000, step=50, key="novo_qtd")
    if st.button("Adicionar produto"):
        if novo_ref and novo_nome and novo_fob > 0:
            try:
                adicionar_produto(novo_ref, novo_nome, novo_comp, novo_fob, int(novo_qtd))
                st.success(f"Produto '{novo_nome}' adicionado ao catálogo.")
                st.rerun()
            except Exception as e:
                st.error(f"Não foi possível adicionar: {e}")
        else:
            st.warning("Informe ao menos Ref., Produto e FOB US$/un.")

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
# 3. Modo de precificação (direto por markup, ou reverso a partir do preço final)
# ----------------------------------------------------------------------------
st.header("3. Quantidades, preços e modo de precificação")

modo_global = st.radio(
    "Modo de cálculo da precificação",
    options=["Definir markup (%) e calcular o preço de venda", "Definir o preço de venda final e calcular o markup resultante"],
    horizontal=False,
)
modo_calc = "markup" if modo_global.startswith("Definir markup") else "preco_final"

markup_global_pct = params_db.get("markup", 1.0) * 100
if modo_calc == "markup":
    markup_global_pct = st.slider("Markup padrão (%) aplicado a todos os itens — ajustável por item na tabela abaixo", 0, 300, int(markup_global_pct), step=5)

st.caption(
    "Edite diretamente a tabela: quantidade, preço FOB (US$/un.) e "
    + ("markup (%)" if modo_calc == "markup" else "preço de venda final (R$/un.)")
    + " de cada item."
)

linhas = []
for label in selecionados_labels:
    p = opcoes[label]
    linha = {
        "Ref.": p["ref"],
        "Produto": p["produto"],
        "Composição": p["composicao"],
        "Qtd.": int(p["qtd_padrao"]),
        "FOB US$/un.": float(p["fob_usd"]),
    }
    if modo_calc == "markup":
        linha["Markup (%)"] = markup_global_pct
    else:
        linha["Preço venda final R$/un."] = 0.0
    linhas.append(linha)

df_edit = pd.DataFrame(linhas)

col_config = {
    "Qtd.": st.column_config.NumberColumn(min_value=1, step=1),
    "FOB US$/un.": st.column_config.NumberColumn(min_value=0.0, step=0.1, format="%.2f"),
}
if modo_calc == "markup":
    col_config["Markup (%)"] = st.column_config.NumberColumn(min_value=0.0, max_value=500.0, step=5.0, format="%.1f")
else:
    col_config["Preço venda final R$/un."] = st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.2f")

df_edit = st.data_editor(
    df_edit,
    column_config=col_config,
    disabled=["Ref.", "Produto", "Composição"],
    hide_index=True,
    use_container_width=True,
)

itens_simulacao = []
for _, row in df_edit.iterrows():
    item = ItemSimulacao(
        ref=row["Ref."],
        produto=row["Produto"],
        composicao=row["Composição"],
        qtd=float(row["Qtd."]),
        fob_unit_usd=float(row["FOB US$/un."]),
        modo=modo_calc,
    )
    if modo_calc == "markup":
        item.markup = float(row["Markup (%)"]) / 100
    else:
        item.preco_venda_unit = float(row["Preço venda final R$/un."])
    itens_simulacao.append(item)

resultado = calcular_simulacao(
    itens=itens_simulacao,
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

# ----------------------------------------------------------------------------
# Preenchimento dinâmico do Dashboard Superior (Donut Chart e Card ROI)
# ----------------------------------------------------------------------------
with placeholder_chart:
    # Dados com as 3 métricas solicitadas
    labels = ['Custo Total', 'Lucro Estimado', 'Receita Total']
    values = [resultado.custo_total_rs, resultado.lucro_total_rs, resultado.receita_total_rs]
    
    # Formatação estrita no padrão brasileiro: XX.XXX,XX
    text_values = [f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") for v in values]

    fig = go.Figure(data=[go.Pie(
        labels=labels, 
        values=values, 
        hole=.5,
        marker=dict(colors=['#FF4B4B', '#00D48A', '#1F77B4']),
        showlegend=True,
        text=text_values,
        textinfo='label+text',    # Mostra o Nome + Valor formatado
        textposition='outside',   # Deixa os nomes totalmente visíveis do lado de fora
        hoverinfo='label+text'
    )])
    
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        height=180,               # Altura expandida para o gráfico ficar maior
        legend=dict(
            orientation="h",      # Legenda horizontal charmosa embaixo do gráfico
            yanchor="bottom",
            y=-0.5,
            xanchor="center",
            x=0.5
        )
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# Mantemos o cartão do ROI exatamente como você pediu para deixar
with placeholder_metric:
    st.metric(
        label="ROI da Remessa",
        value=f"{resultado.roi * 100:.2f}%",
        delta=f"Lucro: {_fmt_rs(resultado.lucro_total_rs)}",
        delta_color="normal"
    )


# ----------------------------------------------------------------------------
# 4. Resultado — custo geral da importação
# ----------------------------------------------------------------------------
st.header("4. Custo geral da importação")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total da invoice (US$)", f"US$ {resultado.total_invoice_usd:,.2f}")
m2.metric("Mercadoria (R$)", _fmt_rs(resultado.mercadoria_rs_total))
m3.metric("Valor aduaneiro (R$)", _fmt_rs(resultado.valor_aduaneiro_rs))
m4.metric("Custo geral importação (R$)", _fmt_rs(resultado.custo_geral_importacao_rs))

impostos_df = pd.DataFrame(
    {
        "Tributo/Encargo": ["II", "IPI", "PIS-Importação", "COFINS-Importação", "AFRMM", "ICMS Importação", "Despesas portuárias"],
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
impostos_df["Valor (R$)"] = impostos_df["Valor (R$)"].map(_fmt_rs)
st.dataframe(impostos_df, hide_index=True, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------------
# 5. Detalhamento por item (rateio proporcional) + precificação
# ----------------------------------------------------------------------------
st.header("5. Detalhamento por item e precificação final")

det_rows = []
for item in resultado.itens:
    det_rows.append(
        {
            "Produto": f"{item.ref} — {item.produto}",
            "Qtd.": int(item.qtd),
            "Valor US$": round(item.valor_usd, 2),
            "% Invoice": _fmt_pct(item.participacao),
            "Merc. R$": round(item.mercadoria_rs, 2),
            "Frete R$": round(item.frete_rs, 2),
            "II R$": round(item.ii_rs, 2),
            "PIS R$": round(item.pis_rs, 2),
            "COFINS R$": round(item.cofins_rs, 2),
            "AFRMM R$": round(item.afrmm_rs, 2),
            "ICMS R$": round(item.icms_rs, 2),
            "Desp. R$": round(item.despesas_rs, 2),
            "Custo Total R$": round(item.custo_total_rs, 2),
            "Custo R$/Un.": round(item.custo_unit_rs, 2),
            "Markup": _fmt_pct(item.markup),
            "Preço Venda R$/Un.": round(item.preco_venda_unit_calculado, 2),
            "Lucro Total R$": round(item.lucro_total_rs, 2),
        }
    )
st.dataframe(pd.DataFrame(det_rows), hide_index=True, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------------
# 6. Resumo financeiro
# ----------------------------------------------------------------------------
st.header("6. Resumo financeiro da remessa")

r1, r2, r3, r4 = st.columns(4)
r1.metric("Custo total (R$)", _fmt_rs(resultado.custo_total_rs))
r2.metric("Receita total estimada (R$)", _fmt_rs(resultado.receita_total_rs))
r3.metric("Lucro total estimado (R$)", _fmt_rs(resultado.lucro_total_rs))
r4.metric("ROI sobre o custo", _fmt_pct(resultado.roi))

st.subheader("💰 Preço final total da remessa")
st.markdown(
    f"<div style='background-color:#1b2a4a;color:white;padding:18px;border-radius:8px;"
    f"font-size:28px;font-weight:bold;text-align:center;'>{_fmt_rs(resultado.receita_total_rs)}</div>",
    unsafe_allow_html=True,
)

st.divider()

# ----------------------------------------------------------------------------
# 7. Geração de PDF
# ----------------------------------------------------------------------------
st.header("7. Gerar orçamento em PDF")

pc1, pc2 = st.columns(2)
with pc1:
    cliente_nome = st.text_input("Nome do cliente (opcional)")
with pc2:
    numero_orcamento = st.text_input("Número do orçamento (opcional)")
observacoes = st.text_area("Observações (opcional)", height=80)

if st.button("📄 Gerar PDF do orçamento", type="primary"):
    pdf_bytes = gerar_pdf_orcamento(
        resultado=resultado,
        logo_path=str(LOGO_PATH),
        cliente=cliente_nome,
        numero_orcamento=numero_orcamento,
        observacoes=observacoes,
    )
    st.success("PDF gerado com sucesso!")
    st.download_button(
        label="⬇️ Baixar orçamento em PDF",
        data=pdf_bytes,
        file_name=f"orcamento_ricex_{numero_orcamento or 'simulacao'}.pdf",
        mime="application/pdf",
    )

st.divider()
st.caption("Ricex Importação — Simulador interno. Valores sujeitos a variação cambial e condições comerciais no embarque.")

#%%

# cd "C:\Users\Luca Caruso\Desktop\Projetos\Case Ricex\Simulacao_Roupas\ricex_app"
# pip install -r requirements.txt
# streamlit run app.py


