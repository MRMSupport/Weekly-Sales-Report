Build the MegaRhino weekly per-brand sales report for **each brand the "Brand Info" sheet has opted in** (see Section A), one PDF and one Missive **DRAFT (do NOT send)** per brand. This routine fires Monday ~10 PM Philippine time (≈ Monday morning US-Pacific), so the prior week's fees have settled.

You are running autonomously in a Claude Code cloud session with the repository cloned to the working directory. `build_report.py` and `logo_0.png.b64` are in the repo root; the script decodes the logo to `logo_0.png` itself at run start, so you don't need to do anything with it. Do not ask for approval. Process brands independently: if one brand fails, log it and continue to the next. At the end, print a summary of every brand and its outcome.

Install the PDF dependency once if not already present: `pip install --break-system-packages reportlab`.

## A. Build the opted-in brand list (sheet-driven)
1. Jarvio `list_brands` — this is the full universe of brands and their `brand_tenant_id` / `marketplace_id`.
2. **Read the "Brand Info" tab** of Google Sheet `1oZw5mSqO2YDvbPkYAcAz6NaO8PJG4RZcxxrVszyb5pY` to decide which brands to report on and who receives each draft. Use the **Google Drive connector** `read_file_content` with that spreadsheet's fileId (it returns the tab as a parseable markdown table). Do NOT use Jarvio `get_google_sheet` — `google_sheets` is not authorized on these tenants and it errors. The columns that matter (match by header name, not position — the sheet may gain columns):
   - `Brand` — display name.
   - `Brand Code` — the short code (e.g. `FH`, `GWUS`, `GWCA`, `TC`). **This is the join key** to `list_brands` (whose names carry the code in parentheses, e.g. `Firehouse (FH)`).
   - `Weekly Sales Recipient Trigger` — **`Yes` = report on this brand; anything else (No/blank) = skip it.**
   - `Weekly Sales Report Recipient TO` — draft To recipients (may be blank today).
   - `Weekly Sales Report Recipient CC` — draft Cc recipients (may be blank today). NOTE: this is a different column from `Client Success Recipient CC` — do not confuse them.
   - If `read_file_content` on the sheet fails, STOP the run and report it — brand selection cannot proceed without the sheet, and guessing the brand list is not allowed.
3. **Keep only** brands whose `Weekly Sales Recipient Trigger` is `Yes` (case-insensitive).
4. **Always exclude** `MegaRhino (MR)` (the agency itself) and `Zoni Pets (ZP)` (wound down — zero inventory/sales) **even if the sheet marks them `Yes`.**
5. **Match each opted-in sheet row to a `list_brands` entry by Brand Code** (fallback: brand name). If a `Yes` row has no matching Jarvio brand, or a code matches more than one entry ambiguously, **log it as `unmatched — skipped` and continue** — never guess.
6. **Dedupe:** some brands appear more than once in `list_brands` (e.g. `Girl With The Dogs CA` has two tenant IDs on the same marketplace). Collapse entries with the same `brand_name` + `marketplace_id` to a single `brand_tenant_id`. If data pulls fail on the chosen ID, fall back to the other.
7. For each remaining brand keep `brand_name`, `brand_tenant_id`, `marketplace_id`, plus the sheet's `TO` and `CC` strings. That is the client set to report on.

## B. Reporting week
For each brand, the week is the most recent completed **Sunday 00:00 → Saturday 23:59 in that brand's marketplace timezone** (US-Pacific for `ATVPDKIKX0DER`; Canada `A2EUQ1WTGCTBG2` uses its own local time). Use `orderMetrics` intervals so the timezone is handled. Compute the exact dates from today and use them as the period label (e.g. "June 21–27, 2026").

## For EACH brand, do the following (pass `brand_tenant_id` in every Jarvio call; use `sp_api_pull_data`, never `my_data`):

### 1. Units + net revenue (client-facing headline)
`sp_api_pull_data` → `/sales/v1/orderMetrics` for the ORDER week, per ASIN (`granularity=Total`, iterate `asin=`), plus the account total to reconcile against. Revenue already nets promotions.
- **If total units = 0 → SKIP this brand** (record it as "skipped — no sales"; create no PDF, no draft).

### 2. Product lines — one row per SKU
Report **one row per SKU (child ASIN / size-color variation) for EVERY brand** — no parent-ASIN roll-up and no hand-defined family maps. This applies to Firehouse too (its old Light/Dark/Tacky family map is retired). Keep each child ASIN that had sales in the week as its own line; drop SKUs with zero units. Units and revenue are already per-ASIN from step 1. For the display name, pull the item title from `asin_information` and use the variation label (size/color, or the 2-pack descriptor) so each row is distinguishable, trimmed.

### 3. Available inventory
`sp_api_pull_data` → `/fba/inventory/v1/summaries`, sum `fulfillableQuantity` per child ASIN (in-stock only; if a SKU spans more than one listing/row, sum across them). Weeks of cover = SKU available / SKU weekly units. Pill GREEN if ≥ 4 weeks, else RED.

### 4. Actual fees
`sp_api_pull_data` → `/finances/v0/financialEvents`, pulled **day by day** (the wrapper truncates each list at 50 events and saves large results to tool-results files — parse those; a few settled days is enough to derive stable rates). From the settled shipment events compute the actual fee rates, then apply them to each SKU's order-week units/revenue:
- `referral_rate` = actual Commission / principal (~14.9–15.0%)
- `fba_per_unit` = actual FBAPerUnitFulfillmentFee / units — blends the $3.44 base and ~$8.50 surcharge units (NOT a flat $3.44); it varies by size, so compute it per SKU where the sample allows, else fall back to a blended rate for similar SKUs.
- `other_per_unit` = remaining item-level fees / units
- **EXCLUDE ads** (Sponsored Products) and all account-level fees (monthly/long-term storage, inbound/removal, refund admin, etc.) — they are NOT part of this profit figure (surfaced by the disclaimer in step 6).

### 5. Profit
Per SKU: `profit = revenue − (referral_rate·revenue + fba_per_unit·units + other_per_unit·units)`. Brand totals = sums of SKUs; margin = total profit / total revenue. This is profit after per-order Amazon fees only — see the disclaimer in step 6.

### 6. Build the PDF
Write a per-brand JSON file, then run the generalized builder (it auto-fits any number of product rows and overflows to more pages if needed — do not hand-tune layout):
```
python3 build_report.py brand_data.json _raw.pdf
```
Then **normalize `_raw.pdf` into the final delivered PDF** (required). reportlab emits an ASCII85-heavy PDF; rewrite it to a standard, linearized binary PDF so it opens reliably in every viewer. Install `ghostscript`/`qpdf` once if missing (`apt-get install -y ghostscript qpdf`):
```
gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.7 -dNOPAUSE -dBATCH -dQUIET -dAutoRotatePages=/None -sOutputFile=_gs.pdf _raw.pdf
qpdf --linearize --object-streams=generate _gs.pdf "<Brand> - Weekly Sales Statistics (<period>).pdf"
```
Assert the final file starts with `%PDF` and `qpdf --check` reports no syntax/stream errors; if either fails, record the brand as `pdf-normalize-failed` and create no draft. (Context: attachments once arrived "Failed to load"; the real cause was the webhook, not the PDF — see step 8 and `CLAUDE.md` — but a standard PDF is still what we deliver.)

`brand_data.json` schema (see `sample_data.json` for a working example):
```
{
  "brand": "<brand_name>",
  "period": "<Mon D–D, YYYY>",
  "units": <int total>, "units_sub": "across <N> SKUs",
  "revenue": <float>, "revenue_sub": "net ordered product sales",
  "profit": <float>, "profit_sub": "~<M>% margin after actual Amazon fees",
  "products": [ ["<SKU name>", <units>, <revenue>, <profit>, <available>, <true|false green>], ... ],
  "disclaimer": "Profit is after per-order Amazon fees (referral, FBA fulfillment, and other per-item fees) only; it excludes advertising, storage, and other account-level fees and product cost, so actual net profit is lower.",
  "footer": "MegaRhino Marketing & Retail  |  www.megarhino.com  |  support@megarhino.com  |  828.222.3842"
}
```
- `products` is **one row per SKU** (child ASIN), ordered however you like (revenue-descending reads well). `units_sub` should read `across <N> SKUs`.
- **Always include the `disclaimer` field** with the exact standard text above — the builder renders it as a small footnote beneath the KPI cards so the profit figure is never read as true net profit.

### 7. Verify before drafting
Confirm the per-SKU profits sum to the brand total and units/revenue reconcile to the orderMetrics account total (within rounding). **If it does not reconcile, do NOT create a draft for that brand** — record a discrepancy in the summary and move on. Never draft numbers you could not verify.

### 8. Create the Missive draft (direct webhook — no browser; To/Cc from the sheet)
The webhook can attach the PDF two ways. Use the Drive path first; if it fails, fall back to inline base64 so the draft still lands. **The Apps Script webhook hands the file to Missive as RAW base64 (no `data:` URI).** This was a fix: a prior version wrapped the bytes as `data:application/pdf;base64,…`, Missive base64-decoded that whole string (including the literal `data:…;base64,` text) into the file, and every attachment arrived corrupted ("Failed to load PDF document"). Do NOT reintroduce a `data:` URI wrapper in `payload.json` or in the `.gs` — send only the bare base64. See `CLAUDE.md` for the full root cause.

**a. Primary — upload to Drive.** Upload the finished PDF to Google Drive via the Google Drive connector (`create_file`, base64 content, mime `application/pdf`, disable conversion to Google type). Capture the Drive file `id`. Build `payload.json` with a top-level `"driveFileId": "<id>"`.

**b. Fallback — inline base64 (only if 8a fails).** If the Drive upload errors (connector unavailable, permission/quota error, etc.), skip `driveFileId` and instead base64-encode the PDF file yourself and put it in an `attachments` array:
```
"attachments": [ { "base64_data": "<base64 of the PDF>", "filename": "<Brand> - Weekly Sales Statistics (<period>).pdf", "media_type": "application/pdf" } ]
```
The webhook accepts either shape; do NOT send both for the same draft. Note the fallback was used in the final summary for that brand.

**c. POST directly to the Apps Script webhook with curl** (follow redirects; Apps Script requires `text/plain`):
```
EXEC="https://script.google.com/macros/s/AKfycbwluzQW0Hz4_LSKAZQZ4Gowb8QF47NCZNIjyO92R5k7UXN8WXxRj5pdpbfXa5XeGADCQQ/exec"
curl -sL -X POST "$EXEC" -H "Content-Type: text/plain;charset=utf-8" --data @payload.json
```
`payload.json` — set `to`/`cc` from this brand's sheet columns:
```
{
  "subject": "<Brand> — Weekly Sales Report (<period>)",
  "body": "<HTML cover note with the brand's units / revenue / profit highlights>",
  "from": { "name": "MegaRhino Marketing & Retail", "email": "support@megarhino.com" },
  "to": [ {"email": "<from Weekly Sales Report Recipient TO>"} ],
  "cc": [ {"email": "<from Weekly Sales Report Recipient CC>"} ],
  "driveFileId": "<id from 8a>",   // OR "attachments": [...] from 8b — never both
  "send": false
}
```
   - Split the TO and CC cells on commas/semicolons into one `{"email": ...}` object per address; trim whitespace.
   - **If the TO cell is blank, omit the `to` key entirely** (create the draft with no recipient, routed manually in Missive — matches current practice). Likewise omit `cc` if that cell is blank. A blank TO is NOT a reason to skip the brand — still build the PDF and the draft.

**d. If the sandbox blocks the POST, fall back to Claude in Chrome.** If curl returns a proxy `403` / `host_not_allowed` / "blocked-by-allowlist" (the sandbox egress does not permit `script.google.com`), do NOT just stop — re-issue the *same* POST from the browser, but only if the Claude-in-Chrome tools exist in this run. Navigate a tab to a normal page (e.g. `https://example.com`), then via `javascript_tool`:
```
fetch(EXEC, {method:"POST", headers:{"Content-Type":"text/plain;charset=utf-8"}, body:<payload JSON>, redirect:"follow"})
```
Apps Script cold-starts can exceed a tool's timeout, so kick the fetch off storing its result on `window.__draft`, then poll `window.__draft` in a later call rather than awaiting inline; if a tab becomes unresponsive, open a fresh tab. Classify the outcome: **success** (`{"status":"success"}`) → done; **definitive block and no Chrome available** → report the brand `unsent`; **ambiguous / timeout** → report `unconfirmed` and do NOT retry (a retry risks a duplicate draft). Proper long-term fix: enable network egress for `script.google.com` (Org settings → Capabilities → Code execution) — note it applies to newly-started sessions, not one already running. See `SETUP_GUIDE.md`.

**e. Confirm & verify delivery integrity.** The webhook response must be `status: success`, code `201`. **Never set `send: true`** — always a DRAFT even when recipients are present; MegaRhino reviews and sends in Missive. Then verify the file did not corrupt on the way to Drive: re-download it via the Google Drive connector (`download_file_content` on the `driveFileId`), base64-decode, and confirm it is byte-identical to the local normalized PDF and starts with `%PDF`. If it does not match, flag the brand `delivery-corrupted` in the summary and investigate before trusting the draft. **Limitation:** this checks the upload/Drive round-trip and the webhook contract (raw base64), but the routine runs headless and cannot open Missive — so the *rendered* Missive attachment can only be confirmed by a human. Note in the summary that a person should spot-check at least one brand's attachment opens.

## Final summary
Print one row per brand: name, outcome (**drafted** / skipped-not-opted-in / skipped-no-sales / unmatched-skipped / reconcile-failed / pdf-normalize-failed / delivery-corrupted / unsent / unconfirmed / error), units, revenue, profit, margin, To/Cc used (or "none"), attachment path used (drive / inline-fallback), send path (curl / chrome), delivery-integrity (ok / corrupted / not-checked), Drive file id (if any), Missive draft id. Remind the reader to open at least one draft's PDF attachment as a human spot-check. Also list any `Yes` sheet rows that did not match a Jarvio brand. State clearly that only DRAFTS were created and nothing was emailed.
