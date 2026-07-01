# Firehouse Weekly Sales Report — repo notes

This repo is cloned by a **Claude Code Routine** every Monday ~10 PM Philippine time to build and draft the Firehouse weekly Amazon sales report. The full task lives in `ROUTINE_PROMPT.md` (paste it as the routine's Instructions).

## Files
- `build_report.py` — branded reportlab PDF generator. Edit the `DATA` dict at the top each run, then `python3 build_report.py "<out>.pdf"`. Design is final — do not change layout/colors.
- `logo_0.png` — red rhino logo used by the PDF header. Keep next to the build script.
- `ROUTINE_PROMPT.md` — the self-contained weekly workflow.
- `Missive Draft Creator Webhook.gs` — reference copy of the Apps Script that turns a webhook POST into a Missive draft (deployed separately by MegaRhino; not run here).

## Profit method (v2 — actual fees)
Profit = Net Sales − Total Amazon Charges, order-week basis, using ACTUAL fee rates from settled `financialEvents`. Per family:
`charges = referral_rate·revenue + fba_per_unit·units + other_per_unit·units`.
- referral_rate ≈ actual Commission / principal (~15%)
- fba_per_unit = actual FBAPerUnitFulfillmentFee / units — blends $3.44 base and ~$8.50 surcharge units (NOT flat $3.44)
- Ads (Sponsored Products) are EXCLUDED per client.

## Data sourcing
Jarvio `sp_api_pull_data` only (never `my_data` — not brand-scoped). Firehouse `brand_tenant_id 720e5885-8877-4677-a796-aa246babef14`, marketplace `ATVPDKIKX0DER`. orderMetrics for client-facing units/revenue (order week); financialEvents for actual fee RATES (settlement-dated) — do not mix the two bases.

## Delivery
Google Drive connector uploads the PDF → `driveFileId` → direct curl POST to the Apps Script `/exec` webhook with `send:false`. Always a DRAFT; never auto-send.

## Requirements
Python 3 + `reportlab` (installed by `setup.sh`). Network access must allow `script.google.com` and `script.googleusercontent.com` for the webhook (see the setup guide).
