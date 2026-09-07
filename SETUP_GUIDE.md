# MegaRhino Weekly Sales Report → Claude Code Routine — setup guide

## What this does
Runs the Monday weekly report in the cloud on **Claude Code Routines** (Anthropic-managed, runs on schedule even when your laptop is closed). It runs for **every client brand opted in via the "Brand Info" sheet**: one HTML report and one **enqueued Missive draft** per brand. Same profit logic, same design.

Delivery uses the **outbox → queue mailer** pattern: the routine drops a job JSON into a Google Drive outbox via the Google Drive connector, and a Google Apps Script "queue mailer" (`Code.gs`) renders the PDF and creates the Missive draft on Google's side. There is **no webhook POST from the routine and no network-egress allowlist to configure** — this is the main change from the old direct-curl setup. Schedule: **Monday 10 PM Philippine time** (≈ Mon 7 AM US-Pacific — late enough that the prior week's fees have settled). Each draft's To/Cc come from the sheet (blank = no recipient, routed manually in Missive).

## Prerequisite (plan gate)
Routines require **Claude Code on the web enabled** on your plan (Pro, Max, Team, or Enterprise; research preview). Turn it on at [claude.ai/code](https://claude.ai/code) (connect GitHub when prompted). On **Team/Enterprise**, an Owner must not have the Routines toggle off at claude.ai/admin-settings/claude-code. If step 2 below shows no cloud option, this is the blocker.

## One-time: the queue mailer (a separate Apps Script project)
The queue mailer is a Google Apps Script that MegaRhino owns. It is shared infrastructure — many projects enqueue jobs into it, not just this one. It is not in this repo, on purpose — the Apps Script project is the only copy, so the two cannot drift apart. It is currently the 2026-09-01 revision. Here is what it does beyond the base mailer it grew out of:
- `sendViaMissive_` creates the Missive draft directly against the Missive API. It reads the token from a Script Property named `MISSIVE_TOKEN` (Project Settings → Script Properties) — the token is **not** written into the file itself, so that property has to be set for sending to work.
- `buildAttachments_` has a `PDF_FROM_HTML_GZ:` branch that renders the PDF from a gzipped report HTML carried in the marker, so the email body can be a separate short cover note. The existing `PDF_FROM_HTML` / URL / Drive-fileId paths and the Gmail path are unchanged, so every other project that uses the mailer is unaffected.
- It also reads a job's `missiveLabels` field (passed to Missive as `add_shared_labels`), dedups job files, claims a row before sending it, quarantines malformed job files instead of failing the whole run, and exposes a `doPost` web-app endpoint.

If you ever need to (re-)deploy it:
1. Open the Apps Script project that owns the queue mailer — queue sheet `1NhR5UxbQ090WZGeHkesv3CLypWXKGqkUNUfqKj8B--Y`, tab `Queue` (the one whose `runQueue` trigger polls `OUTBOX_FOLDER_ID = 1Va4VHJFydqAjq9piydQFdeVnPElszFDD`).
2. Edit it there directly — this repo deliberately keeps no copy to paste from.
3. Set the Script Property `MISSIVE_TOKEN` to the Missive API token, if it isn't set already.
4. Save. If the 10-minute `runQueue` trigger isn't installed yet, run `setupTrigger` once.

Confirm the outbox has (or the mailer will auto-create) an `Archive`/`Archived` and `Attachments` subfolder — the mailer moves processed jobs and saves rendered PDFs there.

## Steps

### 1. Put this bundle in a GitHub repo
A Routine clones a GitHub repo — it can't read your local folder. Create a private repo (e.g. `megarhino/weekly-sales-report`) and push the contents of this `weekly-sales-report/` folder:
- `build_report.py` — generalized **HTML** report builder (stdlib only; inlines the logo from `logo_0.png.b64`)
- `logo_0.png.b64` — logo as base64 text (the only tracked copy — see "Why the logo is base64" below)
- `CLAUDE.md` — method notes (auto-loaded in the clone)
- `ROUTINE_PROMPT.md` — the multi-brand workflow (paste as the routine's Instructions)
- `setup.sh` — no-op (kept for compatibility; there are no dependencies to install)
- `sample_data.json` — a synthetic example payload for local testing only
- `.gitignore` / `.gitattributes` — build-artifact ignores and binary defense-in-depth

Everything here is plain text, so GitHub's "Add file → Upload files" drag-and-drop works. Only `.gitignore` / `.gitattributes` are dotfiles; if your OS file picker hides them, add each via GitHub's web **Add file → Create new file** and type the filename directly.

### 2. Create the routine
At [claude.ai/code/routines](https://claude.ai/code/routines) → **New routine** (or Desktop app → Routines → New → **Remote**, or CLI `/schedule`):
- **Name:** MegaRhino Weekly Sales Report (all brands)
- **Instructions:** paste the full contents of `ROUTINE_PROMPT.md`
- **Repository:** the repo from step 1
- **Trigger → Schedule:** Weekly, **Monday, 10:00 PM** (entered in your local zone, converted automatically — set 10 PM Philippine time).

One session processes all opted-in brands sequentially, so expect a longer run than a single-brand job.

### 3. Environment — no setup script or allowlist needed
This is simpler than the old setup:
- **Setup script:** none required. `build_report.py` is pure Python (standard library). You may point it at `setup.sh`, but it does nothing.
- **Network access:** the old `script.google.com` / `script.googleusercontent.com` allowlist is **no longer needed** — the routine never POSTs a webhook. Its only outbound calls are connectors (Jarvio, Google Drive), which route through Anthropic and are exempt from the allowlist. The actual Missive send happens later inside the Google-hosted queue mailer.

### 4. Connectors
In the routine's **Connectors** tab, keep **Jarvio** and **Google Drive** enabled (remove the rest to limit scope). Google Drive is used to read the Brand Info sheet (`read_file_content`), write each job to the outbox (`create_file`), and read/write the dedup ledger. If Drive isn't authorized, the run STOPs at the STEP 0 preflight (outbox unreachable) or at brand selection (can't read the sheet).

### 5. Team-plan re-check (do this when moving/re-configuring on the Team plan)
Connectors do **not** carry over from a personal account — they are per-account (and, for Routines, per-routine). No IDs in this bundle change. Confirm, in order:
1. **Code on web enabled** for the Team account (see Prerequisite), and the admin Routines toggle is on.
2. **Jarvio connected** under Settings → Connectors on the Team account, and enabled on this routine. Re-run `list_brands` in a test to confirm the brand set and tenant IDs look right.
3. **Google Drive connected** on the Team account and enabled on this routine.
4. **Queue mailer deployed** with the updated `sendViaMissive_` (see "One-time" above), and its `runQueue` trigger active.
5. **PDF renderer — nothing to do here.** The Monday report is rendered by Google's built-in HTML-to-PDF converter, not a Chrome-based service. That service was built but never set up — it's parked outside this repo, in the maintainer's local project folder, with its own setup steps in its README if you ever want to turn it on. There's no `RENDER_URL` / `RENDER_TOKEN` to configure today, and `build_report.py` no longer takes a `logo_url` / `MR_LOGO_URL` override — the logo is inlined from `logo_0.png.b64`.

### 6. Test before trusting it
Open the routine → **Run now**, then open the run session and read the transcript (don't trust the green dot). Confirm it: passed the STEP 0 outbox preflight; read the Brand Info sheet; built the opted-in brand list purely from `Weekly Sales Recipient Trigger = Yes` rows (no brand hardcoded in or out; GWTD CA deduped); and for at least the first couple of brands pulled data, built the report + cover HTML (both should show 0 `<style>` and 0 `undefined` — the report is table-based now too, so it no longer contains a `<style>` block), wrote a `job_weekly_<CODE>_<date>.json` to the outbox, verified the read-back parsed, and recorded the ledger key. Then wait for the queue mailer's next ~10-minute cycle and confirm the Missive **draft** appeared with its PDF attachment (not sent). Check the end-of-run summary shows every brand as enqueued / skipped-no-sales / reconcile-failed — none should silently vanish.

### 7. Disable the old desktop task
Once a Run-now produces correct drafts, disable the local task `firehouse-weekly-sales-report` (Cowork → Scheduled tasks) so it doesn't double-enqueue. Keep it — don't delete — until you've seen a real Monday cloud run land.

## Why the logo is stored as base64 (`logo_0.png.b64`)
An earlier version committed a raw binary `logo_0.png`. Some git/CI clone environments silently apply line-ending normalization to files they don't recognize as binary, which corrupted the PNG on checkout with no error. The fix: store the logo as base64 **text** (`logo_0.png.b64`) and have `build_report.py` inline it as a data URI. Text can't be corrupted this way. `.gitattributes` (forcing `*.png binary`) is kept only as defense-in-depth for any future binary asset.

## Honest caveats
1. **Connector parity in the cloud** — Jarvio + Google Drive should behave the same headless, but the exact Jarvio tool set behaving identically is the thing to watch in the step-6 test run.
2. **HTML→PDF fidelity** — the PDF is rendered by Google's built-in `Blob.getAs('application/pdf')` converter, which is weak: it ignores CSS `background-color` on divs, mishandles `inline-block`, and drops SVG. A Chrome-based renderer was built to replace it but was never set up — it's parked outside this repo if you want to pick that up later. Because of this, `build_report.py` builds the report the same table-based, `bgcolor`-filled way as the cover note, and as of 2026-09-07 the top-12 revenue bar chart and the inventory legend were removed from it because they didn't render reliably through this converter. **Spot-check the first PDF after any change to `build_report.py`:** confirm the KPI cards, the availability pills, and the zebra rows on the product table all show their fills — that's exactly what this converter tends to drop.
3. **Profit method** — per-SKU fee rates are derived from a few settled days; the step-7 reconcile guard holds back any brand whose SKU profits don't sum to the orderMetrics total. Spot-check 2–3 brands' first drafts against Seller Central before trusting them unattended.
