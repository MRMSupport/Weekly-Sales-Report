#!/usr/bin/env python3
"""
MegaRhino weekly per-brand sales report — TABLE-BASED, self-contained HTML.

    python3 build_report.py <data.json> <report.html> [<cover.html>]
      - 2 args: write the full report HTML only.
      - 3 args: also write the short cover-note HTML (used as the email body).
    (Back-compat: `python3 build_report.py <report.html>` uses the built-in DATA.)

WHY TABLES (not divs): the full report HTML is rendered to a PDF by the Google
Apps Script queue mailer (`Blob.getAs('application/pdf')`) AND, for the cover
note, shown as the email body in Missive. Both engines are weak: they IGNORE CSS
`background-color` on divs/spans and mishandle `inline-block` layout. So every
colored fill (KPI cards, the red header bar, the green/red availability pills,
zebra rows, revenue bars) uses the HTML **`bgcolor` attribute** on table cells
(with a matching inline style as belt-and-suspenders), borders use `border`
(which both engines DO honor), and layout uses `<table>`. A white-background
wrapper + light color-scheme meta keeps it readable in email dark mode.

DELIVERY SPLIT: the routine sends the SHORT cover note as the email body
(`htmlBodyGz`) and ships the FULL report gzipped inside the job's `attachments`
marker (`PDF_FROM_HTML_GZ:...`); the mailer decompresses it and renders the PDF.
So the body is a light cover note and the PDF is the full report.

One row per SKU. Profit = Net Sales − actual per-order Amazon fees (referral +
FBA fulfillment + other per-item); excludes ads, storage, other account-level
fees, and COGS — surfaced by the `disclaimer`.
"""
import os, sys, json, base64, html as _html

RED, GREEN, REDLT = "#C10123", "#2FA84F", "#D13B3B"
INK, GRAY, MUTE = "#2B2B2B", "#6C6D70", "#8A8A8E"
CARD, CARD2, LINE = "#F9F9FB", "#EFEFF2", "#E6E6EA"
FONT = "Arial,Helvetica,sans-serif"

LOGO_B64_PATH = os.path.join(os.path.dirname(__file__), "logo_0.png.b64")

DATA = {
    "brand": "Demo Brand",
    "period": "June 21–27, 2026",
    "units": 165, "units_sub": "across 3 SKUs",
    "revenue": 3150.00, "revenue_sub": "net ordered product sales",
    "profit": 2016.00, "profit_sub": "~64% margin after actual Amazon fees",
    "products": [
        ("Standard",  25,  500.00,  320.00, 170, True),
        ("Premium",    40,  750.00,  480.00, 410, True),
        ("Deluxe",    100, 1900.00, 1216.00, 890, True),
    ],
    "disclaimer": ("Profit is after per-order Amazon fees (referral, FBA fulfillment, and other "
                   "per-item fees) only; it excludes advertising, storage, and other account-level "
                   "fees and product cost, so actual net profit is lower."),
    "footer": "MegaRhino Marketing & Retail  |  www.megarhino.com  |  support@megarhino.com  |  828.222.3842",
}


def money(v):
    return "${:,.2f}".format(float(v))


def esc(s):
    return _html.escape(str(s), quote=True)


def logo_data_uri():
    if not os.path.exists(LOGO_B64_PATH):
        return ""
    with open(LOGO_B64_PATH, "r") as f:
        raw = "".join(f.read().split())
    return "data:image/png;base64," + raw


def _doc(inner):
    """Wrap content in a white-background, dark-mode-resistant table shell."""
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="color-scheme" content="light only">'
        '<meta name="supported-color-schemes" content="light">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#ffffff;" bgcolor="#FFFFFF">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'bgcolor="#FFFFFF" style="background:#ffffff;">'
        '<tr><td align="center" style="padding:24px 16px;">'
        '<table role="presentation" width="720" cellpadding="0" cellspacing="0" border="0" '
        'style="width:720px;max-width:720px;font-family:{font};color:{ink};">{inner}</table>'
        '</td></tr></table></body></html>'
    ).format(font=FONT, ink=INK, inner=inner)


def _header_rows(data):
    logo = logo_data_uri()
    logo_cell = (
        '<td width="54" valign="middle" style="padding-right:12px;">'
        '<img src="{uri}" alt="MegaRhino" width="42" height="42" style="display:block;"></td>'
    ).format(uri=logo) if logo else ""
    header = (
        '<tr><td style="padding:0 0 4px 0;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
        '{logo}'
        '<td valign="middle">'
        '<div style="font-size:21px;font-weight:bold;color:{ink};line-height:1.15;">Weekly Sales Report</div>'
        '<div style="font-size:11px;color:{gray};padding-top:3px;">{brand} &bull; {period}</div>'
        '</td></tr></table></td></tr>'
    ).format(logo=logo_cell, ink=INK, gray=GRAY, brand=esc(data["brand"]), period=esc(data["period"]))
    # Full-width red rule via a border-top on a block div: borders render in
    # BOTH the email client and Google's HTML->PDF converter (CSS background on
    # a div does not), and a block div always fills the cell width.
    rule = (
        '<tr><td style="padding:10px 0 18px 0;font-size:0;line-height:0;">'
        '<div style="border-top:2px solid {red};font-size:0;line-height:0;">&nbsp;</div>'
        '</td></tr>'
    ).format(red=RED)
    return header + rule


def _kpi_cards(data):
    def card(label, big, sub):
        return (
            '<td width="32%" valign="top" bgcolor="{card}" '
            'style="background:{card};border-top:3px solid {red};padding:12px 14px;">'
            '<div style="font-size:9px;font-weight:bold;letter-spacing:.5px;color:{mute};padding-bottom:8px;">{label}</div>'
            '<div style="font-size:23px;font-weight:bold;color:{ink};padding-bottom:6px;">{big}</div>'
            '<div style="font-size:9px;color:{gray};">{sub}</div></td>'
        ).format(card=CARD, red=RED, mute=MUTE, ink=INK, gray=GRAY,
                 label=esc(label), big=esc(big), sub=esc(sub))
    spacer = '<td width="2%">&nbsp;</td>'
    row = (card("TOTAL UNITS SOLD", str(data["units"]), data.get("units_sub", "")) + spacer
           + card("TOTAL REVENUE", money(data["revenue"]), data.get("revenue_sub", "")) + spacer
           + card("TOTAL PROFIT", money(data["profit"]), data.get("profit_sub", "")))
    return ('<tr><td><table width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr>{row}</tr></table></td></tr>').format(row=row)


def _disclaimer_row(data):
    disc = data.get("disclaimer", "")
    if not disc:
        return ""
    return ('<tr><td style="padding:10px 0 0 0;font-size:8px;font-style:italic;'
            'color:{mute};line-height:1.4;">{d}</td></tr>').format(mute=MUTE, d=esc(disc))


def _product_table(products):
    head_cells = ""
    heads = [("PRODUCT", None, "left"), ("UNITS", "12%", "left"), ("REVENUE", "16%", "left"),
             ("PROFIT", "16%", "left"), ("AVAILABLE", "14%", "left")]
    for label, w, al in heads:
        wa = ' width="{}"'.format(w) if w else ""
        head_cells += (
            '<td{wa} align="{al}" bgcolor="{red}" '
            'style="background:{red};color:#ffffff;font-size:9.5px;font-weight:bold;padding:6px 8px;">{lab}</td>'
        ).format(wa=wa, al=al, red=RED, lab=esc(label))
    rows = ""
    for i, (name, u, rev, prof, avail, green) in enumerate(products):
        zc = "#FFFFFF" if i % 2 == 0 else CARD2
        pill = GREEN if green else REDLT
        def cell(content, color=INK, weight="normal", align="left"):
            return ('<td bgcolor="{zc}" align="{al}" style="background:{zc};padding:8px;font-size:10.5px;'
                    'font-weight:{wt};color:{col};border-bottom:1px solid {line};">{c}</td>'
                    ).format(zc=zc, al=align, wt=weight, col=color, line=LINE, c=content)
        pill_html = (
            '<table cellpadding="0" cellspacing="0" border="0"><tr>'
            '<td bgcolor="{pill}" align="center" style="background:{pill};color:#ffffff;font-size:10px;'
            'font-weight:bold;padding:3px 12px;border-radius:5px;">{v}</td></tr></table>'
        ).format(pill=pill, v=esc(avail))
        avail_cell = ('<td bgcolor="{zc}" style="background:{zc};padding:6px 8px;'
                      'border-bottom:1px solid {line};">{p}</td>').format(zc=zc, line=LINE, p=pill_html)
        rows += ('<tr>' + cell(esc(name), color=INK, weight="bold") + cell(esc(str(u)))
                 + cell(esc(money(rev)), color=GRAY) + cell(esc(money(prof)), color=GRAY)
                 + avail_cell + '</tr>')
    heading = ('<tr><td style="padding:22px 0 8px 0;font-size:11.5px;font-weight:bold;color:{ink};">'
               'Performance by Product</td></tr>').format(ink=INK)
    table = ('<tr><td><table width="100%" cellpadding="0" cellspacing="0" border="0" '
             'style="border-collapse:collapse;"><tr>{h}</tr>{r}</table></td></tr>').format(h=head_cells, r=rows)
    return heading + table


def _legend_row():
    def item(color, text):
        return ('<td width="18" valign="middle"><table cellpadding="0" cellspacing="0" border="0"><tr>'
                '<td width="16" height="9" bgcolor="{col}" style="background:{col};width:16px;height:9px;'
                'font-size:1px;line-height:1px;">&nbsp;</td></tr></table></td>'
                '<td valign="middle" style="font-size:9px;color:{gray};padding:0 24px 0 8px;">{t}</td>'
                ).format(col=color, gray=GRAY, t=esc(text))
    return ('<tr><td style="padding:12px 0 0 0;"><table cellpadding="0" cellspacing="0" border="0"><tr>'
            + item(GREEN, "≥ 4 weeks of available inventory")
            + item(REDLT, "< 4 weeks of available inventory")
            + '</tr></table></td></tr>')


def _revenue_chart(products):
    top12 = sorted(products, key=lambda p: p[2], reverse=True)[:12]
    maxrev = max((p[2] for p in top12), default=1) or 1
    label = "Revenue by Product" + (" (top 12)" if len(products) > 12 else "")
    bars = ""
    for name, u, rev, prof, avail, green in top12:
        pct = max(1, int(round(100.0 * (float(rev) / float(maxrev)))))
        bar = ('<table width="{pct}%" cellpadding="0" cellspacing="0" border="0"><tr>'
               '<td height="11" bgcolor="{red}" style="background:{red};height:11px;line-height:11px;font-size:1px;">'
               '&nbsp;</td></tr></table>').format(pct=pct, red=RED)
        bars += (
            '<tr>'
            '<td width="22%" align="right" style="font-size:9px;color:{gray};padding:0 8px 8px 0;">{nm}</td>'
            '<td width="60%" style="padding:0 0 8px 0;">{bar}</td>'
            '<td width="18%" style="font-size:9px;color:{gray};padding:0 0 8px 6px;">{rev}</td>'
            '</tr>'
        ).format(gray=GRAY, nm=esc(name), bar=bar, rev=esc(money(rev)))
    heading = ('<tr><td style="padding:22px 0 12px 0;font-size:11.5px;font-weight:bold;color:{ink};">{label}</td></tr>'
               ).format(ink=INK, label=esc(label))
    table = ('<tr><td><table width="100%" cellpadding="0" cellspacing="0" border="0">{bars}</table></td></tr>'
             ).format(bars=bars)
    return heading + table


def _footer_row(data):
    footer = data.get("footer", "")
    if not footer:
        return ""
    return ('<tr><td align="center" style="padding:26px 0 0 0;font-size:8.5px;font-weight:bold;'
            'color:{gray};">{f}</td></tr>').format(gray=GRAY, f=esc(footer))


def render_report(data):
    products = [tuple(p) for p in data["products"]]
    inner = (_header_rows(data) + _kpi_cards(data) + _disclaimer_row(data)
             + _product_table(products)
             + _footer_row(data))
    return _doc(inner)


def render_cover(data):
    """Short branded cover note used as the email body (full report is the PDF)."""
    kpis = [("Units", str(data["units"])), ("Net revenue", money(data["revenue"])),
            ("Profit", money(data["profit"]))]
    kpi_cells = ""
    for i, (lab, val) in enumerate(kpis):
        spacer = '<td width="2%">&nbsp;</td>' if i else ""
        kpi_cells += (spacer + '<td width="32%" valign="top" bgcolor="{card}" '
                      'style="background:{card};border-top:3px solid {red};padding:12px 14px;">'
                      '<div style="font-size:9px;font-weight:bold;letter-spacing:.5px;color:{mute};padding-bottom:6px;">{lab}</div>'
                      '<div style="font-size:20px;font-weight:bold;color:{ink};">{val}</div></td>'
                      ).format(card=CARD, red=RED, mute=MUTE, ink=INK, lab=esc(lab.upper()), val=esc(val))
    note = ('<tr><td style="padding:2px 0 4px 0;font-size:13px;color:{ink};line-height:1.5;">'
            'Here is the <b>{brand}</b> weekly sales report for <b>{period}</b>. '
            'A summary is below; full per-SKU detail is in the attached PDF.</td></tr>'
            ).format(ink=INK, brand=esc(data["brand"]), period=esc(data["period"]))
    kpi_row = ('<tr><td style="padding:14px 0 0 0;"><table width="100%" cellpadding="0" cellspacing="0" '
               'border="0"><tr>{c}</tr></table></td></tr>').format(c=kpi_cells)
    margin_line = ""
    if data.get("profit_sub"):
        margin_line = ('<tr><td style="padding:8px 0 0 0;font-size:11px;color:{gray};">{s}</td></tr>'
                       ).format(gray=GRAY, s=esc(data["profit_sub"]))
    inner = (_header_rows(data) + note + kpi_row + margin_line
             + _disclaimer_row(data) + _footer_row(data))
    return _doc(inner)


if __name__ == "__main__":
    args = sys.argv[1:]
    data = DATA
    report_out, cover_out = "weekly_report.html", None
    if len(args) >= 2:
        with open(args[0]) as f:
            data = json.load(f)
        report_out = args[1]
        if len(args) >= 3:
            cover_out = args[2]
    elif len(args) == 1:
        report_out = args[0]
    with open(report_out, "w", encoding="utf-8") as f:
        f.write(render_report(data))
    print("wrote", report_out)
    if cover_out:
        with open(cover_out, "w", encoding="utf-8") as f:
            f.write(render_cover(data))
        print("wrote", cover_out)
