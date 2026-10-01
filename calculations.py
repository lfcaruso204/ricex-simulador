"""
Motor de cálculo do Simulador de Importação Ricex.

As fórmulas abaixo replicam, célula a célula, a lógica da planilha
'Fatto_a_Mano_1.xlsx' (aba "Custos Importação"), generalizada para
qualquer número de itens selecionados pelo usuário, e usam o mesmo
princípio de rateio proporcional da planilha 'Fatto_a_Mano_2.xlsx'
(aba "1-Importacao").

Mapeamento Excel -> código (planilha "Custos Importação"):
    B5  cambio                      B6  frete_internacional (US$)
    B9  ii            B10 ipi       B11 pis           B12 cofins
    B13 afrmm         B14 icms      B15 despesas_portuarias (R$)
    B8  total_invoice_usd = SUM(C20:C26)     -> aqui: soma dos itens selecionados
    D6  frete_rs = B6 * B5
    G5/I5 mercadoria_rs = B8 * B5
    G8/I8 valor_aduaneiro = I5 + I6(=D6)
    I9  ii_rs     = I8 * B9
    I10 ipi_rs    = (I8 + I9) * B10
    I11 pis_rs    = (I8 + I9) * B11
    I12 cofins_rs = (I8 + I9) * B12
    I13 afrmm_rs  = D6 * B13
    I14 icms_rs   = (I8+I9+I11+I12+I13+I15) * B14 / (1 - B14)   [cálculo "por dentro"]
    I15 despesas_portuarias_rs = B15
    I16 custo_geral_importacao = SUM(I8:I15)

Por item i (linha 20..26 da planilha, generalizado para N itens):
    C_i  valor_usd_item   = qtd_i * fob_unit_usd_i
    D_i  participacao_i   = C_i / B8
    E_i  mercadoria_rs_i  = C_i * B5
    F_i  frete_rs_i       = D_i * D6
    G_i  ii_rs_i          = D_i * I9
    (novo) ipi_rs_i       = D_i * I10      (não existia na planilha original;
                                             adicionado por generalidade - IPI padrão é 0%)
    H_i  pis_rs_i         = D_i * I11
    I_i  cofins_rs_i      = D_i * I12
    J_i  afrmm_rs_i       = D_i * I13
    K_i  icms_rs_i        = D_i * I14
    L_i  despesas_rs_i    = D_i * I15
    M_i  custo_total_rs_i = SUM(E_i:L_i, ipi_rs_i)
    N_i  custo_unit_rs_i  = M_i / qtd_i

Precificação (aba "3. MARGEM / MARK-UP", generalizada e com cálculo reverso):
    Modo "markup"       : preco_venda_unit = custo_unit * (1 + markup)
    Modo "preco_final"  : markup = preco_venda_unit / custo_unit - 1
    lucro_unit   = preco_venda_unit - custo_unit
    lucro_total  = lucro_unit * qtd
    margem_sobre_venda = lucro_unit / preco_venda_unit   (ex.: G33 da planilha)
"""
from dataclasses import dataclass, field
from typing import List, Literal


@dataclass
class ItemSimulacao:
    ref: str
    produto: str
    composicao: str
    qtd: float
    fob_unit_usd: float
    # modo "markup": markup é a entrada e o preço final é calculado
    # modo "preco_final": preco_venda_unit é a entrada e o markup é calculado
    modo: Literal["markup", "preco_final"] = "markup"
    markup: float = 1.0           # ex.: 1.0 = 100% sobre o custo
    preco_venda_unit: float = 0.0  # usado quando modo == "preco_final"

    # --- campos calculados, preenchidos por calcular_simulacao() ---
    valor_usd: float = 0.0
    participacao: float = 0.0
    mercadoria_rs: float = 0.0
    frete_rs: float = 0.0
    ii_rs: float = 0.0
    ipi_rs: float = 0.0
    pis_rs: float = 0.0
    cofins_rs: float = 0.0
    afrmm_rs: float = 0.0
    icms_rs: float = 0.0
    despesas_rs: float = 0.0
    custo_total_rs: float = 0.0
    custo_unit_rs: float = 0.0
    lucro_unit_rs: float = 0.0
    lucro_total_rs: float = 0.0
    margem_sobre_venda: float = 0.0


@dataclass
class ResultadoSimulacao:
    cambio: float
    frete_internacional_usd: float
    despesas_portuarias_rs: float
    frete_rs_total: float
    total_invoice_usd: float
    mercadoria_rs_total: float
    valor_aduaneiro_rs: float
    ii_rs_total: float
    ipi_rs_total: float
    pis_rs_total: float
    cofins_rs_total: float
    afrmm_rs_total: float
    icms_rs_total: float
    custo_geral_importacao_rs: float
    itens: List[ItemSimulacao] = field(default_factory=list)

    @property
    def custo_total_rs(self) -> float:
        return sum(i.custo_total_rs for i in self.itens)

    @property
    def qtd_total(self) -> float:
        return sum(i.qtd for i in self.itens)

    @property
    def receita_total_rs(self) -> float:
        return sum(i.preco_venda_unit_calculado * i.qtd for i in self.itens)

    @property
    def lucro_total_rs(self) -> float:
        return sum(i.lucro_total_rs for i in self.itens)

    @property
    def roi(self) -> float:
        custo = self.custo_total_rs
        return (self.lucro_total_rs / custo) if custo else 0.0


def calcular_simulacao(
    itens: List[ItemSimulacao],
    cambio: float,
    frete_internacional_usd: float,
    despesas_portuarias_rs: float,
    ii: float,
    ipi: float,
    pis: float,
    cofins: float,
    afrmm: float,
    icms: float,
) -> ResultadoSimulacao:
    """Replica a lógica de 'Custos Importação' do Fatto_a_Mano_1.xlsx
    para a lista de itens selecionada pelo usuário."""

    # B8 — total da invoice (US$), soma dos itens selecionados (C20:C26 generalizado)
    for item in itens:
        item.valor_usd = item.qtd * item.fob_unit_usd
    total_invoice_usd = sum(i.valor_usd for i in itens)

    # D6 — frete internacional convertido para R$
    frete_rs_total = frete_internacional_usd * cambio

    # G5/I5 — mercadoria em R$ (câmbio aplicado sobre o total da invoice)
    mercadoria_rs_total = total_invoice_usd * cambio

    # G8/I8 — valor aduaneiro = mercadoria + frete (em R$)
    valor_aduaneiro_rs = mercadoria_rs_total + frete_rs_total

    # I9 — II
    ii_rs_total = valor_aduaneiro_rs * ii

    base_pis_cofins_ipi = valor_aduaneiro_rs + ii_rs_total
    # I10 — IPI (default 0%, mantido por generalidade/preservação de fórmula)
    ipi_rs_total = base_pis_cofins_ipi * ipi
    # I11 — PIS-Importação
    pis_rs_total = base_pis_cofins_ipi * pis
    # I12 — COFINS-Importação
    cofins_rs_total = base_pis_cofins_ipi * cofins
    # I13 — AFRMM (sobre o frete internacional em R$)
    afrmm_rs_total = frete_rs_total * afrmm
    # I15 — despesas portuárias (valor fixo informado)
    despesas_portuarias_total = despesas_portuarias_rs
    # I14 — ICMS "por dentro"
    base_icms = (
        valor_aduaneiro_rs
        + ii_rs_total
        + pis_rs_total
        + cofins_rs_total
        + afrmm_rs_total
        + despesas_portuarias_total
    )
    icms_rs_total = (base_icms * icms / (1 - icms)) if icms < 1 else 0.0

    # I16 — custo geral da importação
    custo_geral_importacao_rs = (
        valor_aduaneiro_rs
        + ii_rs_total
        + ipi_rs_total
        + pis_rs_total
        + cofins_rs_total
        + afrmm_rs_total
        + icms_rs_total
        + despesas_portuarias_total
    )

    # --- rateio proporcional por item (seção 2 da planilha) ---
    for item in itens:
        item.participacao = (item.valor_usd / total_invoice_usd) if total_invoice_usd else 0.0
        item.mercadoria_rs = item.valor_usd * cambio
        item.frete_rs = item.participacao * frete_rs_total
        item.ii_rs = item.participacao * ii_rs_total
        item.ipi_rs = item.participacao * ipi_rs_total
        item.pis_rs = item.participacao * pis_rs_total
        item.cofins_rs = item.participacao * cofins_rs_total
        item.afrmm_rs = item.participacao * afrmm_rs_total
        item.icms_rs = item.participacao * icms_rs_total
        item.despesas_rs = item.participacao * despesas_portuarias_total

        item.custo_total_rs = (
            item.mercadoria_rs
            + item.frete_rs
            + item.ii_rs
            + item.ipi_rs
            + item.pis_rs
            + item.cofins_rs
            + item.afrmm_rs
            + item.icms_rs
            + item.despesas_rs
        )
        item.custo_unit_rs = (item.custo_total_rs / item.qtd) if item.qtd else 0.0

        # --- precificação (seção 3, com cálculo reverso) ---
        if item.modo == "preco_final" and item.preco_venda_unit:
            preco_unit = item.preco_venda_unit
            item.markup = (preco_unit / item.custo_unit_rs - 1) if item.custo_unit_rs else 0.0
        else:
            preco_unit = item.custo_unit_rs * (1 + item.markup)
            item.preco_venda_unit = preco_unit

        item.preco_venda_unit_calculado = preco_unit
        item.lucro_unit_rs = preco_unit - item.custo_unit_rs
        item.lucro_total_rs = item.lucro_unit_rs * item.qtd
        item.margem_sobre_venda = (item.lucro_unit_rs / preco_unit) if preco_unit else 0.0

    return ResultadoSimulacao(
        cambio=cambio,
        frete_internacional_usd=frete_internacional_usd,
        despesas_portuarias_rs=despesas_portuarias_rs,
        frete_rs_total=frete_rs_total,
        total_invoice_usd=total_invoice_usd,
        mercadoria_rs_total=mercadoria_rs_total,
        valor_aduaneiro_rs=valor_aduaneiro_rs,
        ii_rs_total=ii_rs_total,
        ipi_rs_total=ipi_rs_total,
        pis_rs_total=pis_rs_total,
        cofins_rs_total=cofins_rs_total,
        afrmm_rs_total=afrmm_rs_total,
        icms_rs_total=icms_rs_total,
        custo_geral_importacao_rs=custo_geral_importacao_rs,
        itens=itens,
    )
