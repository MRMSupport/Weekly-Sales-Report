# v2 repo bundle — what changed and how to upload it

## What was broken (v1)
The Missive draft's PDF failed to open. Root cause: `logo_0.png` was committed to
GitHub as a raw binary file. Some git/CI clone environments silently apply
line-ending normalization to files they don't recognize as binary, which
corrupts a PNG on commit/checkout with no error — `qpdf --check` on the
delivered PDF showed `error decoding stream data for object 3 0: ... invalid
distance too far back` (object 3 = the embedded logo). The v1 fix was to add a
`.gitattributes` file forcing `*.png binary`.

## Why v1's fix was hard to deploy
`.gitattributes` starts with a dot. Most OS file-picker dialogs (Finder,
Windows Explorer) hide dotfiles by default, so when you use GitHub's drag-and-
drop / "Upload files" flow, you literally can't select it from the picker.
That's a local OS quirk, not a GitHub restriction — but it blocked you.

## What's different in v2
**The logo is no longer stored as a raw binary file at all**, so there's
nothing for line-ending normalization to corrupt, and no dotfile you're
forced to upload:

- `logo_0.png.b64` — the logo, base64-encoded as plain text. This is the only
  copy of the logo tracked in git.
- `build_report.py` now decodes it to a real `logo_0.png` at the start of
  every run (see `_ensure_logo()` near the top of the file). This always
  re-decodes from the `.b64` source, so even if a corrupted `logo_0.png` ever
  ended up in the working tree, it can't shadow the good one.
- `.gitignore` excludes the decoded `logo_0.png` from commits.
- `.gitattributes` is still included for defense-in-depth (in case a real
  binary asset like a sample PDF gets added later), but the report pipeline
  no longer depends on it.

Verified locally: decoded `logo_0.png.b64` is byte-identical (md5
`a0f20964bf1ffb967c511e0c96b02295`) to the known-good logo from the original
diagnosis, and a full `build_report.py` run + `qpdf --check` on the output
reports zero stream/object errors (see below).

## How to upload this to GitHub
1. Create (or reuse) the private repo, e.g. `megarhino/weekly-sales-report`.
2. Upload every file in this folder **except none are dotfiles you need to
   fight your file picker for** — `logo_0.png.b64` is a normal `.b64` text
   file, so GitHub's regular "Add file → Upload files" drag-and-drop works
   fine for everything here.
3. Optional, for defense-in-depth: add `.gitattributes` via GitHub's web UI
   directly instead of uploading — click **Add file → Create new file**,
   type `.gitattributes` as the filename (the web form lets you type any
   name, dotfiles included), paste the contents from this folder's
   `.gitattributes`, and commit. This sidesteps the file-picker problem
   entirely since nothing is "uploaded" from your disk.
4. Everything else (`CLAUDE.md`, `ROUTINE_PROMPT.md`, `setup.sh`,
   `.gitignore`, `Missive Draft Creator Webhook.gs`) is a plain text file —
   upload normally.

## Files in this bundle
- `build_report.py` — PDF generator (updated: decodes logo from base64 at run start)
- `logo_0.png.b64` — logo, base64 text (NEW — replaces the old raw `logo_0.png`)
- `CLAUDE.md` — repo notes, auto-loaded by the clone (updated)
- `ROUTINE_PROMPT.md` — paste as the routine's Instructions (updated, one-line logo note)
- `setup.sh` — installs reportlab (unchanged)
- `.gitignore` — updated to exclude the generated `logo_0.png`
- `.gitattributes` — unchanged content, now optional/defense-in-depth only
- `Missive Draft Creator Webhook.gs` — reference copy (unchanged)

Everything else in the original **Remote Setup Guide.md** (routine creation,
schedule, network allowlist for `script.google.com` /
`script.googleusercontent.com`, connectors, testing steps) is unaffected by
this change — follow that guide for the rest of the setup.
