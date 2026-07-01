Build the MegaRhino weekly per-brand sales report PDF for the brand **Firehouse** for the PRIOR completed week, then create a **Missive DRAFT (do NOT send)** with the PDF attached. This routine fires Monday ~10 PM Philippine time (≈ Monday morning US-Pacific), so the prior week's fees have settled.

You are running autonomously in a Claude Code cloud session with the repository cloned to the working directory. `build_report.py`, `logo_0.png`, and the Apps Script source are in the repo root. Do not ask for approval — follow every step and finish.

## Define the reporting week
The reporting week is the most recent completed **Sunday 00:00 → Saturday 23:59 US-Pacific** (the 7 days ending the Saturday before today). Compute the exact dates from today's date and use them everywhere as the period label (e.g. "June 21–27, 2026").

## 1. Brand + marketplace
Jarvio connector. Firehouse `brand_tenant_id = 720e5885-8877-4677-a796-aa246babef14`, marketplace `ATVPDKIKX0DER` (US). Pass `brand_tenant_id` in every Jarvio call. Do NOT use pre-synced `my_data` reports — they are not reliably brand-scoped. Use `sp_api_pull_data`.

## 2. Units + net revenue per SKU (client-facing headline)
`sp_api_pull_data` → `/sales/v1/orderMetrics` on the ORDER week (Sun 00:00 to next-Sun 00:00, marketplace TZ), `granularity=Total`, per `asin=`. Per-ASIN calls must reconcile to the account total. Revenue already nets promotions.
SKU → family map: `"Light, Firehouse Moustache Wax"`=Light, `"Dark 2"`=Dark, `"Wacky Tacky, Firehouse Moustache Wax"`=Tacky. Exclude SKUs with no sales.

## 3. Available inventory
`sp_api_pull_data` → `/fba/inventory/v1/summaries` → sum `fulfillableQuantity` per ASIN (in-stock only). Weeks of cover = available / weekly units. Pill GREEN if ≥4 weeks, else RED.

## 4. Actual fees (v2 method)
`sp_api_pull_data` → `/finances/v0/financialEvents`, pulled **day by day** (the wrapper truncates lists at 50; large results are saved to tool-results files — parse those). Per family:
- `referral_rate` = actual Commission / principal (~14.9–15.0%)
- `fba_per_unit` = actual FBAPerUnitFulfillmentFee / units — this **blends the $3.44 base and the ~$8.50 surcharge units**; it is NOT a flat $3.44
- `other_per_unit` = remaining item-level fees / units

## 5. Profit
Per family: `profit = revenue − (referral_rate·revenue + fba_per_unit·units + other_per_unit·units)`. **EXCLUDE ads** (Sponsored Products). Total profit = sum of families; margin = total profit / total revenue.

## 6. Build the PDF
Edit the `DATA` dict at the top of `build_report.py` (period label, units, revenue, profit, per-family rows `(name, units, revenue, profit, available, green)`, and subtitles), then run:
```
pip install --break-system-packages reportlab
python3 build_report.py "Firehouse - Weekly Sales Statistics (<period>).pdf"
```
Keep the design unchanged. Output is a one-page PDF attachment only (no email body in the PDF).

## 7. Verify before sending
Render/inspect the PDF. Confirm per-family profits sum to the total, and units/revenue reconcile to the orderMetrics account totals. If anything does not reconcile, STOP and report — do not create a draft with numbers you could not verify.

## 8. Create the Missive draft (direct webhook — no browser)
a. Upload the finished PDF to Google Drive via the Google Drive connector (`create_file` with base64 content, mime `application/pdf`, disable conversion to Google type). Capture the returned Drive file `id`.
b. POST the payload directly to the Apps Script webhook with curl (follow redirects; Apps Script requires `text/plain` content type):
```
EXEC="https://script.google.com/macros/s/AKfycbwluzQW0Hz4_LSKAZQZ4Gowb8QF47NCZNIjyO92R5k7UXN8WXxRj5pdpbfXa5XeGADCQQ/exec"
curl -sL -X POST "$EXEC" \
  -H "Content-Type: text/plain;charset=utf-8" \
  --data @payload.json
```
where `payload.json` is:
```
{
  "subject": "Firehouse — Weekly Sales Report (<period>)",
  "body": "<HTML cover note with the units / revenue / profit highlights>",
  "from": { "name": "MegaRhino Marketing & Retail", "email": "support@megarhino.com" },
  "driveFileId": "<id from step 8a>",
  "send": false
}
```
c. Confirm the response is `status: success` with code `201`. **Never set `send: true`** — leave it as a draft for human review.
   NOTE: if the curl fails with `403 host_not_allowed`, the routine's environment network access is not permitting `script.google.com`. This must be fixed in the environment settings (Custom network access + allowed domain), not worked around.

## 9. Report
Summarize the run: the period, units, revenue, profit, margin, per-family breakdown, the Drive file id, and the Missive draft id. State clearly that a DRAFT was created and nothing was emailed.
