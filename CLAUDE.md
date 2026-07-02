# MegaRhino Weekly Sales Report — repo notes

This repo is cloned by a **Claude Code Routine** every Monday ~10 PM Philippine time to build and draft the weekly Amazon sales report **for every active client brand**. The full task lives in `ROUTINE_PROMPT.md` (paste it as the routine's Instructions).

## Files
- `build_report.py` — branded reportlab PDF generator. Reads a per-brand JSON file: `python3 build_report.py <data.json> <out.pdf>`. Auto-fits a variable number of product rows and overflows to more pages if needed. Design is final — do not change layout/colors.
- `logo_0.png.b64` — red rhino logo, stored as base64 TEXT. `build_report.py` decodes it to `logo_0.png` at run start every time. **Do not commit a raw `logo_0.png`** — a prior version of this repo shipped the binary PNG directly and it got silently corrupted by git's line-ending normalization in the cloud clone (every generated PDF's embedded logo failed to decompress, "Failed to load PDF document"). Storing it as base64 text sidesteps that class of bug entirely; `.gitignore` keeps the decoded PNG out of the repo.
- `.gitattributes` — defense-in-depth (not load-bearing for the logo anymore, see above). Add it to GitHub via the web "Add file → Create new file" button and type the filename directly — that avoids OS file pickers that hide dotfiles on upload.
- `ROUTINE_PROMPT.md` — the self-contained multi-brand weekly workflow.
- `Missive Draft Creator Webhook.gs` — reference copy of the Apps Script that turns a webhook POST into a Missive draft (deployed separately by MegaRhino; not run here).

## Which brands
All brands from Jarvio `list_brands` EXCEPT `MegaRhino (MR)` (the agency) and `Zoni Pets (ZP)` (wound down). Duplicate entries (same brand_name + marketplace, e.g. GWTD CA) are deduped. Brands with zero sales in the week are skipped.

## Product grouping
- **Firehouse**: hand-defined families (Light / Dark / Tacky) via its SKU map.
- **Every other brand**: one row per **parent ASIN** (child variations rolled up, parent listing title as the name). No manual per-brand map required.

## Profit method (v2 — actual fees)
Profit = Net Sales − Total Amazon Charges, order-week basis, using ACTUAL fee rates from settled `financialEvents`. Per product line:
`charges = referral_rate·revenue + fba_per_unit·units + other_per_unit·units`.
- referral_rate ≈ actual Commission / principal (~15%)
- fba_per_unit = actual FBAPerUnitFulfillmentFee / units — blends $3.44 base and ~$8.50 surcharge units (NOT flat $3.44)
- Ads (Sponsored Products) are EXCLUDED.

## Data sourcing
Jarvio `sp_api_pull_data` only (never `my_data` — not brand-scoped). Pass each brand's `brand_tenant_id` and use its `marketplace_id`. orderMetrics for client-facing units/revenue (order week); financialEvents for actual fee RATES (settlement-dated) — do not mix the two bases.

## Delivery
One PDF + one Missive **draft** per brand. Google Drive connector uploads the PDF → `driveFileId` → direct curl POST to the Apps Script `/exec` webhook with `send:false` and **no recipient** (routed manually in Missive). Always a DRAFT; never auto-send. Brands are processed independently — one failure does not stop the rest.

## Requirements
Python 3 + `reportlab` (installed by `setup.sh`). Network access must allow `script.google.com` and `script.googleusercontent.com` for the webhook (see the setup guide).
