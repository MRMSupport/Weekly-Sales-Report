#!/usr/bin/env python3
"""
MegaRhino weekly per-brand sales report (branded reportlab PDF).

PROFIT METHOD (v2 - actual fees):
  Profit = Net Sales - Total Amazon Charges, on an ORDER-WEEK basis using
  ACTUAL fee rates measured from settled financialEvents (run the Monday after
  the Sat close so fees have settled). Per family:
     charges = referral_rate*revenue + fba_per_unit*units + other_per_unit*units
  referral_rate ~= actual Commission / principal (~15%)
  fba_per_unit  = actual FBAPerUnitFulfillmentFee / units
                  (blends the $3.44 base with the ~$8.50 surcharge units)
  Ads (Sponsored Products) are EXCLUDED per client instruction.
Design unchanged from v1 (logo, brand red #C10223, KPI cards, green/red pills,
revenue bar chart, one page).
"""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
import os

# ---- palette ----
RED   = (0.757, 0.004, 0.137)   # #C10123
GREEN = (0.184, 0.659, 0.310)   # #2FA84F
REDLT = (0.820, 0.231, 0.231)   # #D13B3B legend swatch
INK   = (0.169, 0.169, 0.169)   # #2B2B2B
GRAY  = (0.424, 0.427, 0.439)   # #6C6D71
MUTE  = (0.541, 0.541, 0.557)   # #8A8A8E
CARD  = (0.976, 0.976, 0.984)   # #F9F9FB
CARD2 = (0.937, 0.937, 0.949)   # #EFEFF2

LOGO = os.path.join(os.path.dirname(__file__), "logo_0.png")

# ---- report data (regenerate weekly from connectors) ----
DATA = {
    "brand": "Firehouse",
    "period": "June 21–27, 2026",
    "units": 168, "units_sub": "across 3 active SKUs",
    "revenue": 3152.34, "revenue_sub": "net ordered product sales",
    "profit": 2011.66,
    "profit_sub": "~64% margin after actual Amazon fees",
    "products": [
        # name, units, revenue, profit, available, green(>=4wks)
        ("Light",  27,  512.73,  330.42, 172, True),
        ("Dark",   41,  759.60,  480.62, 412, True),
        ("Tacky", 100, 1880.01, 1200.62, 892, True),
    ],
    "footer": "MegaRhino Marketing & Retail  |  www.megarhino.com  |  support@megarhino.com  |  828.222.3842",
}

def money(v): return "${:,.2f}".format(v)

def build(data, out_path):
    W, H = letter
    c = canvas.Canvas(out_path, pagesize=letter)
    LM, RM = 50, 562

    # ---- header ----
    top = H - 48
    if os.path.exists(LOGO):
        c.drawImage(LOGO, LM, top - 30, width=42, height=42, mask='auto')
    tx = LM + 54
    c.setFillColorRGB(*INK); c.setFont("Helvetica-Bold", 21)
    c.drawString(tx, top - 6, "Weekly Sales Report")
    c.setFillColorRGB(*GRAY); c.setFont("Helvetica", 11)
    c.drawString(tx, top - 24, "{}  •  {}".format(data["brand"], data["period"]))
    # red rule
    c.setFillColorRGB(*RED); c.rect(LM, H - 112, RM - LM, 2, fill=1, stroke=0)

    # ---- KPI cards ----
    cards = [
        ("TOTAL UNITS SOLD", str(data["units"]), data["units_sub"]),
        ("TOTAL REVENUE", money(data["revenue"]), data["revenue_sub"]),
        ("TOTAL PROFIT", money(data["profit"]), data["profit_sub"]),
    ]
    cy_top = H - 130
    cw = (RM - LM - 2 * 14) / 3.0
    ch = 74
    for i, (lab, big, sub) in enumerate(cards):
        x = LM + i * (cw + 14); y = cy_top - ch
        c.setFillColorRGB(*CARD); c.rect(x, y, cw, ch, fill=1, stroke=0)
        c.setFillColorRGB(*RED); c.rect(x, y + ch - 3, cw, 3, fill=1, stroke=0)  # top accent
        c.setFillColorRGB(*MUTE); c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x + 12, y + ch - 20, lab)
        c.setFillColorRGB(*INK); c.setFont("Helvetica-Bold", 23)
        c.drawString(x + 12, y + ch - 48, big)
        c.setFillColorRGB(*GRAY); c.setFont("Helvetica", 8.5)
        c.drawString(x + 12, y + 10, sub)

    # ---- Performance by Product ----
    sy = cy_top - ch - 34
    c.setFillColorRGB(*INK); c.setFont("Helvetica-Bold", 11.5)
    c.drawString(LM, sy, "Performance by Product")

    cols = [LM + 8, LM + 150, LM + 250, LM + 350, RM - 78]
    heads = ["PRODUCT", "UNITS SOLD", "REVENUE", "PROFIT", "AVAILABLE"]
    hy = sy - 22
    c.setFillColorRGB(*RED); c.rect(LM, hy - 4, RM - LM, 20, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1); c.setFont("Helvetica-Bold", 9.5)
    for cx, h in zip(cols, heads):
        c.drawString(cx, hy + 2, h)

    ry = hy - 6
    rh = 30
    for idx, (name, u, rev, prof, avail, green) in enumerate(data["products"]):
        y = ry - rh
        if idx % 2 == 1:
            c.setFillColorRGB(*CARD2); c.rect(LM, y, RM - LM, rh, fill=1, stroke=0)
        cy = y + 10
        c.setFillColorRGB(*INK); c.setFont("Helvetica-Bold", 10.5)
        c.drawString(cols[0], cy, name)
        c.setFont("Helvetica", 10.5); c.setFillColorRGB(*INK)
        c.drawString(cols[1], cy, str(u))
        c.setFillColorRGB(*GRAY)
        c.drawString(cols[2], cy, money(rev))
        c.drawString(cols[3], cy, money(prof))
        # available pill
        pill = GREEN if green else REDLT
        pw, ph = 70, 18
        px = RM - 78; py = y + (rh - ph) / 2
        c.setFillColorRGB(*pill); c.roundRect(px, py, pw, ph, 5, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1); c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(px + pw / 2, py + 5, str(avail))
        ry = y

    # legend
    ly = ry - 22
    c.setFillColorRGB(*GREEN); c.rect(LM + 4, ly, 16, 9, fill=1, stroke=0)
    c.setFillColorRGB(*GRAY); c.setFont("Helvetica", 8.5)
    c.drawString(LM + 26, ly + 1, "≥ 4 weeks of available inventory")
    c.setFillColorRGB(*REDLT); c.rect(LM + 258, ly, 16, 9, fill=1, stroke=0)
    c.setFillColorRGB(*GRAY)
    c.drawString(LM + 280, ly + 1, "< 4 weeks of available inventory")

    # ---- Revenue by Product bar chart ----
    chy = ly - 34
    c.setFillColorRGB(*INK); c.setFont("Helvetica-Bold", 11.5)
    c.drawString(LM, chy, "Revenue by Product")
    maxrev = max(p[2] for p in data["products"])
    bx = LM + 64; bmax = RM - bx - 70
    by = chy - 20
    bh = 11; gap = 24
    for name, u, rev, prof, avail, green in data["products"]:
        c.setFillColorRGB(*GRAY); c.setFont("Helvetica", 9)
        c.drawRightString(bx - 8, by - 8, name)
        w = bmax * (rev / maxrev)
        c.setFillColorRGB(*RED); c.rect(bx, by - bh, w, bh, fill=1, stroke=0)
        c.setFillColorRGB(*GRAY); c.setFont("Helvetica", 9)
        c.drawString(bx + w + 6, by - 8, money(rev))
        by -= gap

    # ---- footer ----
    c.setFillColorRGB(*GRAY); c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(W / 2, 40, data["footer"])
    c.showPage(); c.save()
    return out_path

if __name__ == "__main__":
    out = "/sessions/hopeful-zealous-euler/mnt/Weekly Sales Report/Firehouse - Weekly Sales Statistics (June 21-27, 2026).pdf"
    import sys
    if len(sys.argv) > 1: out = sys.argv[1]
    build(DATA, out)
    print("wrote", out)
