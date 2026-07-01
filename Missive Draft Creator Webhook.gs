/**
 * Missive Draft Creator — Webhook (Apps Script)
 * --------------------------------------------------
 * Creates a Missive draft from a JSON POST.
 *
 * Attachments can be supplied THREE ways (use whichever is easiest):
 *   1) driveFileId:  "<Google Drive file id>"           // single file
 *   2) driveFileIds: ["<id1>", "<id2>", ...]            // multiple files
 *   3) attachments:  [{ base64_data, filename, media_type }]  // inline base64
 *
 * Prefer the Drive options for anything large (e.g. PDFs): the bytes are read
 * server-side, so you never push base64 through a browser.
 */

const MISSIVE_CONFIG = {
  token: 'missive_pat-YuvTKW-cTwG4fN6gNx6Rx5r5Pi-WOEbElXdoLbBIiUXldDxGOCVzMfitKborT2PxUg_pEg',
  organization: '5bb76114-3495-48b2-bf1e-02b9042530dd'
};

/**
 * Simple health check so opening the URL in a browser doesn't error.
 */
function doGet() {
  return ContentService
    .createTextOutput(JSON.stringify({ status: 'ok', message: 'Missive Draft Creator is live. POST JSON to create a draft.' }))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * Main Webhook Handler (handles incoming HTTP POST requests)
 */
function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      throw new Error('No data received in the request body.');
    }

    const payload = JSON.parse(e.postData.contents);

    // 1. Core draft fields
    const draftData = {
      organization: payload.organization || MISSIVE_CONFIG.organization,
      subject: payload.subject || '',
      body: payload.body || '',            // plain text or HTML
      send: payload.send || false          // true = send immediately, false = draft
    };

    // 2. From (sender)
    if (payload.from) {
      draftData.from_field = {
        address: payload.from.email || payload.from.address,
        name: payload.from.name || ''
      };
    }

    // 3. Recipients (To / CC / BCC)
    const mapRecipients = (list) => {
      if (!list || !Array.isArray(list)) return [];
      return list.map(item =>
        (typeof item === 'string')
          ? { address: item, name: '' }
          : { address: item.email || item.address, name: item.name || '' }
      );
    };
    if (payload.to)  draftData.to_fields  = mapRecipients(payload.to);
    if (payload.cc)  draftData.cc_fields  = mapRecipients(payload.cc);
    if (payload.bcc) draftData.bcc_fields = mapRecipients(payload.bcc);

    // 4. Attachments — Drive ids and/or inline base64 are all merged together
    const attachments = [];

    // 4a. Single Drive file id
    if (payload.driveFileId) {
      attachments.push(attachmentFromDrive(payload.driveFileId));
    }
    // 4b. Multiple Drive file ids
    if (payload.driveFileIds && Array.isArray(payload.driveFileIds)) {
      payload.driveFileIds.forEach(id => attachments.push(attachmentFromDrive(id)));
    }
    // 4c. Inline base64 attachments
    if (payload.attachments && Array.isArray(payload.attachments)) {
      payload.attachments.forEach(file => {
        const filename = file.filename || file.name || 'attachment';
        const type = file.media_type || file.mediaType || inferMediaType(filename);
        let data = file.base64_data || file.data || file.file || '';
        // Missive wants base64_data as a data URI and no separate media_type key.
        if (data.indexOf('data:') !== 0) data = 'data:' + type + ';base64,' + data;
        attachments.push({ base64_data: data, filename: filename });
      });
    }
    if (attachments.length > 0) {
      draftData.attachments = attachments;
    }

    // 5. Shared labels, team users, threading
    if (payload.labels && Array.isArray(payload.labels)) draftData.add_shared_labels = payload.labels;
    if (payload.users && Array.isArray(payload.users))   draftData.add_users = payload.users;
    if (payload.conversation_id) draftData.conversation = payload.conversation_id;

    // 6. Send to Missive
    const response = fetchMissiveCreateDraft(draftData);
    const code = response.getResponseCode();
    const text = response.getContentText();
    let json;
    try { json = JSON.parse(text); } catch (err) { json = text; }

    if (code >= 200 && code < 300) {
      return jsonOut({ status: 'success', code: code, data: json });
    }
    return jsonOut({ status: 'error', code: code, message: 'Missive API rejected request', details: json });

  } catch (error) {
    return jsonOut({ status: 'error', message: error.toString() });
  }
}

/**
 * Reads a Google Drive file and returns a Missive-ready attachment object.
 */
function attachmentFromDrive(fileId) {
  const file = DriveApp.getFileById(fileId);
  const blob = file.getBlob();
  const type = blob.getContentType() || inferMediaType(file.getName());
  // Missive attachments: base64_data as a data URI, filename only (no media_type key).
  return {
    base64_data: 'data:' + type + ';base64,' + Utilities.base64Encode(blob.getBytes()),
    filename: file.getName()
  };
}

/**
 * Best-effort MIME type from a filename extension.
 */
function inferMediaType(filename) {
  const ext = String(filename).split('.').pop().toLowerCase();
  const map = {
    pdf: 'application/pdf',
    png: 'image/png',
    jpg: 'image/jpeg', jpeg: 'image/jpeg',
    gif: 'image/gif',
    csv: 'text/csv',
    txt: 'text/plain',
    html: 'text/html',
    doc: 'application/msword',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    xls: 'application/vnd.ms-excel',
    xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
  };
  return map[ext] || 'application/octet-stream';
}

/**
 * Calls the Missive REST API to create the draft.
 */
function fetchMissiveCreateDraft(draftData) {
  const url = 'https://public.missiveapp.com/v1/drafts';
  const options = {
    method: 'post',
    headers: {
      'Authorization': 'Bearer ' + MISSIVE_CONFIG.token,
      'Content-Type': 'application/json'
    },
    payload: JSON.stringify({ drafts: draftData }),
    muteHttpExceptions: true
  };
  return UrlFetchApp.fetch(url, options);
}

/**
 * Helper: JSON ContentService response.
 */
function jsonOut(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
