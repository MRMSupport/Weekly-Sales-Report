#!/usr/bin/env python3
"""
MegaRhino weekly per-brand sales report (branded reportlab PDF).

MULTI-BRAND / GENERALIZED build. Feed it one JSON file per brand:
    python3 build_report.py <data.json> <out.pdf>
(Backward compatible: `python3 build_report.py <out.pdf>` uses the built-in
sample DATA below.)

The renderer auto-fits a VARIABLE number of product rows: it shrinks the row
height as the list grows and, if the table still doesn't fit, flows onto
additional pages (repeating the column header). The KPI cards, green/red
availability pills, "Revenue by Product" chart (top 12), and footer are kept.

PROFIT METHOD (v2 - actual fees), unchanged:
  Profit = Net Sales - Total Amazon Charges, ORDER-WEEK basis, using ACTUAL fee
  rates from settled financialEvents. Per product line:
     charges = referral_rate*revenue + fba_per_unit*units + other_per_unit*units
  fba_per_unit blends the $3.44 base with the ~$8.50 surcharge units.
  Ads (Sponsored Products) EXCLUDED.
"""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os, sys, json, base64

# ---- palette ----
RED   = (0.757, 0.004, 0.137)
GREEN = (0.184, 0.659, 0.310)
REDLT = (0.820, 0.231, 0.231)
INK   = (0.169, 0.169, 0.169)
GRAY  = (0.424, 0.427, 0.439)
MUTE  = (0.541, 0.541, 0.557)
CARD  = (0.976, 0.976, 0.984)
CARD2 = (0.937, 0.937, 0.949)

LOGO = os.path.join(os.path.dirname(__file__), "logo_0.png")
LOGO_B64 = os.path.join(os.path.dirname(__file__), "logo_0.png.b64")


def _ensure_logo():
    """Materialize logo_0.png from the tracked base64 asset (logo_0.png.b64).

    Root-cause fix for the earlier "Failed to load PDF document" bug: a raw
    binary PNG committed to git can get silently corrupted by line-ending
    normalization in some CI/clone environments if no .gitattributes is in
    effect. Base64 text isn't subject to that corruption, so the asset is
    stored as text and decoded here at run start -- this makes the logo
    correct regardless of whether .gitattributes made it into the clone.
    Always re-decodes so a stale/corrupted logo_0.png left in the working
    tree can never shadow the known-good source.
    """
    if os.path.exists(LOGO_B64):
        with open(LOGO_B64, "r") as f:
            raw = f.read()
        with open(LOGO, "wb") as f:
            f.write(base64.b64decode(raw))


_ensure_logo()

LM, RM = 50, 562
COLS = [LM + 8, LM + 210, LM + 300, LM + 392, RM - 78]  # product / units / rev / profit / avail
HEADS = ["PRODUCT", "UNITS", "REVENUE", "PROFIT", "AVAILABLE"]

# ---- sample data (regenerate per brand from connectors) ----
DATA = {
    "brand": "Firehouse",
    "period": "June 21–27, 2026",
    "units": 168, "units_sub": "across 3 product lines",
    "revenue": 3152.34, "revenue_sub": "net ordered product sales",
    "profit": 2011.66, "profit_sub": "~64% margin after actual Amazon fees",
    "products": [
        # name, units, revenue, profit, available, green(>=4wks)
        ("Light",  27,  512.73,  330.42, 172, True),
        ("Dark",   41,  759.60,  480.62, 412, True),
        ("Tacky", 100, 1880.01, 1200.62, 892, True),
    ],
    "footer": "MegaRhino Marketing & Retail  |  www.megarhino.com  |  support@megarhino.com  |  828.222.3842",
}


def money(v):
    return "${:,.2f}".format(v)


def clip(s, n):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def row_height(n):
    if n <= 12: return 30
    if n <= 16: return 24
    if n <= 24: return 20
    return 18


def draw_page_frame(c, data, first):
    """Header + (page 1 only) KPI cards. Returns y where the table area begins."""
    W, H = letter
    top = H - 48
    if os.path.exists(LOGO):
        c.drawImage(LOGO, LM, top - 30, width=42, height=42, mask="auto")
    tx = LM + 54
    c.setFillColorRGB(*INK); c.setFont("Helvetica-Bold", 21)
    title = "Weekly Sales Report" if first else "Weekly Sales Report (cont.)"
    c.drawString(tx, top - 6, title)
    c.setFillColorRGB(*GRAY); c.setFont("Helvetica", 11)
    c.drawString(tx, top - 24, "{}  •  {}".format(data["brand"], data["period"]))
    c.setFillColorRGB(*RED); c.rect(LM, H - 112, RM - LM, 2, fill=1, stroke=0)

    if not first:
        return H - 140

    cards = [
        ("TOTAL UNITS SOLD", str(data["units"]), data.get("units_sub", "")),
        ("TOTAL REVENUE", money(data["revenue"]), data.get("revenue_sub", "")),
        ("TOTAL PROFIT", money(data["profit"]), data.get("profit_sub", "")),
    ]
    cy_top = H - 130
    cw = (RM - LM - 2 * 14) / 3.0
    ch = 74
    for i, (lab, big, sub) in enumerate(cards):
        x = LM + i * (cw + 14); y = cy_top - ch
        c.setFillColorRGB(*CARD); c.rect(x, y, cw, ch, fill=1, stroke=0)
        c.setFillColorRGB(*RED); c.rect(x, y + ch - 3, cw, 3, fill=1, stroke=0)
        c.setFillColorRGB(*MUTE); c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x + 12, y + ch - 20, lab)
        c.setFillColorRGB(*INK); c.setFont("Helvetica-Bold", 23)
        c.drawString(x + 12, y + ch - 48, big)
        c.setFillColorRGB(*GRAY); c.setFont("Helvetica", 8.5)
        c.drawString(x + 12, y + 10, clip(sub, 30))
    return cy_top - ch - 34


def draw_table_header(c, y):
    c.setFillColorRGB(*INK); c.setFont("Helvetica-Bold", 11.5)
    c.drawString(LM, y, "Performance by Product")
    hy = y - 22
    c.setFillColorRGB(*RED); c.rect(LM, hy - 4, RM - LM, 20, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1); c.setFont("Helvetica-Bold", 9.5)
    for cx, h in zip(COLS, HEADS):
        c.drawString(cx, hy + 2, h)
    return hy - 6  # y of first row top edge (ry)


def build(data, out_path):
    W, H = letter
    c = canvas.Canvas(out_path, pagesize=letter)
    products = list(data["products"])
    rh = row_height(len(products))
    name_chars = 34 if rh >= 24 else 40
    BOTTOM_TABLE = 70  # never draw table rows below this y on a page

    first = True
    y_start = draw_page_frame(c, data, first)
    ry = draw_table_header(c, y_start)

    idx = 0
    for name, u, rev, prof, avail, green in products:
        if ry - rh < BOTTOM_TABLE:  # new page for the table
            c.showPage()
            first = False
            y_start = draw_page_frame(c, data, first)
            ry = draw_table_header(c, y_start)
            idx = 0
        y = ry - rh
        if idx % 2 == 1:
            c.setFillColorRGB(*CARD2); c.rect(LM, y, RM - LM, rh, fill=1, stroke=0)
        cy = y + (rh - 10) / 2 + 1
        big_font = rh >= 24
        c.setFillColorRGB(*INK); c.setFont("Helvetica-Bold", 10.5 if big_font else 9)
        c.drawString(COLS[0], cy, clip(name, name_chars))
        c.setFont("Helvetica", 10.5 if big_font else 9); c.setFillColorRGB(*INK)
        c.drawString(COLS[1], cy, str(u))
        c.setFillColorRGB(*GRAY)
        c.drawString(COLS[2], cy, money(rev))
        c.drawString(COLS[3], cy, money(prof))
        pill = GREEN if green else REDLT
        pw, ph = 70, min(18, rh - 4)
        px = RM - 78; py = y + (rh - ph) / 2
        c.setFillColorRGB(*pill); c.roundRect(px, py, pw, ph, 5, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1); c.setFont("Helvetica-Bold", 10 if big_font else 8.5)
        c.drawCentredString(px + pw / 2, py + (ph - 8) / 2, str(avail))
        ry = y
        idx += 1

    # ---- legend (new page if not enough room for legend + chart + footer) ----
    need = 22 + 34 + min(12, len(products)) * 22 + 50
    if ry - need < 30:
        c.showPage(); first = False
        draw_page_frame(c, data, first)
        ry = H - 150
    ly = ry - 22
    c.setFillColorRGB(*GREEN); c.rect(LM + 4, ly, 16, 9, fill=1, stroke=0)
    c.setFillColorRGB(*GRAY); c.setFont("Helvetica", 8.5)
    c.drawString(LM + 26, ly + 1, "≥ 4 weeks of available inventory")
    c.setFillColorRGB(*REDLT); c.rect(LM + 258, ly, 16, 9, fill=1, stroke=0)
    c.setFillColorRGB(*GRAY)
    c.drawString(LM + 280, ly + 1, "< 4 weeks of available inventory")

    # ---- Revenue by Product (top 12) ----
    top12 = sorted(products, key=lambda p: p[2], reverse=True)[:12]
    chy = ly - 34
    c.setFillColorRGB(*INK); c.setFont("Helvetica-Bold", 11.5)
    label = "Revenue by Product" + (" (top 12)" if len(products) > 12 else "")
    c.drawString(LM, chy, label)
    maxrev = max((p[2] for p in top12), default=1) or 1
    bx = LM + 130; bmax = RM - bx - 70
    by = chy - 20; bh = 11; gap = 22
    for name, u, rev, prof, avail, green in top12:
        c.setFillColorRGB(*GRAY); c.setFont("Helvetica", 9)
        c.drawRightString(bx - 8, by - 8, clip(name, 20))
        w = bmax * (rev / maxrev)
        c.setFillColorRGB(*RED); c.rect(bx, by - bh, w, bh, fill=1, stroke=0)
        c.setFillColorRGB(*GRAY); c.setFont("Helvetica", 9)
        c.drawString(bx + w + 6, by - 8, money(rev))
        by -= gap

    # ---- footer ----
    c.setFillColorRGB(*GRAY); c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(W / 2, 40, data.get("footer", ""))
    c.showPage(); c.save()
    return out_path


if __name__ == "__main__":
    args = sys.argv[1:]
    data, out = DATA, "weekly_report.pdf"
    if len(args) == 2:
        with open(args[0]) as f:
            data = json.load(f)
        data["products"] = [tuple(p) for p in data["products"]]
        out = args[1]
    elif len(args) == 1:
        out = args[0]
    build(data, out)
    print("wrote", out)