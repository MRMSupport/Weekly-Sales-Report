Build the MegaRhino weekly per-brand sales report for **each brand the "Brand Info" sheet has opted in** (see Section A). For each brand you generate a self-contained **HTML report** and **enqueue one Missive DRAFT** — you do NOT send email yourself and you do NOT POST to any webhook. Enqueuing means writing one job JSON into a Google Drive **outbox** folder; a separate Google Apps Script "queue mailer" polls that folder, renders the PDF from your HTML on Google's side, and creates the Missive draft (never sends). Enqueuing uses the **Google Drive connector**, which is exempt from the sandbox egress allowlist, so delivery no longer depends on network egress, a webhook, or a browser. This routine fires Monday ~10 PM Philippine time (≈ Monday morning US-Pacific), so the prior week's fees have settled.

You are running autonomously in a Claude Code cloud session with the repository cloned to the working directory. `build_report.py` and `logo_0.png.b64` are in the repo root; the builder inlines the logo from `logo_0.png.b64` itself, so you don't need to do anything with it. Do not ask for approval. Process brands independently: if one brand fails, log it and continue to the next. At the end, print a summary of every brand and its outcome.

`build_report.py` is **pure Python (standard library only)** — there is nothing to `pip install`. reportlab, ghostscript, and qpdf are no longer used (the queue mailer renders the PDF, not this routine).

**Config values:**
- `OUTBOX_FOLDER_ID = 1Va4VHJFydqAjq9piydQFdeVnPElszFDD` — the Google Drive folder the queue mailer polls. Drop each brand's job JSON here. (This is the SAME outbox the Client Success queue mailer uses; the mailer processes every job regardless of type.)
- `LEDGER_FOLDER_ID = 1cR4lDuXpctVaA9q5Qs4VSrw9vsK95A9x` — the Drive folder holding the Weekly Sales dedup ledger `weekly_sales_sent.json`. **This is a DIFFERENT file from Client Success's `sent_reports.json`, and it must NOT live in the outbox** — the mailer treats every `.json` in the outbox as a job to send, so a ledger dropped there would be mis-sent and archived.
- Job send fields (written into every job): `sendApp = Missive` · `sendType = Draft` · `sendAs = support@megarhino.com`. The mailer leaves it as a Missive draft (never auto-sends) because `sendType` contains "draft".

---

## STEP 0 — Preflight: confirm the outbox is reachable (DO THIS FIRST)

No network egress is needed — sending happens later, in the queue mailer, via Google. But confirm you can write to the queue before building anything, so a misconfigured folder ID fails fast. Using the Google Drive connector, verify `OUTBOX_FOLDER_ID` resolves (e.g. `get_file_metadata` on that ID, or `search_files` scoped to it). If it does not resolve, **STOP immediately** — do not read the calendar/sheet or pull any data. Report that the outbox is not reachable and end the run. Otherwise proceed.

---

## A. Build the opted-in brand list (sheet-driven)
1. Jarvio `list_brands` — this is the full universe of brands and their `brand_tenant_id` / `marketplace_id`.
2. **Read the "Brand Info" tab** of Google Sheet `1oZw5mSqO2YDvbPkYAcAz6NaO8PJG4RZcxxrVszyb5pY` to decide which brands to report on and who receives each draft. Use the **Google Drive connector** `read_file_content` with that spreadsheet's fileId (it returns the tab as a parseable markdown table). Do NOT use Jarvio `get_google_sheet` — `google_sheets` is not authorized on these tenants and it errors. The columns that matter (match by header name, not position — the sheet may gain columns):
   - `Brand` — display name.
   - `Brand Code` — the short code (e.g. `FH`, `GWUS`, `GWCA`, `TC`). **This is the join key** to `list_brands` (whose names carry the code in parentheses, e.g. `Firehouse (FH)`).
   - `Weekly Sales Recipient Trigger` — **`Yes` = report on this brand; anything else (No/blank) = skip it.**
   - `Weekly Sales Report Recipient TO` — draft To recipients (may be blank today).
   - `Weekly Sales Report Recipient CC` — draft Cc recipients (may be blank today). NOTE: this is a different column from `Client Success Recipient CC` — do not confuse them.
   - If `read_file_content` on the sheet fails, STOP the run and report it — brand selection cannot proceed without the sheet, and guessing the brand list is not allowed.
3. **Keep only** brands whose `Weekly Sales Recipient Trigger` is `Yes` (case-insensitive). The sheet is the sole authority on which brands run — do not hardcode any brand in or out.
4. **Match each opted-in sheet row to a `list_brands` entry by Brand Code** (fallback: brand name). If a `Yes` row has no matching Jarvio brand, or a code matches more than one entry ambiguously, **log it as `unmatched — skipped` and continue** — never guess.
5. **Dedupe:** some brands appear more than once in `list_brands` (e.g. `Girl With The Dogs CA` has two tenant IDs on the same marketplace). Collapse entries with the same `brand_name` + `marketplace_id` to a single `brand_tenant_id`. If data pulls fail on the chosen ID, fall back to the other.
6. For each remaining brand keep `brand_name`, `brand_tenant_id`, `marketplace_id`, plus the sheet's `TO` and `CC` strings. That is the client set to report on.

## B. Reporting week
For each brand, the week is the most recent completed **Sunday 00:00 → Saturday 23:59 in that brand's marketplace timezone** (US-Pacific for `ATVPDKIKX0DER`; Canada `A2EUQ1WTGCTBG2` uses its own local time). Use `orderMetrics` intervals so the timezone is handled. Compute the exact dates from today and use them as the period label (e.g. "June 21–27, 2026").

## For EACH brand, do the following (pass `brand_tenant_id` in every Jarvio call; use `sp_api_pull_data`, never `my_data`):

### 1. Units + net revenue (client-facing headline)
`sp_api_pull_data` → `/sales/v1/orderMetrics` for the ORDER week, per ASIN (`granularity=Total`, iterate `asin=`), plus the account total to reconcile against. Revenue already nets promotions.
- **If total units = 0 → SKIP this brand** (record it as "skipped — no sales"; create no HTML, enqueue nothing).

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

### 6. Build the report + cover-note HTML
Write a per-brand JSON file, then run the builder to emit TWO self-contained HTML files — the full report (rendered into the attached PDF) and a short branded cover note (the email body):
```
python3 build_report.py brand_data.json report_<CODE>.html cover_<CODE>.html
```
Both are **table-based with inline styles and `bgcolor` fills** (the builder handles this — do not hand-tune). This layout is required because both render engines — Missive's email view and Google's HTML→PDF converter — ignore CSS `background-color` on divs and mishandle `inline-block`; `bgcolor` on table cells and `border` both render reliably, and a white-background wrapper keeps the body legible in email dark mode. The logo is inlined as a small base64 data URI. Verify: `grep -c '<style' report_<CODE>.html cover_<CODE>.html` and `grep -c 'undefined' report_<CODE>.html cover_<CODE>.html` must all return 0.

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

### 7. Verify before enqueuing
Confirm the per-SKU profits sum to the brand total and units/revenue reconcile to the orderMetrics account total (within rounding). **If it does not reconcile, do NOT enqueue that brand** — record a discrepancy in the summary and move on. Never enqueue numbers you could not verify.

### 8. Enqueue the Missive draft (drop a job into the Drive outbox)
You do not send email and you do not call a webhook. For each brand, write one job JSON into the outbox; the queue mailer renders the PDF from the HTML and creates the Missive draft. To/Cc come from the sheet.

**8-pre — Skip already-enqueued (dedup gate).** The canonical Weekly Sales ledger is `weekly_sales_sent.json` in `LEDGER_FOLDER_ID` (a compact object `{ "<key>": "<ISO enqueuedAt>" }`). Load it via the Drive connector (`search_files` for the title within `LEDGER_FOLDER_ID`, then `read_file_content`/`download_file_content`, parse JSON; treat a missing file as `{}`). **Corruption guard:** if the file EXISTS but does not parse, STOP and report it (do not treat as `{}` — that would re-enqueue). Build this brand's key `<CODE>__<weekStartYYYY-MM-DD>` (weekStart = the Sunday that begins the reporting week). If the key already exists, SKIP this brand (record "skipped — already enqueued"). Only enqueue keys not yet in the ledger.

**8a — Build and write the job.** Gzip+base64 the cover note (→ email body) and the full report (→ carried inside the `attachments` marker, so the mailer renders the PDF from it and the body stays a light cover note). Gzipping keeps the job under Drive's ~16 KB `create_file` truncation cliff and keeps every value under the 50k-char Google Sheets cell limit. In Python:
```python
import gzip, base64, json, datetime
def gz(path): return base64.b64encode(gzip.compress(open(path, "rb").read())).decode()
cover_gz  = gz(f"cover_{CODE}.html")     # short cover note → email body
report_gz = gz(f"report_{CODE}.html")    # full report → the mailer renders the PDF from this
# The mailer splits the attachments field on commas/newlines, so the FILENAME
# must contain NO comma (the period label "June 21–27, 2026" has one). base64
# itself never contains a comma. Strip commas from the filename; en-dash is fine.
pdf_name = f"{BRAND} - Weekly Sales Statistics ({PERIOD}).pdf".replace(",", "")
job = {
    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    "sendType": "Draft",                                             # Missive DRAFT, never send
    "sendApp":  "Missive",
    "sendAs":   "support@megarhino.com",
    "subject":  f"{BRAND} — Weekly Sales Report ({PERIOD})",
    "htmlBodyGz": cover_gz,                                          # cover note = the email body
    "attachments": f"PDF_FROM_HTML_GZ:{report_gz}::{pdf_name}",      # mailer decompresses & renders the PDF
}
if TO_RESOLVED: job["to"] = TO_RESOLVED   # sheet "Weekly Sales Report Recipient TO", comma-separated; OMIT if blank
if CC_RESOLVED: job["cc"] = CC_RESOLVED   # sheet "Weekly Sales Report Recipient CC", comma-separated; OMIT if blank
base64Content = base64.b64encode(json.dumps(job).encode("utf-8")).decode()
assert len(base64Content) < 15000, "job too large after gzip — report brand as not-enqueued for manual handling"
```
- `htmlBodyGz` is the COVER note (the mailer decompresses it into the email body). The full report rides gzipped inside `attachments` — do NOT also put the report in `htmlBodyGz`.
- `attachments` is `PDF_FROM_HTML_GZ:<gzip-base64 of the report>::<comma-free filename>.pdf`. This tells the mailer to decompress that report HTML and render the attached PDF from it. Do NOT put a Drive fileId here and do NOT upload a PDF.
- `to`/`cc` are plain comma-separated strings (the mailer splits them itself). **A blank TO does NOT skip the brand** — enqueue it with no `to` field; the draft lands in Missive with no recipient, routed manually (matches current practice).

Then write it into the outbox with the Google Drive connector `create_file`:
- `parentId` = `OUTBOX_FOLDER_ID`
- `title` = `job_weekly_<CODE>_<YYYY-MM-DD>.json` (the `weekly_` prefix distinguishes it from Client Success jobs in the shared outbox; unique per brand + week)
- `contentMimeType` = `application/json`, `disableConversionToGoogleType: true`
- `base64Content` = the value computed above.

**Size guard:** if `len(base64Content) >= 15000` (an unusually huge catalog even after gzip), do NOT write a truncated job — report the brand as **not enqueued (body too large after gzip)** and skip it.

**Verify:** re-read the job file back (`read_file_content`) and confirm it parses as JSON. A truncated/corrupt read means the brand was NOT enqueued — report it as **not enqueued** and do not record it in the ledger.

**8b — Record the ledger.** On a confirmed write, add the brand's key to the ledger with the ISO enqueue time (`ledger[key] = "<ISO now>"`), prune any entry older than 60 days, and write the compact JSON back with `create_file` (`parentId = LEDGER_FOLDER_ID`, `title = "weekly_sales_sent.json"`, `contentMimeType = "application/json"`, `disableConversionToGoogleType: true`). Re-read to confirm it parses and contains the new key; if not, report the brand **enqueued-but-unrecorded** so a human can fix the ledger before the next run (do not re-enqueue). Do this immediately after each enqueue, not batched, so an overlapping run cannot double-enqueue.

## Final summary
Print one row per brand: name, outcome (**enqueued** / skipped-not-opted-in / skipped-no-sales / unmatched-skipped / skipped-already-enqueued / reconcile-failed / not-enqueued / enqueued-but-unrecorded / error), units, revenue, profit, margin, To/Cc used (or "none"), and the job filename written to the outbox. Also list any `Yes` sheet rows that did not match a Jarvio brand. State clearly that this routine only **enqueues** Missive DRAFTS — the queue mailer creates the actual drafts asynchronously (on its ~10-minute trigger) and nothing is auto-sent. Recommend a human spot-check that at least one brand's draft appeared in Missive with its PDF attachment.
