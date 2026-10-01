"""Geração do PDF de orçamento para o cliente."""
from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

from calculations import ResultadoSimulacao


def _fmt_rs(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_usd(v: float) -> str:
    return "US$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_pct(v: float) -> str:
    return f"{v * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_pdf_orcamento(
    resultado: ResultadoSimulacao,
    logo_path: str,
    cliente: str = "",
    numero_orcamento: str = "",
    observacoes: str = "",
) -> bytes:
    """Gera um PDF de orçamento detalhando a remessa item a item até o preço final."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        title="Orçamento de Importação - Ricex",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="RicexTitle",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=2,
            textColor=colors.HexColor("#1b2a4a"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="RicexSubtitle",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.grey,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeader",
            parent=styles["Heading2"],
            fontSize=11,
            spaceBefore=10,
            spaceAfter=4,
            textColor=colors.white,
            backColor=colors.HexColor("#1b2a4a"),
            leftIndent=4,
            borderPadding=4,
        )
    )
    small_right = ParagraphStyle(name="SmallRight", parent=styles["Normal"], fontSize=9, alignment=TA_RIGHT)

    elements = []

    # --- Cabeçalho: logo + título ---
    try:
        logo = Image(logo_path, width=35 * mm, height=35 * mm, kind="proportional")
    except Exception:
        logo = Spacer(1, 1)

    header_table = Table(
        [
            [
                logo,
                Paragraph(
                    "<b>RICEX IMPORTAÇÃO</b><br/>Orçamento de Importação — Peças de Vestuário",
                    styles["RicexTitle"],
                ),
            ]
        ],
        colWidths=[40 * mm, None],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 4))

    info_linhas = [
        f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    ]
    if numero_orcamento:
        info_linhas.append(f"Orçamento nº: {numero_orcamento}")
    if cliente:
        info_linhas.append(f"Cliente: {cliente}")
    elements.append(Paragraph(" | ".join(info_linhas), styles["RicexSubtitle"]))
    elements.append(HRFlowable(width="100%", color=colors.HexColor("#1b2a4a"), thickness=1, spaceAfter=6, spaceBefore=6))

    # --- Parâmetros gerais da operação ---
    elements.append(Paragraph("PARÂMETROS GERAIS DA OPERAÇÃO", styles["SectionHeader"]))
    params_data = [
        ["Câmbio (R$/US$)", f"{resultado.cambio:.4f}", "Frete internacional (US$)", _fmt_usd(resultado.frete_internacional_usd)],
        ["Despesas portuárias (R$)", _fmt_rs(resultado.despesas_portuarias_rs), "Total da invoice (US$)", _fmt_usd(resultado.total_invoice_usd)],
        ["Valor aduaneiro (R$)", _fmt_rs(resultado.valor_aduaneiro_rs), "Custo geral de importação (R$)", _fmt_rs(resultado.custo_geral_importacao_rs)],
    ]
    t_params = Table(params_data, colWidths=[55 * mm, 35 * mm, 60 * mm, 35 * mm])
    t_params.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ]
        )
    )
    elements.append(t_params)

    impostos_data = [
        [
            f"II: {_fmt_pct(resultado.ii_rs_total / resultado.valor_aduaneiro_rs) if resultado.valor_aduaneiro_rs else '-'}",
            f"IPI R$: {_fmt_rs(resultado.ipi_rs_total)}",
            f"PIS R$: {_fmt_rs(resultado.pis_rs_total)}",
            f"COFINS R$: {_fmt_rs(resultado.cofins_rs_total)}",
            f"AFRMM R$: {_fmt_rs(resultado.afrmm_rs_total)}",
            f"ICMS R$: {_fmt_rs(resultado.icms_rs_total)}",
        ]
    ]
    t_impostos = Table(impostos_data, colWidths=[31 * mm] * 6)
    t_impostos.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#333333")),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(t_impostos)

    # --- Detalhamento item a item ---
    elements.append(Paragraph("DETALHAMENTO DA REMESSA — ITEM A ITEM", styles["SectionHeader"]))

    header = ["Produto", "Qtd.", "FOB US$/un.", "Custo R$/un.", "Markup", "Preço Venda R$/un.", "Subtotal R$"]
    rows = [header]
    for item in resultado.itens:
        rows.append(
            [
                Paragraph(f"{item.produto}<br/><font size=6 color='grey'>{item.ref}</font>", styles["Normal"]),
                f"{item.qtd:,.0f}".replace(",", "."),
                f"{item.fob_unit_usd:,.2f}",
                _fmt_rs(item.custo_unit_rs),
                _fmt_pct(item.markup),
                _fmt_rs(item.preco_venda_unit_calculado),
                _fmt_rs(item.preco_venda_unit_calculado * item.qtd),
            ]
        )

    custo_total = resultado.custo_total_rs
    receita_total = resultado.receita_total_rs
    lucro_total = resultado.lucro_total_rs
    qtd_total = resultado.qtd_total

    rows.append(
        [
            "TOTAL / MÉDIA",
            f"{qtd_total:,.0f}".replace(",", "."),
            "",
            _fmt_rs(custo_total / qtd_total) if qtd_total else "-",
            "",
            _fmt_rs(receita_total / qtd_total) if qtd_total else "-",
            _fmt_rs(receita_total),
        ]
    )

    t_itens = Table(rows, colWidths=[42 * mm, 16 * mm, 22 * mm, 24 * mm, 18 * mm, 30 * mm, 28 * mm], repeatRows=1)
    t_itens.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b2a4a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f2f4f8")]),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#d7dcea")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c9cfdd")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(t_itens)

    # --- Resumo financeiro final ---
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("RESUMO FINANCEIRO", styles["SectionHeader"]))

    roi = (lucro_total / custo_total) if custo_total else 0.0
    resumo_data = [
        ["Custo total da importação (R$)", _fmt_rs(custo_total)],
        ["Receita total estimada (R$)", _fmt_rs(receita_total)],
        ["Lucro total estimado (R$)", _fmt_rs(lucro_total)],
        ["ROI sobre o custo", _fmt_pct(roi)],
    ]
    t_resumo = Table(resumo_data, colWidths=[90 * mm, 50 * mm])
    t_resumo.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.lightgrey),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#1b2a4a")),
            ]
        )
    )
    elements.append(t_resumo)

    elements.append(Spacer(1, 10))
    preco_final_box = Table(
        [["PREÇO FINAL TOTAL DA REMESSA", _fmt_rs(receita_total)]],
        colWidths=[90 * mm, 50 * mm],
    )
    preco_final_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1b2a4a")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(preco_final_box)

    if observacoes:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("OBSERVAÇÕES", styles["SectionHeader"]))
        elements.append(Paragraph(observacoes, styles["Normal"]))

    elements.append(Spacer(1, 16))
    elements.append(
        Paragraph(
            "Este orçamento é uma simulação e pode sofrer alterações conforme variação cambial, "
            "frete e demais condições comerciais no momento do embarque.",
            ParagraphStyle(name="Footer", parent=styles["Normal"], fontSize=7.5, textColor=colors.grey),
        )
    )

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
