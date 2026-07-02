Build the MegaRhino weekly per-brand sales report for **every active client brand**, one PDF and one Missive **DRAFT (do NOT send)** per brand. This routine fires Monday ~10 PM Philippine time (≈ Monday morning US-Pacific), so the prior week's fees have settled.

You are running autonomously in a Claude Code cloud session with the repository cloned to the working directory. `build_report.py` and `logo_0.png.b64` are in the repo root; the script decodes the logo to `logo_0.png` itself at run start, so you don't need to do anything with it. Do not ask for approval. Process brands independently: if one brand fails, log it and continue to the next. At the end, print a summary of every brand and its outcome.

Install the PDF dependency once if not already present: `pip install --break-system-packages reportlab`.

## A. Build the active brand list
1. Jarvio `list_brands`.
2. **Exclude** `MegaRhino (MR)` (the agency itself) and `Zoni Pets (ZP)` (wound down — zero inventory/sales).
3. **Dedupe:** some brands appear more than once (e.g. `Girl With The Dogs CA` has two tenant IDs on the same marketplace). Collapse entries with the same `brand_name` + `marketplace_id` to a single `brand_tenant_id`. If data pulls fail on the chosen ID, fall back to the other.
4. Keep `brand_name`, `brand_tenant_id`, `marketplace_id` for each remaining brand. That is the client set to report on.

## B. Reporting week
For each brand, the week is the most recent completed **Sunday 00:00 → Saturday 23:59 in that brand's marketplace timezone** (US-Pacific for `ATVPDKIKX0DER`; Canada `A2EUQ1WTGCTBG2` uses its own local time). Use `orderMetrics` intervals so the timezone is handled. Compute the exact dates from today and use them as the period label (e.g. "June 21–27, 2026").

## For EACH brand, do the following (pass `brand_tenant_id` in every Jarvio call; use `sp_api_pull_data`, never `my_data`):

### 1. Units + net revenue (client-facing headline)
`sp_api_pull_data` → `/sales/v1/orderMetrics` for the ORDER week, per ASIN (`granularity=Total`, iterate `asin=`), plus the account total to reconcile against. Revenue already nets promotions.
- **If total units = 0 → SKIP this brand** (record it as "skipped — no sales"; create no PDF, no draft).

### 2. Group products
- **Firehouse only:** keep the hand-defined families using this SKU map — `"Light, Firehouse Moustache Wax"`=Light, `"Dark 2"`=Dark, `"Wacky Tacky, Firehouse Moustache Wax"`=Tacky.
- **Every other brand:** group child ASINs by **parent ASIN**. Get the parent ASIN and a display title from `asin_information` (catalog relationships); if an ASIN has no parent, treat it as its own line. Display name = the parent listing title, trimmed. Sum units and revenue per group.

### 3. Available inventory
`sp_api_pull_data` → `/fba/inventory/v1/summaries`, sum `fulfillableQuantity` per ASIN (in-stock only), aggregate to each group. Weeks of cover = group available / group weekly units. Pill GREEN if ≥ 4 weeks, else RED.

### 4. Actual fees (v2 method)
`sp_api_pull_data` → `/finances/v0/financialEvents`, pulled **day by day** (the wrapper truncates lists at 50; large results save to tool-results files — parse those). Aggregate each group's child-ASIN settled events. Per group:
- `referral_rate` = actual Commission / principal (~14.9–15.0%)
- `fba_per_unit` = actual FBAPerUnitFulfillmentFee / units — blends the $3.44 base and ~$8.50 surcharge units (NOT a flat $3.44)
- `other_per_unit` = remaining item-level fees / units
- **EXCLUDE ads** (Sponsored Products).

### 5. Profit
Per group: `profit = revenue − (referral_rate·revenue + fba_per_unit·units + other_per_unit·units)`. Brand totals = sums of groups; margin = total profit / total revenue.

### 6. Build the PDF
Write a per-brand JSON file, then run the generalized builder (it auto-fits any number of product rows and overflows to more pages if needed — do not hand-tune layout):
```
python3 build_report.py brand_data.json "<Brand> - Weekly Sales Statistics (<period>).pdf"
```
`brand_data.json` schema:
```
{
  "brand": "<brand_name>",
  "period": "<Mon D–D, YYYY>",
  "units": <int total>, "units_sub": "across <N> product lines",
  "revenue": <float>, "revenue_sub": "net ordered product sales",
  "profit": <float>, "profit_sub": "~<M>% margin after actual Amazon fees",
  "products": [ ["<name>", <units>, <revenue>, <profit>, <available>, <true|false green>], ... ],
  "footer": "MegaRhino Marketing & Retail  |  www.megarhino.com  |  support@megarhino.com  |  828.222.3842"
}
```

### 7. Verify before drafting
Confirm the group profits sum to the brand total and units/revenue reconcile to the orderMetrics account total (within rounding). **If it does not reconcile, do NOT create a draft for that brand** — record a discrepancy in the summary and move on. Never draft numbers you could not verify.

### 8. Create the Missive draft (direct webhook — no browser, no recipient)
a. Upload the finished PDF to Google Drive via the Google Drive connector (`create_file`, base64 content, mime `application/pdf`, disable conversion to Google type). Capture the Drive file `id`.
b. POST directly to the Apps Script webhook with curl (follow redirects; Apps Script requires `text/plain`):
```
EXEC="https://script.google.com/macros/s/AKfycbwluzQW0Hz4_LSKAZQZ4Gowb8QF47NCZNIjyO92R5k7UXN8WXxRj5pdpbfXa5XeGADCQQ/exec"
curl -sL -X POST "$EXEC" -H "Content-Type: text/plain;charset=utf-8" --data @payload.json
```
`payload.json` (note: **no `to` field** — drafts are routed manually in Missive, matching current practice):
```
{
  "subject": "<Brand> — Weekly Sales Report (<period>)",
  "body": "<HTML cover note with the brand's units / revenue / profit highlights>",
  "from": { "name": "MegaRhino Marketing & Retail", "email": "support@megarhino.com" },
  "driveFileId": "<id from 8a>",
  "send": false
}
```
c. Confirm the response is `status: success`, code `201`. **Never set `send: true`.**
   If curl returns `403 host_not_allowed`, the routine environment does not permit `script.google.com` — STOP and report it; do not work around it.

## Final summary
Print one row per brand: name, outcome (**drafted** / skipped-no-sales / reconcile-failed / error), units, revenue, profit, margin, Drive file id, Missive draft id. State clearly that only DRAFTS were created and nothing was emailed.