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
    remover_produto,
    salvar_modelo_simulacao,
    listar_modelos_simulacao,
    carrega_modelo_simulacao,
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

# Inicializa o banco de dados e sincroniza silenciosamente com o database_new.xlsx superior
init_db()

# ----------------------------------------------------------------------------
# Inicialização e Controle do Session State para Restauração dos Cenários
# ----------------------------------------------------------------------------
params_db = obter_parametros_gerais()

if "cambio" not in st.session_state:
    st.session_state["cambio"] = float(params_db.get("cambio", 5.144))
if "frete_internacional" not in st.session_state:
    st.session_state["frete_internacional"] = float(params_db.get("frete_internacional", 5100.0))
if "despesas_portuarias" not in st.session_state:
    st.session_state["despesas_portuarias"] = float(params_db.get("despesas_portuarias", 15000.0))
if "ii" not in st.session_state:
    st.session_state["ii"] = float(params_db.get("ii", 0.35)) * 100
if "ipi" not in st.session_state:
    st.session_state["ipi"] = float(params_db.get("ipi", 0.0)) * 100
if "pis" not in st.session_state:
    st.session_state["pis"] = float(params_db.get("pis", 0.021)) * 100
if "cofins" not in st.session_state:
    # Corrigido para carregar do banco de dados com segurança no início do app
    st.session_state["cofins"] = float(params_db.get("cofins", 0.0965)) * 100
if "icms" not in st.session_state:
    st.session_state["icms"] = float(params_db.get("icms", 0.14)) * 100
if "afrmm" not in st.session_state:
    st.session_state["afrmm"] = float(params_db.get("afrmm", 0.08)) * 100
if "icms_venda" not in st.session_state:
    st.session_state["icms_venda"] = 18.0
if "outros_custos_pct" not in st.session_state:
    st.session_state["outros_custos_pct"] = 5.0
if "tipo_frete_global" not in st.session_state:
    st.session_state["tipo_frete_global"] = "Por Fatura (Proporcional ao valor em US$)"

# --- ACRESCENTADO: Inicialização segura das variáveis de controle do PDF ---
if "pdf_bytes_gerado" not in st.session_state:
    st.session_state["pdf_bytes_gerado"] = None
if "pdf_gerado_sucesso" not in st.session_state:
    st.session_state["pdf_gerado_sucesso"] = False

# ----------------------------------------------------------------------------
# Cabeçalho com logo + Reservas vazias (Empty) para o dashboard superior direito
# ----------------------------------------------------------------------------
col_logo, col_title, col_chart, col_metric = st.columns([1.0, 2.5, 3.5, 3.0])


with col_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=140)
        
with col_title:
    st.markdown("<h2 style='margin:0; padding:0; font-size: 28px;'>Simulador de Importação Multiprojetos</h2>", unsafe_allow_html=True)
    st.caption("Ricex Importação — custos, impostos, rateio e precificação analítica")

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


# ============================================================================
#%% PASSO PRÉVIO: GERENCIADOR DE PASTAS (Executado antes de carregar os componentes de tela)
# ============================================================================


# Inicializa uma chave de controle para forçar o redesenho dos inputs quando uma pasta for aberta
if "reset_widgets_key" not in st.session_state:
    st.session_state["reset_widgets_key"] = 0

st.header("📂 Gerenciador de Pastas de Simulação")
modelos_disponiveis = listar_modelos_simulacao()

if modelos_disponiveis:
    opcoes_modelos = {"--- Selecione um modelo salvo para aplicar ---": None}
    for m in modelos_disponiveis:
        opcoes_modelos[f"{m['nome_simulacao']} ({m['data_criacao']})"] = m['id']
        
    modelo_selecionado = st.selectbox("Pastas e Modelos Antigos:", options=list(opcoes_modelos.keys()))
    id_modelo = opcoes_modelos[modelo_selecionado]
    
    if id_modelo:
        col_btn1, col_btn2, _ = st.columns([2.5, 2.5, 5.0])
        
        with col_btn1:
            if st.button("📂 Aplicar Cenário Selecionado", use_container_width=True):
                params_rec, itens_rec = carrega_modelo_simulacao(id_modelo)
                if params_rec:
                    # 1. Sobrescreve TODOS os estados do Session State com os dados gravados na pasta
                    st.session_state["cambio"] = float(params_rec.get("cambio", 5.144))
                    st.session_state["frete_internacional"] = float(params_rec.get("frete_internacional", 5100.0))
                    st.session_state["despesas_portuarias"] = float(params_rec.get("despesas_portuarias", 15000.0))
                    st.session_state["ii"] = float(params_rec.get("ii", 0.35)) * 100
                    st.session_state["ipi"] = float(params_rec.get("ipi", 0.0)) * 100
                    st.session_state["pis"] = float(params_rec.get("pis", 0.021)) * 100
                    st.session_state["cofins"] = float(params_rec.get("cofins", 0.0965)) * 100
                    st.session_state["icms"] = float(params_rec.get("icms", 0.14)) * 100
                    st.session_state["afrmm"] = float(params_rec.get("afrmm", 0.08)) * 100
                    st.session_state["icms_venda"] = float(params_rec.get("icms_venda", 0.18) if params_rec.get("icms_venda", 18.0) < 1.0 else params_rec.get("icms_venda", 18.0))
                    st.session_state["outros_custos_pct"] = float(params_rec.get("outros_custos_pct", 0.05) if params_rec.get("outros_custos_pct", 5.0) < 1.0 else params_rec.get("outros_custos_pct", 5.0))
                    st.session_state["tipo_frete_global"] = params_rec.get("tipo_frete", "Por Fatura (Proporcional ao valor em US$)")
                    st.session_state["modelo_carregado_itens"] = itens_rec
                    
                    # Salva o markup customizado da simulação para a tabela 4 ler
                    if "markup" in params_rec:
                        st.session_state["markup_salvo_pasta"] = float(params_rec.get("markup"))
                    
                    # 2. Força o Streamlit a destruir os inputs antigos e redesenhar com os valores da pasta
                    st.session_state["reset_widgets_key"] += 1
                    
                    st.success("Cenário preparado!")
                    st.rerun()
                    
        with col_btn2:
            if st.button("❌ Excluir Pasta / Modelo", type="secondary", use_container_width=True):
                from database import get_connection
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("DELETE FROM simulacoes_salvas WHERE id = ?", (id_modelo,))
                    conn.commit()
                    conn.close()
                    st.toast("Pasta removida permanentemente do histórico!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao deletar: {e}")
else:
    st.info("Nenhuma pasta de simulação foi salva ainda.")

st.divider()

# Sufixo dinâmico para forçar renderização limpa
w_key = f"_v{st.session_state['reset_widgets_key']}"

with st.sidebar:
    st.header("⚙️ Parâmetros da Operação")
    st.caption("Altere os valores da remessa e impostos abaixo:")
    
    cambio = st.number_input("Câmbio (R$/US$)", min_value=0.0, key=f"cambio{w_key}", value=st.session_state["cambio"], step=0.001, format="%.4f")
    frete_internacional = st.number_input("Frete internacional total (US$)", min_value=0.0, key=f"frete_internacional{w_key}", value=st.session_state["frete_internacional"], step=50.0)
    despesas_portuarias = st.number_input("Despesas portuárias (R$)", min_value=0.0, key=f"despesas_portuarias{w_key}", value=st.session_state["despesas_portuarias"], step=500.0)
    
    st.divider()
    st.subheader("Impostos de Importação")
    
    ii_input = st.number_input("II — Imposto de Importação (%)", min_value=0.0, max_value=200.0, key=f"ii{w_key}", value=st.session_state["ii"], step=0.5)
    ii_val = ii_input / 100

    ipi_input = st.number_input("IPI (%)", min_value=0.0, max_value=200.0, key=f"ipi{w_key}", value=st.session_state["ipi"], step=0.5)
    ipi_val = ipi_input / 100

    pis_input = st.number_input("PIS-Importação (%)", min_value=0.0, max_value=100.0, key=f"pis{w_key}", value=st.session_state["pis"], step=0.1)
    pis_val = pis_input / 100

    cofins_input = st.number_input("COFINS-Importação (%)", min_value=0.0, max_value=100.0, key=f"cofins{w_key}", value=st.session_state["cofins"], step=0.1)
    cofins_val = cofins_input / 100

    icms_input = st.number_input("ICMS Importação (por dentro %)", min_value=0.0, max_value=99.0, key=f"icms{w_key}", value=st.session_state["icms"], step=0.5)
    icms_val = icms_input / 100

    afrmm_input = st.number_input("AFRMM (sobre frete %)", min_value=0.0, max_value=100.0, key=f"afrmm{w_key}", value=st.session_state["afrmm"], step=0.5)
    afrmm_val = afrmm_input / 100

    st.divider()
    st.subheader("📊 Parâmetros Comerciais e de Venda")
    
    icms_venda_input = st.number_input("ICMS da Venda Simulada (%)", min_value=0.0, max_value=100.0, key=f"icms_venda{w_key}", value=st.session_state["icms_venda"], step=0.5)
    icms_venda_val = icms_venda_input / 100
    
    outros_custos_input = st.number_input("Outros (Mkt, Propaganda, etc. %)", min_value=0.0, max_value=100.0, key=f"outros_custos_pct{w_key}", value=st.session_state["outros_custos_pct"], step=0.5)
    outros_custos_pct_val = outros_custos_input / 100

    st.sidebar.divider()
    if st.button("💾 Salvar como padrão", use_container_width=True):
        salvar_parametros_gerais(
            {
                "cambio": cambio, "frete_internacional": frete_internacional, "despesas_portuarias": despesas_portuarias,
                "ii": ii_val, "ipi": ipi_val, "pis": pis_val, "cofins": cofins_val, "afrmm": afrmm_val, "icms": icms_val,
                "markup": params_db.get("markup", 1.0),
            }
        )
        st.success("Parâmetros salvos com padrão!")

# ----------------------------------------------------------------------------
# % % 1. Catálogo de produtos (SQLite) + seleção de itens
# ----------------------------------------------------------------------------
st.header("1. Seleção de produtos da remessa")

# --- ADICIONADO: Expander para recolher o gerenciamento do catálogo ---
with st.expander("⚙️ Adicionar / Remover Produtos", expanded=False):
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
                    
                    # MODIFICADO: Filtra apenas referências numéricas que tenham até 4 dígitos (<= 9999)
                    refs_existentes = [
                        int(p["ref"]) for p in produtos_existentes 
                        if p["ref"].isdigit() and len(p["ref"]) <= 4
                    ]
                    
                    # Se houver alguma referência de até 4 dígitos, pega o maior e soma 1. Caso contrário, começa em 1000.
                    novo_ref = str(max(refs_existentes) + 1) if refs_existentes else "1000"
                except:
                    novo_ref = str(random.randint(1000, 9999))

            if novo_nome and novo_fob > 0:
                try:
                    adicionar_produto(novo_ref, novo_nome, novo_comp, novo_fob, int(novo_qtd))
                    st.success(f"Produto {novo_nome} adicionado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Não foi possível adicionar: {e}")


    with aba_remover:
        produtos_db_remover = listar_produtos(somente_ativos=True)
        if produtos_db_remover:
            opcoes_remover = {f"{p['ref']} — {p['produto']}": p["id"] for p in produtos_db_remover}
            produto_para_remover = st.selectbox(
                "Selecione o produto que deseja excluir do catálogo:",
                options=list(opcoes_remover.keys())
            )
            if st.button("Remover Produto"):
                remover_produto(opcoes_remover[produto_para_remover])
                st.success("Produto desativado com sucesso!")
                st.rerun()
        else:
            st.info("Não há produtos ativos no catálogo para remover.")
# ----------------------------------------------------------------------

# O restante do código (Multiselect) fica FORA do expander para estar sempre visível
produtos_db = listar_produtos()
opcoes = {f"{p['ref']} — {p['produto']}": p for p in produtos_db}

default_selection = None
if "modelo_carregado_itens" in st.session_state:
    refs_salvas = [it["Ref."] for it in st.session_state["modelo_carregado_itens"]]
    default_selection = [lbl for lbl, p in opcoes.items() if p["ref"] in refs_salvas]

selecionados_labels = st.multiselect(
    "Escolha os produtos que farão parte desta remessa",
    options=list(opcoes.keys()),
    default=default_selection if default_selection else list(opcoes.keys())[:7] if len(opcoes) >= 7 else list(opcoes.keys()),
)

if not selecionados_labels:
    st.info("Selecione ao menos um produto para simular a importação.")
    st.stop()

st.divider()


# ----------------------------------------------------------------------------
#%% 2. Definição de Quantidades, Itens e Tipo de Frete (Fatura vs Peso)
# ----------------------------------------------------------------------------
st.header("2. Quantidades, preços e parametrização do Frete")

default_frete_options = ["Por Fatura (Proporcional ao valor em US$)", "Por Quantidade / Peso (Proporcional ao quilo/volume)"]
default_frete_idx = 0
if st.session_state["tipo_frete_global"] in default_frete_options:
    default_frete_idx = default_frete_options.index(st.session_state["tipo_frete_global"])

tipo_frete_global = st.radio(
    "Defina o método de distribuição do frete para toda a remessa:",
    options=default_frete_options,
    horizontal=True,
    index=default_frete_idx
)

st.session_state["tipo_frete_global"] = tipo_frete_global
is_frete_quantidade = "Quantidade" in tipo_frete_global

linhas_itens = []
for label in selecionados_labels:
    p = opcoes[label]
    
    qtd_inicial = int(p["qtd_padrao"])
    peso_inicial = 1.0
    if "modelo_carregado_itens" in st.session_state:
        match_salvo = next((it for it in st.session_state["modelo_carregado_itens"] if it["Ref."] == p["ref"]), None)
        if match_salvo:
            qtd_inicial = int(match_salvo.get("Qtd.", qtd_inicial))
            peso_inicial = float(match_salvo.get("Peso Unit. (kg)", peso_inicial))

    item_dict = {
        "Ref.": p["ref"], "Produto": p["produto"], "Composição/Tipo": p["composicao"],
        "Qtd.": qtd_inicial, "FOB US$/un.": float(p["fob_usd"]),
    }
    if is_frete_quantidade:
        item_dict["Peso Unit. (kg)"] = peso_inicial  
    linhas_itens.append(item_dict)

df_itens_config = pd.DataFrame(linhas_itens)

col_config_itens = {
    "Qtd.": st.column_config.NumberColumn(min_value=1, step=1),
    "FOB US$/un.": st.column_config.NumberColumn(min_value=0.0, step=0.1, format="US$ %.2f"),
}
if is_frete_quantidade:
    col_config_itens["Peso Unit. (kg)"] = st.column_config.NumberColumn(min_value=0.01, step=0.1, format="%.2f kg")

df_itens_editado = st.data_editor(
    df_itens_config, column_config=col_config_itens, disabled=["Ref.", "Produto", "Composição/Tipo"],
    hide_index=True, use_container_width=True, key="editor_itens_frete"
)

total_qtd_t2 = df_itens_editado["Qtd."].sum()
total_fob_t2 = (df_itens_editado["Qtd."] * df_itens_editado["FOB US$/un."]).sum()

if is_frete_quantidade:
    total_peso_t2 = (df_itens_editado["Qtd."] * df_itens_editado["Peso Unit. (kg)"]).sum()
    st.markdown(f"📊 **SOMA** — Quantidade Total: **{_fmt_qtd(int(total_qtd_t2))}** | FOB Total: **{_fmt_usd(total_fob_t2)}** | Peso Total: **{total_peso_t2:,.2f} kg**")
else:
    st.markdown(f"📊 **SOMA** — Quantidade Total: **{_fmt_qtd(int(total_qtd_t2))}** | FOB Total: **{_fmt_usd(total_fob_t2)}**")

st.divider()


# ============================================================================
#%% 3. Processamento Inicial dos Custos de Importação (Nacionalização)
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
    
    if not is_frete_quantidade and total_fob_fatura > 0:
        fator_frete = fob_total_item / total_fob_fatura
    elif is_frete_quantidade and total_peso_acumulado > 0:
        item_peso_total = qtd * float(row["Peso Unit. (kg)"])
        fator_frete = item_peso_total / total_peso_acumulado
    else:
        fator_frete = 1.0 / len(df_itens_editado)
        
    frete_atribuido_usd = frete_internacional * fator_frete
    
    item = ItemSimulacao(
        ref=row["Ref."], produto=row["Produto"], composicao=row["Composição/Tipo"],
        qtd=qtd, fob_unit_usd=fob_unit, modo="markup" 
    )
    item.frete_customizado_usd = frete_atribuido_usd
    itens_pre_calculo.append(item)

resultado = calcular_simulacao(
    itens=itens_pre_calculo, cambio=cambio, frete_internacional_usd=frete_internacional,
    despesas_portuarias_rs=despesas_portuarias, ii=ii_val, ipi=ipi_val, pis=pis_val, cofins=cofins_val, afrmm=afrmm_val, icms=icms_val,
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total da invoice (US$)", _fmt_usd(resultado.total_invoice_usd))
m2.metric("Mercadoria (R$)", _fmt_rs(resultado.mercadoria_rs_total))
m3.metric("Valor aduaneiro (R$)", _fmt_rs(resultado.valor_aduaneiro_rs))
m4.metric("Custo de Importação (R$)", _fmt_rs(resultado.custo_geral_importacao_rs))

# Modificação no Passo 3 para exibir o valor das Despesas Portuárias no nome do encargo
impostos_df = pd.DataFrame({
    "Tributo/Encargo": [
        f"II ({_fmt_pct(ii_val)})", 
        f"IPI ({_fmt_pct(ipi_val)})", 
        f"PIS-Importação ({_fmt_pct(pis_val)})", 
        f"COFINS-Importação ({_fmt_pct(cofins_val)})", 
        f"AFRMM ({_fmt_pct(afrmm_val)})", 
        f"ICMS Importação ({_fmt_pct(icms_val)})", 
        f"Despesas portuárias ({_fmt_rs(despesas_portuarias)})"  # <-- ATUALIZADO
    ],
    "Valor (R$)": [
        resultado.ii_rs_total, 
        resultado.ipi_rs_total, 
        resultado.pis_rs_total, 
        resultado.cofins_rs_total, 
        resultado.afrmm_rs_total, 
        resultado.icms_rs_total, 
        resultado.despesas_portuarias_rs
    ]
})

soma_impostos = impostos_df["Valor (R$)"].sum()

df_impostos_render = impostos_df.copy()
df_impostos_render["Valor (R$)"] = df_impostos_render["Valor (R$)"].map(_fmt_rs)
st.dataframe(df_impostos_render, hide_index=True, use_container_width=True)

st.markdown(f"💰 **SOMA** — Total de Tributos/Encargos: **{_fmt_rs(soma_impostos)}**")

st.divider()


# ============================================================================
# ============================================================================
# 4. Precificação Final Comercial (Markup e Impostos de Venda)
# ============================================================================
st.header("4. Precificação Final Comercial (Markup e Impostos de Venda)")

modo_global = st.radio("Modo de cálculo comercial", options=["Definir markup (%) e simular o preço de venda final", "Definir o preço de venda final e extrair o markup"], horizontal=True)
modo_calc = "markup" if modo_global.startswith("Definir markup") else "preco_final"

# [CORRIGIDO] Força a leitura do valor da pasta e injeta a chave dinâmica w_key para o slider redesenhar na tela
markup_global_pct = st.session_state.get("markup_salvo_pasta", params_db.get("markup", 1.0) * 100)
if modo_calc == "markup":
    markup_global_pct = st.slider("Markup padrão (%) aplicado aos itens", 0, 300, int(markup_global_pct), step=5, key=f"markup_slider{w_key}")

linhas_precificacao = []
for item in resultado.itens:
    linha = {"Ref.": item.ref, "Produto": item.produto, "Custo Nacionalizado Unit.": round(item.custo_unit_rs, 2)}
    if modo_calc == "markup":
        linha["Markup (%)"] = float(markup_global_pct)
    else:
        linha["Preço Venda Final Requerido (R$)"] = round(item.custo_unit_rs * 2.0, 2)
    linhas_precificacao.append(linha)

# --- VISUALIZAÇÃO ATUALIZADA DO PASSO 4: Gráfico de Barras Empilhadas (Stacked) ---
linhas_precificacao = []
for item in resultado.itens:
    custo_base_unit = item.custo_unit_rs
    
    if modo_calc == "markup":
        mk_aplicado = float(markup_global_pct) / 100
        divisor = 1.0 - (icms_venda_val + outros_custos_pct_val)
        preco_venda_unit = (custo_base_unit * (1 + mk_aplicado)) / divisor if divisor > 0 else custo_base_unit * (1 + mk_aplicado)
    else:
        preco_venda_unit = round(custo_base_unit * 2.0, 2)
    
    margem_comercial_unit = max(0.0, preco_venda_unit - custo_base_unit)

    linhas_precificacao.append({
        "Ref.": item.ref, 
        "Produto": item.produto, 
        "Identificador": f"{item.ref} — {item.produto}",
        "Custo Nacionalizado Unit.": round(custo_base_unit, 2),
        "Margem Comercial Unit.": round(margem_comercial_unit, 2),
        "Preço Venda Unit.": round(preco_venda_unit, 2),
        "Markup (%)": float(markup_global_pct) if modo_calc == "markup" else 100.0
    })

df_base_prec = pd.DataFrame(linhas_precificacao)

# Construção do gráfico de barras
fig_barras = go.Figure()

# 1ª Camada: Custo Nacionalizado
fig_barras.add_trace(go.Bar(
    y=df_base_prec["Identificador"],
    x=df_base_prec["Custo Nacionalizado Unit."],
    name="Custo Nacionalizado",
    orientation='h',
    marker_color='#1b2a4a', 
    text=df_base_prec["Custo Nacionalizado Unit."].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")),
    textposition='inside',
    insidetextanchor='middle',
    textfont=dict(color='white'), # Fonte branca para o custo interno
    hovertemplate="<b>%{y}</b><br>Custo Nacionalizado: R$ %{x:,.2f}<extra></extra>"
))

# 2ª Camada: Acréscimo Comercial (Verde Água Escurecido + Texto Branco + Rótulo Externo)
fig_barras.add_trace(go.Bar(
    y=df_base_prec["Identificador"],
    x=df_base_prec["Margem Comercial Unit."],
    name="Margem + Impostos de Venda",
    orientation='h',
    marker_color='#00A877', # ATUALIZADO: Verde água mais escuro para melhor legibilidade
    text=df_base_prec["Markup (%)"].apply(lambda x: f"Markup {x:.0f}%"),
    textposition='inside',
    insidetextanchor='middle',
    textfont=dict(color='white'), # ATUALIZADO: Fonte rigorosamente em branco dentro do verde
    hovertemplate="<b>%{y}</b><br>Margem Comercial: R$ %{x:,.2f}<extra></extra>"
))

# 3ª Camada Invisível (Apenas para fixar o rótulo externo "Preço Venda: R$ XX,XX" sem quebrar o empilhamento)
fig_barras.add_trace(go.Bar(
    y=df_base_prec["Identificador"],
    x=[0.001] * len(df_base_prec), # Tamanho quase nulo para servir apenas de âncora na ponta
    orientation='h',
    showlegend=False,
    marker=dict(color='rgba(0,0,0,0)'), # Totalmente transparente
    # ATUALIZADO: Exibe o texto estático "Preço Venda: R$ XX,XX" colado no final da barra verde
    text=df_base_prec["Preço Venda Unit."].apply(lambda x: f" Preço Venda: R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")),
    textposition='outside', 
    hoverinfo='skip'
))

# --- AJUSTE DE LAYOUT PARA NÃO CORTAR O TEXTO ---

# 1. Encontra o maior preço de venda para calcular um fôlego no eixo X
maior_preco = float(df_base_prec["Preço Venda Unit."].max()) if not df_base_prec.empty else 100.0

fig_barras.update_layout(
    title="Composição do Preço de Venda Final (Custo vs. Formação de Margem)",
    xaxis_title="Valor por Unidade (R$)",
    # Define manualmente o limite do eixo X com 25% de folga para o rótulo caber perfeitamente
    xaxis=dict(range=[0, maior_preco * 1.25]), 
    barmode='stack', 
    legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5),
    yaxis=dict(autorange="reversed"), 
    margin=dict(l=10, r=20, t=40, b=80), # Margem direita reduzida pois a folga agora está no próprio eixo X
    height=120 + (len(df_base_prec) * 38), 
)

# Garante que o texto fora da barra possa ser desenhado além da linha do gráfico sem ser clipado (cortado)
fig_barras.update_traces(cliponaxis=False)

st.plotly_chart(fig_barras, use_container_width=True, config={'displayModeBar': False})


# Bloco Final de Compatibilidade com o restante das tabelas do app
if modo_calc == "markup":
    df_prec_editado = df_base_prec[["Ref.", "Produto", "Custo Nacionalizado Unit.", "Markup (%)"]].copy()
else:
    df_prec_editado = df_base_prec.rename(columns={"Preço Venda Unit.": "Preço Venda Final Requerido (R$)"})
# --------------------------------------------------------------------------------


# Recálculo Comercial Pós-Importação
det_rows = []
total_receita_simulada = 0.0
total_custo_comercial_total = 0.0

for idx, item in enumerate(resultado.itens):
    row_edit = df_prec_editado.iloc[idx]
    custo_base_unit = item.custo_unit_rs
    
    if modo_calc == "markup":
        mk_aplicado = float(row_edit["Markup (%)"]) / 100
        divisor = 1.0 - (icms_venda_val + outros_custos_pct_val)
        preco_venda_unit = (custo_base_unit * (1 + mk_aplicado)) / divisor if divisor > 0 else custo_base_unit * (1 + mk_aplicado)
    else:
        preco_venda_unit = float(row_edit["Preço Venda Final Requerido (R$)"])
        margem_liquida_rs = (preco_venda_unit * (1.0 - icms_venda_val - outros_custos_pct_val)) - custo_base_unit
        mk_aplicado = (margem_liquida_rs / custo_base_unit) if custo_base_unit > 0 else 0.0

    venda_total_item = preco_venda_unit * item.qtd
    icms_venda_rs = venda_total_item * icms_venda_val
    outros_custos_rs = venda_total_item * outros_custos_pct_val
    custo_total_comercial_item = item.custo_total_rs + icms_venda_rs + outros_custos_rs
    lucro_liquido_item = venda_total_item - custo_total_comercial_item
    
    total_receita_simulada += venda_total_item
    total_custo_comercial_total += custo_total_comercial_item
    
    det_rows.append({
        "Produto": f"{item.ref} — {item.produto}", "Qtd.": int(item.qtd), "Custo Nac. Un.": custo_base_unit,
        "Markup": mk_aplicado, "Preço Venda Un.": preco_venda_unit, "Faturamento Esperado": venda_total_item, "Lucro Líquido": lucro_liquido_item
    })

df_detalhado_final = pd.DataFrame(det_rows)
st.subheader("📋 Tabela Consolidada de Distribuição Comercial por Item")

df_det_render = df_detalhado_final.copy()
df_det_render["Custo Nac. Un."] = df_det_render["Custo Nac. Un."].map(_fmt_rs)
df_det_render["Markup"] = df_det_render["Markup"].map(_fmt_pct)
df_det_render["Preço Venda Un."] = df_det_render["Preço Venda Un."].map(_fmt_rs)
df_det_render["Faturamento Esperado"] = df_det_render["Faturamento Esperado"].map(_fmt_rs)
df_det_render["Lucro Líquido"] = df_det_render["Lucro Líquido"].map(_fmt_rs)

st.dataframe(df_det_render, hide_index=True, use_container_width=True)

lucro_global_calculado = total_receita_simulada - total_custo_comercial_total
roi_global_calculado = (lucro_global_calculado / total_custo_comercial_total) if total_custo_comercial_total > 0 else 0.0

# ----------------------------------------------------------------------------
# Atualização dos gráficos de rosca e blocos de KPI originais (Topo da página)
# ----------------------------------------------------------------------------
with placeholder_chart:
    labels_pie = ['Custo de Importação<br>+ Comercial', 'Lucro Líquido Estimado']
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
    # Simulação visual perfeita do st.metric com quebra de linha livre para o Markup
    # Alterado font-weight do valor do ROI para 400 para remover o negrito
    html_metric = f"""
    <div style="font-family: sans-serif;">
        <span style="font-size: 14px; color: #555; font-weight: 400;">ROI Real da Operação</span>
        <div style="font-size: 36px; font-weight: 400; color: #111; margin: 4px 0;">{roi_global_calculado * 100:.2f}%</div>
        <div style="background-color: #e8f8f2; color: #008a57; padding: 4px 10px; border-radius: 20px; display: inline-block; font-size: 14px; font-weight: 500;">
            📈 ↑ Lucro: {_fmt_rs(lucro_global_calculado)}<br>
            📊 Markup Selecionado: {markup_global_pct:.1f}%
        </div>
    </div>
    """
    st.markdown(html_metric, unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Interface de salvamento do modelo de simulação em pasta
# ----------------------------------------------------------------------------
st.header("💾 Salvar esta Simulação em uma Pasta")
nome_da_pasta = st.text_input("Dê um nome para a sua pasta de simulação:", placeholder="Ex: Planejamento Coleção Lote 01")

if st.button("💾 Salvar Pasta de Simulação", type="primary"):
    if nome_da_pasta.strip():
        # [RESOLVIDO] Injetando a variável do markup atual para salvar fisicamente no registro do banco
        payload_params = {
            "cambio": cambio, "frete_internacional": frete_internacional, "despesas_portuarias": despesas_portuarias,
            "ii": ii_val, "ipi": ipi_val, "pis": pis_val, "cofins": cofins_val, "icms": icms_val, "afrmm": afrmm_val,
            "icms_venda": icms_venda_val,
            "outros_custos_pct": outros_custos_pct_val,
            "tipo_frete": tipo_frete_global,
            "markup": markup_global_pct  # Adicionado o markup do slider no pacote da pasta
        }
        payload_itens = df_itens_editado.to_dict(orient="records")
        
        salvar_modelo_simulacao(nome_da_pasta, payload_params, payload_itens)
        st.success(f"Simulação '{nome_da_pasta}' arquivada com sucesso com TODOS os parâmetros e markup salvos!")
        st.rerun()
    else:
        st.warning("Insira um nome válido para conseguir salvar a pasta.")


st.divider()

# ============================================================================
#%% 5. Resumo Financeiro Consolidado da Remessa
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

# ============================================================================

# %% 6. Geração e Prévia de PDF (VISUALIZADOR CORRIGIDO E RESTAURADO)
# ============================================================================
# ============================================================================
# %% 6. Geração e Prévia de PDF (VISUALIZADOR CORRIGIDO E RESTAURADO)
# ============================================================================
st.header("6. Gerar e Visualizar Orçamento em PDF")

pc1, pc2 = st.columns(2)
with pc1:
    cliente_nome = st.text_input("Nome do cliente (opcional)", key="pdf_cliente")
with pc2:
    numero_orcamento = st.text_input("Número do orçamento (opcional)", key="pdf_numero")
observacoes = st.text_area("Observações do Orçamento (opcional)", height=80, key="pdf_obs")

if st.button("📄 Gerar e Visualizar PDF"):
    import copy
    # 1. Criamos um clone do resultado para não estragar a memória da tela
    resultado_pdf = copy.deepcopy(resultado)
    
    # 2. Varre cada item e força o objeto a recalcular e gravar o markup/preço final selecionados na tela
    for idx, item in enumerate(resultado_pdf.itens):
        row_edit = df_prec_editado.iloc[idx]
        
        if modo_calc == "markup":
            # Puxa os 40% (ou o valor digitado) da linha do editor
            mk_aplicado = float(row_edit["Markup (%)"]) / 100
            divisor = 1.0 - (icms_venda_val + outros_custos_pct_val)
            
            # Aplica a mesma fórmula comercial padrão do Passo 4
            preco_venda_unit = (item.custo_unit_rs * (1 + mk_aplicado)) / divisor if divisor > 0 else item.custo_unit_rs * (1 + mk_aplicado)
        else:
            preco_venda_unit = float(row_edit["Preço Venda Final Requerido (R$)"])
            margem_liquida_rs = (preco_venda_unit * (1.0 - icms_venda_val - outros_custos_pct_val)) - item.custo_unit_rs
            mk_aplicado = (margem_liquida_rs / item.custo_unit_rs) if item.custo_unit_rs > 0 else 0.0

        # Grava os valores calculados diretamente nas propriedades oficiais lidas pelo PDF de fábrica
        item.markup = mk_aplicado
        item.preco_venda_unit_calculado = preco_venda_unit

    # 3. Chama a função estável original (sem parâmetros extras que geravam TypeError)
    bytes_temp = gerar_pdf_orcamento(
        resultado=resultado_pdf, 
        logo_path=str(LOGO_PATH), 
        cliente=cliente_nome,
        numero_orcamento=numero_orcamento, 
        observacoes=observacoes
    )
    
    st.session_state.pdf_bytes_gerado = bytes_temp
    st.session_state.pdf_generated_sucesso = True  # Define que a geração funcionou
    st.session_state.pdf_gerado_sucesso = True     # Garante sincronismo com o seu verificador

# Bloco do Visualizador acoplado após a geração
if st.session_state.get("pdf_gerado_sucesso") and st.session_state.pdf_bytes_gerado is not None:
    st.success("PDF gerado com sucesso! Veja a prévia abaixo:")
    
    try:
        import fitz  # PyMuPDF
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
