/**
 * Client Success Queue Mailer — Google Apps Script
 * =================================================
 * Runs on Google's side (a time-driven trigger), so there is NO sandbox egress
 * limit and NO domain verification needed — it sends as the Google account that
 * owns this script.
 *
 * Two jobs each run (see runQueue):
 *   1) ingestOutbox_()  — read job files the routine dropped in a Drive "outbox"
 *                         folder and append them as rows in the queue sheet.
 *   2) processQueue_()  — for each "Pending" row: build attachments (render the
 *                         PDF from the HTML if asked), send or draft via Gmail or
 *                         Missive per the row's markers, then mark Completed/Error.
 *
 * Columns are matched BY HEADER NAME (row 1), not by position — so you can
 * reorder or add columns freely. Edit CONFIG.HEADERS if you rename any.
 */

// ============================ CONFIG ============================
const CONFIG = {
  // The queue spreadsheet + tab (from your URL).
  SHEET_ID: '1oZw5mSqO2YDvbPkYAcAz6NaO8PJG4RZcxxrVszyb5pY',
  SHEET_GID: 702254193,

  // Drive folder where the routine drops job JSON files (the outbox).
  OUTBOX_FOLDER_ID: '1Va4VHJFydqAjq9piydQFdeVnPElszFDD',

  // Where processed job files and generated attachments go. Pinned to the
  // existing subfolders in the outbox ("Archived" and "Attachments").
  // (Leave blank to auto-create "Archive"/"Attachments" instead.)
  ARCHIVE_FOLDER_ID: '16HnXBOOlTgLUKXiHS8UMiQhAaiJLUmUd',      // "Archived"
  ATTACHMENTS_FOLDER_ID: '1vW0ns5BKTZcbMIbj81DNEBuWkA6D6Os3',  // "Attachments"

  // Used only when Send App = Missive. Paste your Missive draft webhook.
  MISSIVE_WEBHOOK_URL: 'PASTE_MISSIVE_WEBHOOK_URL',

  // Display name on outgoing Gmail.
  GMAIL_SENDER_NAME: 'MegaRhino Client Success',

  // Logical field -> exact column header text in row 1 of the sheet.
  HEADERS: {
    timestamp:      'Timestamp',
    sendType:       'Send Type',      // "Send Now" | "Draft"
    sendApp:        'Send App',       // "Gmail" | "Missive"
    subject:        'Subject',
    htmlBody:       'HTML Body',
    attachments:    'Attachments',    // Drive fileIds / URLs (comma or newline sep), or "PDF_FROM_HTML:<name>.pdf"
    sendAs:         'Send As',        // from address or "noreply"
    to:             'To',             // recipient(s), comma-separated  (ADD THIS COLUMN)
    cc:             'CC',             // cc(s), comma-separated         (ADD THIS COLUMN)
    status:         'Status',         // "Pending" | "Completed" | "Error"
    completionDate: 'Completion Date',
    errorLog:       'Error Log',
  },
};

// ======================= ENTRY POINTS ==========================

/** Trigger target. Runs ingest then process. */
function runQueue() {
  ingestOutbox_();
  processQueue_();
}

/** Run once, manually, to install a 10-minute recurring trigger. */
function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'runQueue') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('runQueue').timeBased().everyMinutes(10).create();
}

// ========================= INGEST ==============================

function ingestOutbox_() {
  if (!CONFIG.OUTBOX_FOLDER_ID || CONFIG.OUTBOX_FOLDER_ID.indexOf('PASTE') === 0) return;
  var folders = resolveFolders_();
  var files = folders.outbox.getFilesByType('application/json'); // lists files in the outbox only, not subfolders
  var sh = getSheet_();
  var map = headerMap_(sh);

  while (files.hasNext()) {
    var f = files.next();
    var job, htmlBody;
    try {
      job = JSON.parse(f.getBlob().getDataAsString());
      // The routine/skill gzip+base64 the HTML into htmlBodyGz to keep the job
      // JSON small (Drive create_file silently truncates writes above ~16 KB
      // base64). Decompress it here. Plain htmlBody is still honored for
      // backward compatibility. A job with a present-but-undecompressable
      // htmlBodyGz throws and is skipped (left in place for inspection) rather
      // than sent with an empty body.
      htmlBody = resolveHtmlBody_(job);
    } catch (e) {
      // Malformed job file or unreadable body — leave it in place for a human, skip.
      continue;
    }
    var row = new Array(map.lastCol).fill('');
    setCell_(row, map.idx, 'timestamp',   job.timestamp || new Date().toISOString());
    setCell_(row, map.idx, 'sendType',    job.sendType || 'Send Now');
    setCell_(row, map.idx, 'sendApp',     job.sendApp || 'Gmail');
    setCell_(row, map.idx, 'subject',     job.subject || '');
    setCell_(row, map.idx, 'htmlBody',    htmlBody || '');
    setCell_(row, map.idx, 'attachments', job.attachments || '');
    setCell_(row, map.idx, 'sendAs',      job.sendAs || '');
    setCell_(row, map.idx, 'to',          job.to || '');
    setCell_(row, map.idx, 'cc',          job.cc || '');
    setCell_(row, map.idx, 'status',      'Pending');
    sh.appendRow(row);

    // Job is now recorded in the Sheet → archive the job file.
    f.moveTo(folders.archive);
  }
}

/**
 * Return the HTML body for a job. Prefers gzipped `htmlBodyGz` (base64 of
 * gzip bytes), falling back to a plain `htmlBody`. Throws if a present
 * htmlBodyGz cannot be decoded/decompressed, so the caller can skip the job
 * instead of ingesting an empty body.
 */
function resolveHtmlBody_(job) {
  if (job && job.htmlBodyGz) {
    var bytes = Utilities.base64Decode(job.htmlBodyGz);
    var gzBlob = Utilities.newBlob(bytes, 'application/x-gzip', 'body.html.gz');
    var html = Utilities.ungzip(gzBlob).getDataAsString('UTF-8');
    if (!html) throw new Error('htmlBodyGz decompressed to an empty string');
    return html;
  }
  return (job && job.htmlBody) || '';
}

// ========================= PROCESS =============================

function processQueue_() {
  var sh = getSheet_();
  var map = headerMap_(sh);
  var folders = resolveFolders_();
  var lastRow = sh.getLastRow();
  if (lastRow < 2) return;
  var data = sh.getRange(2, 1, lastRow - 1, map.lastCol).getValues();

  for (var r = 0; r < data.length; r++) {
    var row = data[r];
    var status = String(getCell_(row, map.idx, 'status') || '').trim().toLowerCase();
    if (status !== 'pending') continue;
    var sheetRow = r + 2;

    try {
      var sendApp  = String(getCell_(row, map.idx, 'sendApp')  || 'Gmail').trim().toLowerCase();
      var sendType = String(getCell_(row, map.idx, 'sendType') || 'Send Now').trim().toLowerCase();
      var isDraft  = sendType.indexOf('draft') >= 0;

      var attachments = buildAttachments_(
        String(getCell_(row, map.idx, 'attachments') || ''),
        String(getCell_(row, map.idx, 'htmlBody') || ''),
        String(getCell_(row, map.idx, 'subject') || ''),
        folders.attachments
      );

      if (sendApp.indexOf('missive') >= 0) {
        sendViaMissive_(row, map.idx, attachments, isDraft);
      } else {
        sendViaGmail_(row, map.idx, attachments, isDraft);
      }
      setStatus_(sh, sheetRow, map.idx, 'Completed', '');
    } catch (e) {
      setStatus_(sh, sheetRow, map.idx, 'Error', (e && e.message) ? e.message : String(e));
    }
  }
}

// ======================= ATTACHMENTS ===========================

function buildAttachments_(attachSpec, html, subject, attachmentsFolder) {
  var out = [];
  var spec = String(attachSpec || '').trim();
  if (!spec) return out;
  var parts = spec.split(/[,\n]+/).map(function (s) { return s.trim(); }).filter(Boolean);
  parts.forEach(function (p) {
    if (/^PDF_FROM_HTML/i.test(p)) {
      var name = (p.split(':')[1] || (subject || 'report')).trim();
      if (!/\.pdf$/i.test(name)) name += '.pdf';
      var pdf = renderPdfFromHtml_(html, name);
      // Save a copy of the generated PDF into the Attachments folder for the record.
      if (attachmentsFolder) { try { attachmentsFolder.createFile(pdf); } catch (e) {} }
      out.push(pdf);
    } else if (/^https?:\/\//i.test(p)) {
      out.push(UrlFetchApp.fetch(p).getBlob());
    } else {
      out.push(DriveApp.getFileById(p).getBlob()); // treat as a Drive file ID
    }
  });
  return out;
}

/** Google renders the (inline-styled) HTML to a PDF — no size limit, no upload. */
function renderPdfFromHtml_(html, name) {
  var blob = Utilities.newBlob(html, 'text/html', name.replace(/\.pdf$/i, '.html'));
  var pdf = blob.getAs('application/pdf');
  pdf.setName(name);
  return pdf;
}

// ========================= SENDERS =============================

function sendViaGmail_(row, idx, attachments, isDraft) {
  var to = String(getCell_(row, idx, 'to') || '').trim();
  if (!to) throw new Error('No "To" recipient in row');
  var cc = String(getCell_(row, idx, 'cc') || '').trim();
  var subject = String(getCell_(row, idx, 'subject') || '');
  var html = String(getCell_(row, idx, 'htmlBody') || '');
  var sendAs = String(getCell_(row, idx, 'sendAs') || '').trim();

  var options = { htmlBody: html, attachments: attachments, name: CONFIG.GMAIL_SENDER_NAME };
  if (cc) options.cc = cc;

  var sendAsLower = sendAs.toLowerCase();
  if (sendAs && sendAsLower !== 'noreply' && GmailApp.getAliases().indexOf(sendAs) >= 0) {
    // Send from a configured send-as alias (e.g. reports@megarhino.com).
    options.from = sendAs;
  } else if (sendAsLower === 'noreply' && !isDraft) {
    // Use the Workspace domain's native no-reply address. Send-only: the
    // noReply option is not valid for drafts, and only works on Google
    // Workspace accounts (ignored on consumer Gmail).
    options.noReply = true;
  }

  var plain = htmlToPlain_(html);
  if (isDraft) GmailApp.createDraft(to, subject, plain, options);
  else GmailApp.sendEmail(to, subject, plain, options);
}

function sendViaMissive_(row, idx, attachments, isDraft) {
  // Creates the draft (or sends) directly against the Missive REST API — the
  // logic ported from the old standalone "Missive Draft Creator" webhook so the
  // queue mailer no longer needs a separate webhook or MISSIVE_WEBHOOK_URL.
  var MISSIVE_TOKEN = 'missive_pat-YuvTKW-cTwG4fN6gNx6Rx5r5Pi-WOEbElXdoLbBIiUXldDxGOCVzMfitKborT2PxUg_pEg';
  var MISSIVE_ORG   = '5bb76114-3495-48b2-bf1e-02b9042530dd';
  var SENDER_NAME   = 'MegaRhino Marketing & Retail';
  var DEFAULT_FROM  = 'support@megarhino.com';

  var subject = String(getCell_(row, idx, 'subject') || '');
  var html    = String(getCell_(row, idx, 'htmlBody') || '');
  var sendAs  = String(getCell_(row, idx, 'sendAs') || '').trim();
  var fromAddr = (sendAs && sendAs.toLowerCase() !== 'noreply' && sendAs.indexOf('@') >= 0)
    ? sendAs : DEFAULT_FROM;

  // "To"/"CC" arrive as comma/semicolon-separated strings -> Missive address arrays.
  var toFields = String(getCell_(row, idx, 'to') || '')
    .split(/[,;]+/).map(function (s) { return s.trim(); })
    .filter(Boolean).map(function (a) { return { address: a }; });
  var ccFields = String(getCell_(row, idx, 'cc') || '')
    .split(/[,;]+/).map(function (s) { return s.trim(); })
    .filter(Boolean).map(function (a) { return { address: a }; });

  var draft = {
    organization: MISSIVE_ORG,
    subject: subject,
    body: html,                       // HTML body (same HTML rendered to the PDF)
    from_field: { address: fromAddr, name: SENDER_NAME },
    send: isDraft ? false : true      // false = leave as a draft; true = send now
  };
  if (toFields.length) draft.to_fields = toFields;
  if (ccFields.length) draft.cc_fields = ccFields;

  // Attachments: Missive expects RAW base64 in base64_data (NOT a data: URI).
  // Sending a "data:<type>;base64," prefix makes Missive decode that literal
  // text into the file and corrupts every attachment, so send only the bytes.
  if (attachments && attachments.length) {
    draft.attachments = attachments.map(function (b) {
      return { base64_data: Utilities.base64Encode(b.getBytes()), filename: b.getName() };
    });
  }

  var resp = UrlFetchApp.fetch('https://public.missiveapp.com/v1/drafts', {
    method: 'post',
    headers: { 'Authorization': 'Bearer ' + MISSIVE_TOKEN, 'Content-Type': 'application/json' },
    payload: JSON.stringify({ drafts: draft }),
    muteHttpExceptions: true,
  });
  var code = resp.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error('Missive API HTTP ' + code + ': ' + resp.getContentText().slice(0, 300));
  }
}

// ========================== HELPERS ============================

/** Resolve the outbox + Archive + Attachments folders (auto-create the last two if not set). */
function resolveFolders_() {
  var outbox = DriveApp.getFolderById(CONFIG.OUTBOX_FOLDER_ID);
  var archive = CONFIG.ARCHIVE_FOLDER_ID
    ? DriveApp.getFolderById(CONFIG.ARCHIVE_FOLDER_ID)
    : getOrCreateChild_(outbox, 'Archive');
  var attachments = CONFIG.ATTACHMENTS_FOLDER_ID
    ? DriveApp.getFolderById(CONFIG.ATTACHMENTS_FOLDER_ID)
    : getOrCreateChild_(outbox, 'Attachments');
  return { outbox: outbox, archive: archive, attachments: attachments };
}

function getOrCreateChild_(parent, name) {
  var it = parent.getFoldersByName(name);
  return it.hasNext() ? it.next() : parent.createFolder(name);
}

function getSheet_() {
  var ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
  var byGid = ss.getSheets().filter(function (s) { return s.getSheetId() === CONFIG.SHEET_GID; })[0];
  return byGid || ss.getSheets()[0];
}

function headerMap_(sh) {
  var lastCol = Math.max(sh.getLastColumn(), 1);
  var headers = sh.getRange(1, 1, 1, lastCol).getValues()[0].map(String);
  var idx = {};
  Object.keys(CONFIG.HEADERS).forEach(function (key) {
    idx[key] = headers.indexOf(CONFIG.HEADERS[key]); // -1 if missing
  });
  return { headers: headers, idx: idx, lastCol: lastCol };
}

function getCell_(row, idx, key) { return idx[key] >= 0 ? row[idx[key]] : ''; }
function setCell_(row, idx, key, val) { if (idx[key] >= 0) row[idx[key]] = val; }

function setStatus_(sh, sheetRow, idx, status, err) {
  if (idx.status >= 0) sh.getRange(sheetRow, idx.status + 1).setValue(status);
  if (idx.completionDate >= 0) sh.getRange(sheetRow, idx.completionDate + 1).setValue(new Date());
  if (idx.errorLog >= 0) sh.getRange(sheetRow, idx.errorLog + 1).setValue(err || '');
}

function htmlToPlain_(html) {
  return String(html).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}
