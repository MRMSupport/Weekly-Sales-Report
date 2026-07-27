#!/usr/bin/env python3
"""
MegaRhino weekly per-brand sales report — SELF-CONTAINED HTML builder.

    python3 build_report.py <data.json> <out.html>
(Backward compatible: `python3 build_report.py <out.html>` uses the built-in
sample DATA below.)

WHY HTML (not a PDF): delivery no longer POSTs a PDF through a webhook. The
routine drops a job JSON into a Google Drive "outbox"; a Google Apps Script
"queue mailer" reads it, renders the PDF from this HTML on Google's side
(Utilities.newBlob(html,'text/html').getAs('application/pdf')), and creates the
Missive draft. The SAME html is both the email body and the attached PDF.

HTML RULES (must hold so it renders identically as email body AND as the PDF the
mailer generates): inline styles ONLY — no <style> blocks, no external CSS, no
remote images (the logo is inlined as a base64 data URI), and NO <table> element
(layout is inline-block cells). Keep it print-clean and self-contained.

The report reproduces the previous reportlab design: header + logo, three KPI
cards (units / net revenue / profit) with a red top rule, a disclaimer footnote,
a per-SKU performance grid with green/red weeks-of-cover pills, a "Revenue by
Product" (top 12) bar chart, and the centered footer. One row per SKU — no
parent-ASIN roll-up.

PROFIT METHOD (unchanged): Profit = Net Sales - actual per-order Amazon fees
(referral + FBA fulfillment + other per-item), order-week basis; excludes ads,
storage, other account-level fees, and COGS — surfaced by the `disclaimer`.
"""
import os, sys, json, base64, html as _html

# ---- palette (hex equivalents of the reportlab RGB palette) ----
RED   = "#C10123"   # brand red
GREEN = "#2FA84F"   # >= 4 weeks cover
REDLT = "#D13B3B"   # < 4 weeks cover
INK   = "#2B2B2B"   # headings / values
GRAY  = "#6C6D70"   # secondary text
MUTE  = "#8A8A8E"   # labels / footnote
CARD  = "#F9F9FB"   # KPI card fill
CARD2 = "#EFEFF2"   # zebra row fill

LOGO_B64_PATH = os.path.join(os.path.dirname(__file__), "logo_0.png.b64")

# ---- sample data (regenerate per brand from connectors) ----
DATA = {
    "brand": "Firehouse",
    "period": "June 21–27, 2026",
    "units": 168, "units_sub": "across 3 SKUs",
    "revenue": 3152.34, "revenue_sub": "net ordered product sales",
    "profit": 2011.66, "profit_sub": "~64% margin after actual Amazon fees",
    "products": [
        ("Light",  27,  512.73,  330.42, 172, True),
        ("Dark",   41,  759.60,  480.62, 412, True),
        ("Tacky", 100, 1880.01, 1200.62, 892, True),
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
    """Return the rhino logo as a base64 data URI, or '' if the asset is missing.

    The logo is stored as base64 TEXT (logo_0.png.b64) — same asset the old
    reportlab build decoded — and inlined here so the HTML is fully
    self-contained (no remote image fetch, which the mailer's HTML->PDF
    renderer could not resolve)."""
    if not os.path.exists(LOGO_B64_PATH):
        return ""
    with open(LOGO_B64_PATH, "r") as f:
        raw = "".join(f.read().split())  # strip any whitespace/newlines
    return "data:image/png;base64," + raw


def kpi_card(label, big, sub):
    return (
        '<div style="display:inline-block;vertical-align:top;width:32%;'
        'box-sizing:border-box;background:{card};border-top:3px solid {red};'
        'padding:12px 14px 12px 14px;margin:0;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:9px;'
        'font-weight:bold;letter-spacing:0.5px;color:{mute};margin:0 0 8px 0;">{label}</div>'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:23px;'
        'font-weight:bold;color:{ink};margin:0 0 6px 0;">{big}</div>'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:9px;'
        'color:{gray};margin:0;">{sub}</div>'
        '</div>'
    ).format(card=CARD, red=RED, mute=MUTE, ink=INK, gray=GRAY,
             label=esc(label), big=esc(big), sub=esc(sub))


def grid_cell(content, width, align="left", color=INK, weight="normal",
              size="11px", white=False):
    c = "#FFFFFF" if white else color
    return (
        '<div style="display:inline-block;vertical-align:middle;width:{w};'
        'box-sizing:border-box;padding:0 6px;text-align:{al};'
        'font-family:Arial,Helvetica,sans-serif;font-size:{sz};font-weight:{wt};'
        'color:{col};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{c}</div>'
    ).format(w=width, al=align, sz=size, wt=weight, col=c, c=content)


# column widths (sum ~ 100% of a ~700px content box)
COL_W = {"product": "44%", "units": "12%", "revenue": "16%", "profit": "16%", "avail": "12%"}


def header_row():
    heads = [("PRODUCT", "product", "left"), ("UNITS", "units", "left"),
             ("REVENUE", "revenue", "left"), ("PROFIT", "profit", "left"),
             ("AVAILABLE", "avail", "left")]
    cells = "".join(
        grid_cell(esc(h), COL_W[k], al, white=True, weight="bold", size="9.5px")
        for h, k, al in heads
    )
    return ('<div style="background:{red};font-size:0;line-height:20px;'
            'padding:4px 0;margin:0;">{cells}</div>').format(red=RED, cells=cells)


def product_row(p, idx):
    name, u, rev, prof, avail, green = p
    bg = CARD2 if idx % 2 == 1 else "#FFFFFF"
    pill = GREEN if green else REDLT
    pill_html = (
        '<span style="display:inline-block;background:{pill};color:#FFFFFF;'
        'font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:bold;'
        'border-radius:5px;padding:2px 0;width:58px;text-align:center;">{v}</span>'
    ).format(pill=pill, v=esc(avail))
    cells = (
        grid_cell(esc(name), COL_W["product"], "left", color=INK, weight="bold", size="10.5px")
        + grid_cell(esc(str(u)), COL_W["units"], "left", color=INK, size="10.5px")
        + grid_cell(esc(money(rev)), COL_W["revenue"], "left", color=GRAY, size="10.5px")
        + grid_cell(esc(money(prof)), COL_W["profit"], "left", color=GRAY, size="10.5px")
        + grid_cell(pill_html, COL_W["avail"], "left", size="10.5px")
    )
    return ('<div style="background:{bg};font-size:0;line-height:30px;'
            'border-bottom:1px solid #E6E6EA;">{cells}</div>').format(bg=bg, cells=cells)


def legend():
    def item(color, text):
        return (
            '<span style="display:inline-block;vertical-align:middle;margin-right:28px;">'
            '<span style="display:inline-block;vertical-align:middle;width:16px;height:9px;'
            'background:{col};margin-right:8px;"></span>'
            '<span style="font-family:Arial,Helvetica,sans-serif;font-size:9px;'
            'color:{gray};vertical-align:middle;">{t}</span></span>'
        ).format(col=color, gray=GRAY, t=esc(text))
    return ('<div style="margin:12px 0 0 0;">'
            + item(GREEN, "≥ 4 weeks of available inventory")
            + item(REDLT, "< 4 weeks of available inventory")
            + '</div>')


def revenue_chart(products):
    top12 = sorted(products, key=lambda p: p[2], reverse=True)[:12]
    maxrev = max((p[2] for p in top12), default=1) or 1
    label = "Revenue by Product" + (" (top 12)" if len(products) > 12 else "")
    rows = []
    for name, u, rev, prof, avail, green in top12:
        w = max(1.0, 100.0 * (float(rev) / float(maxrev)))  # % of the bar track
        rows.append((
            '<div style="font-size:0;margin:0 0 8px 0;">'
            '<div style="display:inline-block;vertical-align:middle;width:22%;'
            'box-sizing:border-box;padding-right:8px;text-align:right;'
            'font-family:Arial,Helvetica,sans-serif;font-size:9px;color:{gray};'
            'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{nm}</div>'
            '<div style="display:inline-block;vertical-align:middle;width:60%;">'
            '<span style="display:inline-block;vertical-align:middle;height:11px;'
            'width:{w:.1f}%;background:{red};"></span></div>'
            '<div style="display:inline-block;vertical-align:middle;width:18%;'
            'box-sizing:border-box;padding-left:6px;'
            'font-family:Arial,Helvetica,sans-serif;font-size:9px;color:{gray};'
            'white-space:nowrap;">{rev}</div>'
            '</div>'
        ).format(gray=GRAY, nm=esc(name), w=w, red=RED, rev=esc(money(rev))))
    return ('<div style="margin:22px 0 0 0;">'
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:11.5px;'
            'font-weight:bold;color:{ink};margin:0 0 12px 0;">{label}</div>'
            '{rows}</div>').format(ink=INK, label=esc(label), rows="".join(rows))


def build(data, out_path):
    products = [tuple(p) for p in data["products"]]
    logo = logo_data_uri()
    logo_html = (
        '<img src="{uri}" alt="MegaRhino" width="42" height="42" '
        'style="display:inline-block;vertical-align:middle;margin-right:12px;" />'
    ).format(uri=logo) if logo else ""

    cards = (
        '<div style="font-size:0;margin:0;">'
        + kpi_card("TOTAL UNITS SOLD", str(data["units"]), data.get("units_sub", ""))
        + '<span style="display:inline-block;width:1.5%;"></span>'
        + kpi_card("TOTAL REVENUE", money(data["revenue"]), data.get("revenue_sub", ""))
        + '<span style="display:inline-block;width:1.5%;"></span>'
        + kpi_card("TOTAL PROFIT", money(data["profit"]), data.get("profit_sub", ""))
        + '</div>'
    )

    disc = data.get("disclaimer", "")
    disc_html = (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;'
        'font-style:italic;color:{mute};margin:10px 0 0 0;line-height:1.4;">{d}</div>'
    ).format(mute=MUTE, d=esc(disc)) if disc else ""

    rows = "".join(product_row(p, i) for i, p in enumerate(products))

    footer = data.get("footer", "")
    footer_html = (
        '<div style="text-align:center;font-family:Arial,Helvetica,sans-serif;'
        'font-size:8.5px;font-weight:bold;color:{gray};margin:26px 0 0 0;">{f}</div>'
    ).format(gray=GRAY, f=esc(footer)) if footer else ""

    doc = (
        '<div style="max-width:720px;margin:0 auto;padding:24px 28px;'
        'font-family:Arial,Helvetica,sans-serif;color:{ink};">'
        # header
        '<div style="margin:0 0 4px 0;">'
        '{logo}'
        '<span style="display:inline-block;vertical-align:middle;">'
        '<span style="display:block;font-size:21px;font-weight:bold;color:{ink};">Weekly Sales Report</span>'
        '<span style="display:block;font-size:11px;color:{gray};margin-top:2px;">{brand}  &bull;  {period}</span>'
        '</span></div>'
        '<div style="height:2px;background:{red};margin:10px 0 18px 0;"></div>'
        # KPI cards + disclaimer
        '{cards}{disc}'
        # performance grid
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:11.5px;'
        'font-weight:bold;color:{ink};margin:22px 0 8px 0;">Performance by Product</div>'
        '{header}{rows}'
        # legend + chart + footer
        '{legend}{chart}{footer}'
        '</div>'
    ).format(
        ink=INK, gray=GRAY, red=RED, logo=logo_html,
        brand=esc(data["brand"]), period=esc(data["period"]),
        cards=cards, disc=disc_html, header=header_row(), rows=rows,
        legend=legend(), chart=revenue_chart(products), footer=footer_html,
    )

    html_out = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#FFFFFF;">' + doc + '</body></html>'
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    return out_path


if __name__ == "__main__":
    args = sys.argv[1:]
    data, out = DATA, "weekly_report.html"
    if len(args) == 2:
        with open(args[0]) as f:
            data = json.load(f)
        out = args[1]
    elif len(args) == 1:
        out = args[0]
    build(data, out)
    print("wrote", out)
