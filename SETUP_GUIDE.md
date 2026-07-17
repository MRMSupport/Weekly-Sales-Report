# MegaRhino Weekly Sales Report → Claude Code Routine — setup guide

## What this does
Runs the Monday weekly report in the cloud on **Claude Code Routines** (Anthropic-managed, runs on schedule even when your laptop is closed) instead of on a desktop. It runs for **every client brand opted in via the "Brand Info" sheet**: one PDF and one Missive **draft** per brand. Same profit logic, same design, draft-only delivery. The webhook POST goes direct (curl) instead of through a browser extension, and the schedule is **Monday 10 PM Philippine time** (≈ Mon 7 AM US-Pacific — late enough in the fee-settlement cycle that numbers are settled).

Firehouse keeps its Light/Dark/Tacky families; every other brand is grouped one row per parent ASIN. Each draft's To/Cc come from the sheet (blank = no recipient, routed manually in Missive, as today).

## Prerequisite (plan gate)
Routines require **Claude Code on the web enabled** on your plan (Pro, Max, Team, or Enterprise; research preview). Turn it on at [claude.ai/code](https://claude.ai/code) (connect GitHub when prompted). On **Team/Enterprise**, an Owner must not have the Routines toggle off at claude.ai/admin-settings/claude-code. If step 2 below shows no cloud option, this is the blocker.

## Steps

### 1. Put this bundle in a GitHub repo
A Routine clones a GitHub repo — it can't read your local folder. Create a private repo (e.g. `megarhino/weekly-sales-report`) and push the contents of this `weekly-sales-report/` folder:
- `build_report.py` — generalized PDF builder (reads a per-brand JSON, auto-fits any number of products, spills to more pages for big catalogs; decodes the logo from `logo_0.png.b64` at run start)
- `logo_0.png.b64` — logo as base64 text (the only tracked copy — see "Why the logo is base64" below)
- `CLAUDE.md` — method notes (auto-loaded in the clone)
- `ROUTINE_PROMPT.md` — the multi-brand workflow (paste as the routine's Instructions)
- `setup.sh` — installs reportlab
- `sample_data.json` — a synthetic example payload for local testing only
- `.gitignore` — keeps generated PDFs/JSON and the decoded `logo_0.png` out of the repo
- `.gitattributes` — optional, defense-in-depth (see below)
- `Missive Draft Creator Webhook.gs` — reference copy only (deployed separately)

`logo_0.png.b64`, `sample_data.json`, and everything else here are plain-text files, so GitHub's regular "Add file → Upload files" drag-and-drop works for all of them. Only `.gitignore` / `.gitattributes` are dotfiles; if your OS file picker hides them, add each via GitHub's web **Add file → Create new file** and type the filename directly.

### 2. Create the routine
At [claude.ai/code/routines](https://claude.ai/code/routines) → **New routine** (or Desktop app → Routines → New → **Remote**, or CLI `/schedule`):
- **Name:** MegaRhino Weekly Sales Report (all brands)
- **Instructions:** paste the full contents of `ROUTINE_PROMPT.md`
- **Repository:** the repo from step 1
- **Trigger → Schedule:** Weekly, **Monday, 10:00 PM**. Times are entered in your local zone and converted automatically, so set 10 PM in Philippine time.

One session processes all opted-in brands sequentially, so expect a longer run than a single-brand job. Mind the per-account daily run cap shown at claude.ai/code/routines (this is one run/week, well within it).

### 3. Environment — TWO gotchas that will silently break it
Edit the routine's environment (cloud icon under Instructions → settings):

- **Setup script:** `pip install --break-system-packages reportlab` (or point it at `setup.sh`). Without reportlab, `build_report.py` won't run.
- **Network access → Custom:** add these two domains, keep "include default package managers" checked:
  ```
  script.google.com
  script.googleusercontent.com
  ```
  The default **Trusted** network does NOT allow Google Apps Script hosts, so the webhook curl fails with `403 host_not_allowed`. A run can show **green** (no infra error) while no draft is created — blocked requests show only in the transcript, not the status dot. This is the #1 thing to get right.

### 4. Connectors
In the routine's **Connectors** tab, keep **Jarvio** and **Google Drive** enabled (remove the rest to limit scope). These are your claude.ai integrations; their traffic routes through Anthropic, so they need no allowlist. The Missive webhook is NOT a connector — it's the direct curl in step 8 of the prompt, which is why step 3's allowlist matters.

### 5. Team-plan re-check (do this when moving/re-configuring on the Team plan)
Connectors and environment settings do **not** carry over from a personal account — they are per-account (and, for Routines, per-routine). No IDs in this bundle change; only re-authorize the hosts. Confirm, in order:
1. **Code on web enabled** for the Team account (see Prerequisite), and the admin Routines toggle is on.
2. **Jarvio connected** under Settings → Connectors on the Team account, and enabled on this routine. Re-run `list_brands` in a test to confirm the brand set and tenant IDs look right on this account.
3. **Google Drive connected** on the Team account and enabled on this routine. This connector is used for BOTH reading the Brand Info sheet (`read_file_content`) and uploading each PDF (`create_file`). If it isn't authorized, the run STOPs at brand selection (can't read the sheet). The routine now also has an **inline-base64 fallback** so a Drive *upload* failure alone still produces the draft — but reading the sheet still needs Drive.
4. **Network allowlist re-added** (step 3) on this routine — it does not migrate.
5. **Missive webhook still live:** open the `/exec` URL in a browser; a healthy deploy returns `{"status":"ok",...}`. The token/URL in this bundle are unchanged.

### 6. Test before trusting it
Open the routine → **Run now**, then open the run session and read the transcript (don't trust the green dot). Confirm it: read the Brand Info sheet; built the opted-in brand list (MR and Zoni excluded, GWTD CA deduped); and for at least the first couple of brands pulled data, built the PDF, attached it (Drive or inline-fallback), got `status:success 201`, and left a Missive **draft** (not sent). Check the end-of-run summary shows every brand as drafted / skipped-no-sales / reconcile-failed — none should silently vanish. Fix the environment if any webhook 403'd.

### 7. Disable the old desktop task
Once a Run-now produces correct drafts, disable the local task `firehouse-weekly-sales-report` (Cowork → Scheduled tasks) so it doesn't double-draft Firehouse. Keep it — don't delete — until you've seen a real Monday cloud run land.

## Why the logo is stored as base64 (`logo_0.png.b64`)
An earlier version committed a raw binary `logo_0.png`. Some git/CI clone environments silently apply line-ending normalization to files they don't recognize as binary, which corrupted the PNG on checkout with no error — `qpdf --check` on the delivered PDF reported `error decoding stream data for object 3 0: ... invalid distance too far back` (object 3 = the embedded logo), and Missive showed "Failed to load PDF document." The fix: store the logo as base64 **text** (`logo_0.png.b64`) and have `build_report.py` decode it to `logo_0.png` at the start of every run. Text can't be corrupted this way, and `.gitignore` keeps the decoded PNG out of the repo. `.gitattributes` (forcing `*.png binary`) is kept only as defense-in-depth for any future binary asset; the pipeline no longer depends on it. Verified: the decoded logo is byte-identical to the known-good original (md5 `a0f20964bf1ffb967c511e0c96b02295`), and a full build + `qpdf --check` reports zero stream/object errors.

## Honest caveats
1. **Connector parity in the cloud** — Jarvio + Google Drive should behave the same headless, but the exact Jarvio tool set behaving identically is the thing to watch in the step-6 test run.
2. **Parent-ASIN grouping** — Firehouse was verified against manual numbers; other brands' parent-ASIN roll-up and per-group fee rates have NOT been reconciled against a known-good report. Spot-check 2–3 brands' first drafts against Seller Central before trusting them unattended. The step-7 reconcile guard holds back any brand whose group profits don't sum to the total, but it can't catch a wrong grouping that still sums correctly.
