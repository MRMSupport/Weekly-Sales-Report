# MegaRhino Weekly Sales Report — repo notes

This repo is cloned by a **Claude Code Routine** every Monday ~10 PM Philippine time to build and **enqueue** the weekly Amazon sales report **for each brand opted in via the "Brand Info" sheet**. The full task lives in `ROUTINE_PROMPT.md` (paste it as the routine's Instructions). Setup and troubleshooting live in `SETUP_GUIDE.md`.

## Delivery model (outbox → queue mailer)
The routine does **not** send email and does **not** POST to a webhook. For each brand it builds a self-contained HTML report and **enqueues** one Missive DRAFT by writing a job JSON into a Google Drive **outbox** folder. A separate Google Apps Script "queue mailer" (`Code.gs`, one folder up from this repo; deployed by MegaRhino) polls the outbox on a ~10-minute trigger, renders the PDF from the HTML on Google's side, creates the Missive draft, and archives the job. Enqueuing uses the **Google Drive connector**, which is exempt from the sandbox egress allowlist — so delivery no longer depends on network egress, a webhook, a verified sending domain, or a browser fallback. Always a DRAFT; never auto-send. Brands are processed independently — one failure does not stop the rest.

**Config (see `ROUTINE_PROMPT.md`):**
- `OUTBOX_FOLDER_ID = 1Va4VHJFydqAjq9piydQFdeVnPElszFDD` — the folder the queue mailer polls (shared with the Client Success mailer; it processes any job type). Job files are named `job_weekly_<CODE>_<YYYY-MM-DD>.json`.
- `LEDGER_FOLDER_ID = 1cR4lDuXpctVaA9q5Qs4VSrw9vsK95A9x` — holds the Weekly Sales dedup ledger `weekly_sales_sent.json` (key `<CODE>__<weekStart>`). It is a **different file** from Client Success's `sent_reports.json`, and it must **never** live in the outbox — the mailer treats every `.json` in the outbox as a job to send.
- Job send fields: `sendApp = Missive`, `sendType = Draft`, `sendAs = support@megarhino.com`.

## Files
- `build_report.py` — branded **HTML** report generator (stdlib only; no reportlab/ghostscript/qpdf). Reads a per-brand JSON file: `python3 build_report.py <data.json> <out.html>`. Auto-fits a variable number of product rows; the queue mailer paginates the PDF. Design is final — do not change layout/colors. Emits self-contained HTML: **inline styles only, no `<table>`, no `<style>` blocks, no remote images** (the logo is inlined as a base64 data URI). Those rules matter because the same HTML is both the email body and the source the mailer renders to PDF — if it isn't self-contained it won't render identically in both.
- `logo_0.png.b64` — red rhino logo, stored as base64 TEXT and inlined into the HTML by `build_report.py`. **Do not commit a raw `logo_0.png`.** A prior version shipped the binary PNG and it got silently corrupted by git's line-ending normalization in the cloud clone. Storing the logo as base64 text sidesteps that class of bug entirely.
- `.gitattributes` — defense-in-depth for any future binary asset. If you add it on GitHub, use the web "Add file → Create new file" button and type the filename directly (avoids OS file pickers that hide dotfiles).
- `sample_data.json` — a synthetic multi-line brand payload, only for local testing of `build_report.py`. Not used by the routine.
- `ROUTINE_PROMPT.md` — the self-contained multi-brand weekly workflow.
- `Code.gs` — reference copy of the queue mailer (the live script is deployed in MegaRhino's Apps Script project; see `SETUP_GUIDE.md`). Only its `sendViaMissive_` was changed from the shared Client Success mailer: it now creates the Missive draft directly against `public.missiveapp.com/v1/drafts` (raw-base64 PDF, `send:false`) instead of POSTing to a separate webhook — every other function is byte-identical to the Client Success mailer. Editing this copy changes nothing until MegaRhino redeploys the Apps Script.

## Which brands (sheet-driven)
Governed by the **"Brand Info" tab** of Google Sheet `1oZw5mSqO2YDvbPkYAcAz6NaO8PJG4RZcxxrVszyb5pY`: report only on rows where **`Weekly Sales Recipient Trigger` = `Yes`**. Read the tab via the **Google Drive connector `read_file_content`** (Jarvio `get_google_sheet` is not authorized on these tenants). Join sheet rows to `list_brands` by **`Brand Code`** (name fallback); log unmatched `Yes` rows and skip them. The sheet is the **sole authority** on which brands run — no brand is hardcoded in or out. Duplicate entries (same brand_name + marketplace, e.g. GWTD CA) are deduped. Brands with zero sales in the week are still skipped.

## Product lines (per SKU)
**One row per SKU (child ASIN / size-color variation) for every brand.** No parent-ASIN roll-up and no hand-defined family maps — Firehouse included (its old Light/Dark/Tacky SKU map is retired). Each child ASIN with sales is its own line, named by its variation label; drop zero-unit SKUs. `units_sub` reads `across <N> SKUs`.

## Profit method (actual fees)
Profit = Net Sales − Amazon Charges, order-week basis, using ACTUAL fee rates from settled `financialEvents`. Per SKU:
`charges = referral_rate·revenue + fba_per_unit·units + other_per_unit·units`.
- referral_rate ≈ actual Commission / principal (~15%)
- fba_per_unit = actual FBAPerUnitFulfillmentFee / units — blends $3.44 base and ~$8.50 surcharge units (NOT flat $3.44); varies by size, so compute per SKU where the sample allows.
- Ads (Sponsored Products) are EXCLUDED.
- **This profit is only after per-order Amazon fees.** It does NOT subtract account-level fees (advertising, monthly/long-term storage, inbound/removal, refund admin) or product cost (COGS), so actual net profit is lower. Every report carries a `disclaimer` field saying so (rendered as a footnote under the KPI cards by `build_report.py`).

## Data sourcing
Jarvio `sp_api_pull_data` only (never `my_data` — not brand-scoped). Pass each brand's `brand_tenant_id` and use its `marketplace_id`. orderMetrics for client-facing units/revenue (order week); financialEvents for actual fee RATES (settlement-dated) — do not mix the two bases.

## Requirements
Python 3 only — `build_report.py` uses the standard library, so there is nothing to install (`setup.sh` is a no-op kept for compatibility). No reportlab, ghostscript, or qpdf. No network allowlist is required: the only outbound calls are the Google Drive connector (routes through Anthropic, exempt from the egress allowlist), and the actual Missive send happens later inside the Google-hosted queue mailer, not from this routine.
