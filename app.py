"""
Simulador de Importação — Ricex
=================================
Aplicativo Streamlit para simular a importação de produtos variados,
com opções dinâmicas de frete (Fatura ou Quantidade), parâmetros de venda
(ICMS de Venda, Marketing e Outros), e roteiro analítico dos cálculos.
"""
import base64
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


def _fmt_rs(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


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

with st.expander("➕ Adicionar novo produto ao catálogo"):
    nc1, nc2, nc3, nc4, nc5 = st.columns([1, 2, 2, 1, 1])
    with nc1:
        novo_ref = st.text_input("Ref.", key="novo_ref")
    with nc2:
        novo_nome = st.text_input("Produto", key="novo_nome")
    with nc3:
        novo_comp = st.text_input("Composição/Tipo", key="novo_comp")
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
# 2. Definição de Quantidades, Itens e Tipo de Frete
# ----------------------------------------------------------------------------
st.header("2. Quantidades, preços e parametrização do Frete")
st.caption("Defina o método de distribuição de frete por item: baseado no valor da FATURA ou proporcional à QUANTIDADE.")

linhas_itens = []
for label in selecionados_labels:
    p = opcoes[label]
    linhas_itens.append({
        "Ref.": p["ref"],
        "Produto": p["produto"],
        "Composição/Tipo": p["composicao"],
        "Qtd.": int(p["qtd_padrao"]),
        "FOB US$/un.": float(p["fob_usd"]),
        "Tipo de Frete": "Por Fatura"  # Opção inicial padrão
    })

df_itens_config = pd.DataFrame(linhas_itens)

col_config_itens = {
    "Qtd.": st.column_config.NumberColumn(min_value=1, step=1),
    "FOB US$/un.": st.column_config.NumberColumn(min_value=0.0, step=0.1, format="%.2f"),
    "Tipo de Frete": st.column_config.SelectboxColumn(
        options=["Por Fatura", "Por Quantidade"],
        required=True
    )
}

df_itens_editado = st.data_editor(
    df_itens_config,
    column_config=col_config_itens,
    disabled=["Ref.", "Produto", "Composição/Tipo"],
    hide_index=True,
    use_container_width=True,
    key="editor_itens_frete"
)

st.divider()


# ============================================================================
# 3. Processamento Inicial dos Custos de Importação (Nacionalização)
# ============================================================================
st.header("3. Custo geral da importação (Nacionalização)")

# Preparação dos dados para o motor de cálculos levando em consideração a divisão do frete personalizado
total_fob_fatura = 0.0
total_qtd_unidades = 0.0

for _, row in df_itens_editado.iterrows():
    total_fob_fatura += float(row["Qtd."]) * float(row["FOB US$/un."])
    total_qtd_unidades += float(row["Qtd."])

itens_pre_calculo = []
for _, row in df_itens_editado.iterrows():
    qtd = float(row["Qtd."])
    fob_unit = float(row["FOB US$/un."])
    fob_total_item = qtd * fob_unit
    
    # Aplicação da regra customizada de Frete por Item
    if row["Tipo de Frete"] == "Por Fatura" and total_fob_fatura > 0:
        fator_frete = fob_total_item / total_fob_fatura
    elif row["Tipo de Frete"] == "Por Quantidade" and total_qtd_unidades > 0:
        fator_frete = qtd / total_qtd_unidades
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
    # Atribuição temporária do frete customizado calculado
    item.frete_customizado_usd = frete_atribuido_usd
    itens_pre_calculo.append(item)

# ----------------------------------------------------------------------------
# Chamada Oficial do Motor de Cálculo (Gera a variável 'resultado')
# ----------------------------------------------------------------------------
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
m1.metric("Total da invoice (US$)", f"US$ {resultado.total_invoice_usd:,.2f}")
m2.metric("Mercadoria (R$)", _fmt_rs(resultado.mercadoria_rs_total))
m3.metric("Valor aduaneiro (R$)", _fmt_rs(resultado.valor_aduaneiro_rs))
m4.metric("Custo de Importação (R$)", _fmt_rs(resultado.custo_geral_importacao_rs))

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

# ----------------------------------------------------------------------------
# Recálculo Comercial Pós-Importação (Incluindo ICMS Venda e Outros Parâmetros)
# ----------------------------------------------------------------------------
det_rows = []
total_receita_simulada = 0.0
total_custo_comercial_total = 0.0

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
        if custo_base_unit > 0:
            mk_aplicado = margem_liquida_rs / custo_base_unit
        else:
            mk_aplicado = 0.0

    venda_total_item = preco_venda_unit * item.qtd
    icms_venda_rs = venda_total_item * icms_venda
    outros_custos_rs = venda_total_item * outros_custos_pct
    
    custo_total_comercial_item = item.custo_total_rs + icms_venda_rs + outros_custos_rs
    lucro_liquido_item = venda_total_item - custo_total_comercial_item
    
    total_receita_simulada += venda_total_item
    total_custo_comercial_total += custo_total_comercial_item
    
    det_rows.append({
        "Produto": f"{item.ref} — {item.produto}",
        "Qtd.": int(item.qtd),
        "Custo Nac. Un.": _fmt_rs(custo_base_unit),
        "Markup": _fmt_pct(mk_aplicado),
        "ICMS Venda": _fmt_rs(icms_venda_rs / item.qtd if item.qtd > 0 else 0),
        "Outros/Mkt": _fmt_rs(outros_custos_rs / item.qtd if item.qtd > 0 else 0),
        "Preço Venda Un.": round(preco_venda_unit, 2),
        "Faturamento Esperado": round(venda_total_item, 2),
        "Lucro Líquido": round(lucro_liquido_item, 2)
    })

df_detalhado_final = pd.DataFrame(det_rows)

st.subheader("📋 Tabela Consolidada de Distribuição Comercial por Item")
st.dataframe(df_detalhado_final, hide_index=True, use_container_width=True)

# Atualização dos KPI Globais no Topo do Dashboard dinamicamente
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
r1.metric("Custo Total Acumulado (R$)", _fmt_rs(total_custo_comercial_total))
r2.metric("Receita Total Bruta (R$)", _fmt_rs(total_receita_simulada))
r3.metric("Lucro Líquido Final (R$)", _fmt_rs(lucro_global_calculado))
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

1. **Formação do Valor Aduaneiro**: Para cada item, calcula-se o valor **FOB Unitário** nacionalizado (multiplicado pelo câmbio informado e pela quantidade). Soma-se a isso a cota correspondente do **Frete Internacional** calculada dinamicamente com base nas regras de rateio escolhidas (proporcional ao valor da *Fatura* ou proporcional ao volume de *Quantidade*).
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

# Inicializa as variáveis de memória do Streamlit se elas não existirem
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

# Botão principal que dispara a geração pesada na memória
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
    
    # Salva o arquivo gerado na memória global do Streamlit para não sumir no reload
    st.session_state.pdf_bytes_gerado = bytes_temp
    st.session_state.pdf_gerado_sucesso = True

# Bloco de Renderização Persistente (Executa fora do clique do botão)
if st.session_state.pdf_gerado_sucesso and st.session_state.pdf_bytes_gerado is not None:
    st.success("PDF gerado com sucesso! Veja a prévia abaixo:")
    
    try:
        import fitz  # PyMuPDF
        
        # Carrega o PDF a partir da memória salva no session_state
        doc = fitz.open(stream=st.session_state.pdf_bytes_gerado, filetype="pdf")
        
        # Renderiza as páginas na tela de forma contínua
        for pagina_num in range(len(doc)):
            pagina = doc.load_page(pagina_num)
            pix = pagina.get_pixmap(dpi=130)  # Resolução otimizada para web
            img_data = pix.tobytes("png")
            
            st.image(
                img_data, 
                caption=f"Página {pagina_num + 1} de {len(doc)}", 
                use_container_width=True
            )
            
    except ImportError:
        # Fallback de segurança caso o PyMuPDF não esteja instalado no ambiente correto
        import base64
        base64_pdf = base64.b64encode(st.session_state.pdf_bytes_gerado).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600px" style="border:1px solid #ccc; border-radius:8px;"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    
    st.divider()
    # O botão de baixar lê os dados diretamente do cache da memória estável
    st.download_button(
        label="⬇️ Baixar arquivo PDF Oficial",
        data=st.session_state.pdf_bytes_gerado,
        file_name=f"orcamento_ricex_{numero_orcamento or 'simulacao'}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

st.divider()
st.caption("Ricex Importação — Simulador interno. Valores sujeitos a variação cambial e condições comerciais no embarque.")


#%%
# pip install pymupdf


#%%

# cd "C:\Users\Luca Caruso\Desktop\Projetos\Case Ricex\Simulacao_Roupas\ricex_app"
# pip install -r requirements.txt
# streamlit run app.py











