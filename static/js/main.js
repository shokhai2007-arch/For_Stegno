/**
 * StegoVault — Main JavaScript
 * Handles:
 *  - Tab switching
 *  - AJAX API calls for text / image encode & decode
 *  - Copy-to-clipboard for text results
 *  - Drag-and-drop and file-input for images and generic files
 *  - Capacity badge + live size-warning for image encode
 *  - Auto-download for encoded image and recovered secret file
 */

'use strict';

/* ── Tiny Helpers ─────────────────────────────────────────────────────── */

const $ = id => document.getElementById(id);

function show(el) { el.hidden = false; }
function hide(el) { el.hidden = true;  }

function setLoading(btn, on) {
  btn.disabled = on;
  const label   = btn.querySelector('.btn-label');
  const spinner = btn.querySelector('.btn-spinner');
  on ? (hide(label), show(spinner)) : (show(label), hide(spinner));
}

function showError(boxId, msg) {
  const box = $(boxId);
  box.textContent = '⚠  ' + msg;
  show(box);
}

function clearError(boxId) { hide($(boxId)); }

function fmtBytes(n) {
  if (n < 1024)        return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function triggerDownload(dataUrl, filename) {
  const a = Object.assign(document.createElement('a'), {
    href: dataUrl, download: filename
  });
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/* ── Tab Switching ────────────────────────────────────────────────────── */

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.dataset.panel;

    document.querySelectorAll('.tab-btn').forEach(b => {
      b.classList.remove('active');
      b.setAttribute('aria-selected', 'false');
    });
    btn.classList.add('active');
    btn.setAttribute('aria-selected', 'true');

    document.querySelectorAll('.panel').forEach(panel => {
      const isTarget = panel.id === `panel-${target}`;
      panel.hidden = !isTarget;
      panel.classList.toggle('active', isTarget);
    });
  });
});

/**
 * Centralized API helper with robust error handling.
 * Maps HTTP status codes to user-friendly messages and handles network failures.
 */
async function apiPost(url, body, isJson = true) {
  const options = { method: 'POST', body: isJson ? JSON.stringify(body) : body };
  if (isJson) options.headers = { 'Content-Type': 'application/json' };

  try {
    const resp = await fetch(url, options);
    
    // Attempt to parse JSON even if status is not 200
    let data;
    const contentType = resp.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      data = await resp.json();
    }

    if (resp.ok) {
      return data || { ok: true };
    }

    // Handle known error statuses
    if (resp.status === 413) return { ok: false, error: "File is too large. Maximum limit is 32MB." };
    if (resp.status === 404) return { ok: false, error: "The requested service was not found (404)." };
    if (resp.status >= 500)  return { ok: false, error: "Server error. The system might be temporarily down." };

    // Return the error from JSON if available, otherwise generic
    return { ok: false, error: (data && data.error) ? data.error : `Error: ${resp.statusText} (${resp.status})` };

  } catch (err) {
    console.error("Fetch error:", err);
    // Likely a network / CORS / connection refused issue
    return { ok: false, error: "Connection failed. Please check your internet or ensure the server is running." };
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   TEXT — ENCODE
   ══════════════════════════════════════════════════════════════════════════ */

$('btn-text-encode').addEventListener('click', async () => {
  clearError('text-encode-error');
  hide($('text-encode-result'));

  const cover  = $('txt-cover').value;
  const secret = $('txt-secret').value;

  if (!cover.trim())  { showError('text-encode-error', 'Please enter cover text.'); return; }
  if (!secret.trim()) { showError('text-encode-error', 'Please enter a secret message.'); return; }

  setLoading($('btn-text-encode'), true);
  const data = await apiPost('/api/text/encode', { cover, secret });
  setLoading($('btn-text-encode'), false);

  if (!data.ok) { showError('text-encode-error', data.error); return; }
  $('text-encode-output').textContent = data.result;
  show($('text-encode-result'));
});

/* ── Copy to Clipboard ────────────────────────────────────────────────── */

$('btn-copy-text').addEventListener('click', async () => {
  const text = $('text-encode-output').textContent;
  if (!text) return;

  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = Object.assign(document.createElement('textarea'), {
      value: text, style: 'position:fixed;opacity:0'
    });
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }

  const toast = $('copy-toast');
  toast.hidden = false;
  toast.style.animation = 'none';
  toast.offsetHeight;           // trigger reflow
  toast.style.animation = '';
  setTimeout(() => hide(toast), 2100);
});

/* ══════════════════════════════════════════════════════════════════════════
   TEXT — DECODE
   ══════════════════════════════════════════════════════════════════════════ */

$('btn-text-decode').addEventListener('click', async () => {
  clearError('text-decode-error');
  hide($('text-decode-result'));

  const encoded = $('txt-encoded').value;
  if (!encoded.trim()) { showError('text-decode-error', 'Please paste encoded text.'); return; }

  setLoading($('btn-text-decode'), true);
  const data = await apiPost('/api/text/decode', { encoded });
  setLoading($('btn-text-decode'), false);

  if (!data.ok) { showError('text-decode-error', data.error); return; }
  $('text-decode-output').textContent = data.secret;
  show($('text-decode-result'));
});

/* ══════════════════════════════════════════════════════════════════════════
   IMAGE — DROP-ZONE SETUP
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Wire a drop-zone to a hidden file input.
 * onFile(file) is called whenever a file is chosen.
 */
function setupDropZone(zoneId, inputId, onFile) {
  const zone  = $(zoneId);
  const input = $(inputId);

  zone.addEventListener('click',   () => input.click());
  zone.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') input.click();
  });
  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('dragover');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) { syncInput(input, file); onFile(file); }
  });
  input.addEventListener('change', () => {
    const file = input.files[0];
    if (file) onFile(file);
  });
}

/** Mirror a File into a file-input's FileList via DataTransfer. */
function syncInput(input, file) {
  const dt = new DataTransfer();
  dt.items.add(file);
  input.files = dt.files;
}

/** Show image preview inside a drop-zone. */
function previewImage(file, imgId, zoneId, innerId) {
  const reader = new FileReader();
  reader.onload = e => {
    const img  = $(imgId);
    const zone = $(zoneId);
    img.src = e.target.result;
    img.hidden = false;
    if (innerId) $(innerId).style.display = 'none';
    zone.classList.add('has-file');
  };
  reader.readAsDataURL(file);
}

/* ══════════════════════════════════════════════════════════════════════════
   IMAGE ENCODE — COVER IMAGE
   ══════════════════════════════════════════════════════════════════════════ */

let coverCapacityBytes = null;   // kept in memory for size comparison

setupDropZone('drop-cover', 'img-cover', async file => {
  // Show image preview
  previewImage(file, 'cover-preview', 'drop-cover', 'drop-cover-inner');

  // Reset capacity badge
  hide($('capacity-badge'));
  coverCapacityBytes = null;
  updateSizeWarning();

  // Fetch capacity from server
  const fd = new FormData();
  fd.append('cover', file);
  
  const data = await apiPost('/api/image/capacity', fd, false);
  if (data.ok) {
    coverCapacityBytes = data.capacity_bytes;
    $('capacity-text').textContent = `Max hidden file: ${fmtBytes(coverCapacityBytes)}`;
    show($('capacity-badge'));
    updateSizeWarning();
  }
});

/* ══════════════════════════════════════════════════════════════════════════
   IMAGE ENCODE — SECRET FILE
   ══════════════════════════════════════════════════════════════════════════ */

let secretFileSize = null;

setupDropZone('drop-secret', 'img-secret-file', file => {
  secretFileSize = file.size;
  syncInput($('img-secret-file'), file);

  // Update file pill
  $('secret-file-name').textContent = file.name;
  $('secret-file-size').textContent = fmtBytes(file.size);
  const pill = $('secret-file-info');
  show(pill);

  // Style the drop zone
  const zone  = $('drop-secret');
  const inner = $('drop-secret-inner');
  inner.querySelector('.drop-icon').textContent  = fileIcon(file.name);
  inner.querySelector('.drop-text').textContent  = file.name;
  inner.querySelector('.drop-hint').textContent  = fmtBytes(file.size);
  zone.classList.add('has-file');

  updateSizeWarning();
});

/** Pick a suitable emoji icon based on file extension. */
function fileIcon(name) {
  const ext = name.split('.').pop().toLowerCase();
  const map = {
    pdf: '📕', zip: '📦', rar: '📦', '7z': '📦',
    mp3: '🎵', wav: '🎵', flac: '🎵', ogg: '🎵',
    mp4: '🎬', avi: '🎬', mkv: '🎬', mov: '🎬',
    png: '🖼️', jpg: '🖼️', jpeg: '🖼️', gif: '🖼️', webp: '🖼️',
    doc: '📝', docx: '📝', txt: '📝', md: '📝',
    xls: '📊', xlsx: '📊', csv: '📊',
    exe: '⚙️', sh: '⚙️', py: '🐍', js: '📜',
  };
  return map[ext] || '📄';
}

/**
 * Compare secretFileSize vs capacityBytes and show / hide the warning bar.
 * The server counts header overhead too; we add a conservative 300-byte buffer.
 */
function updateSizeWarning() {
  const warning = $('size-warning');
  const warnText = $('size-warning-text');

  if (secretFileSize === null || coverCapacityBytes === null) {
    hide(warning);
    return;
  }

  // Header is at most 1 + 255 + 4 = 260 bytes
  const overhead    = 260;
  const neededBytes = secretFileSize + overhead;

  if (neededBytes > coverCapacityBytes) {
    const deficit = neededBytes - coverCapacityBytes;
    warnText.textContent =
      `This file is ${fmtBytes(deficit)} too large for the selected cover image. ` +
      `Use a larger cover image or a smaller file. ` +
      `Current capacity: ${fmtBytes(coverCapacityBytes - overhead)}.`;
    show(warning);
  } else {
    hide(warning);
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   IMAGE — ENCODE BUTTON
   ══════════════════════════════════════════════════════════════════════════ */

let encodedImageDataUrl = null;

$('btn-image-encode').addEventListener('click', async () => {
  clearError('image-encode-error');
  hide($('image-encode-result'));
  encodedImageDataUrl = null;

  const coverInput  = $('img-cover');
  const secretInput = $('img-secret-file');

  if (!coverInput.files[0])  { showError('image-encode-error', 'Please upload a cover image.'); return; }
  if (!secretInput.files[0]) { showError('image-encode-error', 'Please upload a secret file.'); return; }

  const fd = new FormData();
  fd.append('cover',       coverInput.files[0]);
  fd.append('secret_file', secretInput.files[0]);

  setLoading($('btn-image-encode'), true);
  const data = await apiPost('/api/image/encode', fd, false);
  setLoading($('btn-image-encode'), false);

  if (!data.ok) { showError('image-encode-error', data.error); return; }

  encodedImageDataUrl = `data:image/png;base64,${data.image_b64}`;
  $('image-encode-output').src = encodedImageDataUrl;
  show($('image-encode-result'));

  // Auto-download
  triggerDownload(encodedImageDataUrl, 'stego_encoded.png');
});

$('btn-download-encoded').addEventListener('click', () => {
  if (encodedImageDataUrl) triggerDownload(encodedImageDataUrl, 'stego_encoded.png');
});

/* ══════════════════════════════════════════════════════════════════════════
   IMAGE — DECODE DROP-ZONE
   ══════════════════════════════════════════════════════════════════════════ */

setupDropZone('drop-encoded', 'img-encoded', file => {
  previewImage(file, 'encoded-preview', 'drop-encoded', 'drop-encoded-inner');
});

/* ══════════════════════════════════════════════════════════════════════════
   IMAGE — DECODE BUTTON
   ══════════════════════════════════════════════════════════════════════════ */

let recoveredFileDataUrl = null;
let recoveredFilename    = null;

$('btn-image-decode').addEventListener('click', async () => {
  clearError('image-decode-error');
  hide($('image-decode-result'));
  recoveredFileDataUrl = null;
  recoveredFilename    = null;

  const encodedInput = $('img-encoded');
  if (!encodedInput.files[0]) {
    showError('image-decode-error', 'Please upload an encoded image.');
    return;
  }

  const fd = new FormData();
  fd.append('encoded', encodedInput.files[0]);

  setLoading($('btn-image-decode'), true);
  const data = await apiPost('/api/image/decode', fd, false);
  setLoading($('btn-image-decode'), false);

  if (!data.ok) { showError('image-decode-error', data.error); return; }

  recoveredFilename    = data.filename;
  recoveredFileDataUrl = `data:${data.mime};base64,${data.file_b64}`;

  // Update recovery card
  $('recover-filename').textContent = data.filename;
  $('recover-size').textContent     = fmtBytes(data.size);

  // Update file icon in recovery card
  $('file-recover-info').querySelector('.file-recover-icon').textContent =
    fileIcon(data.filename);

  show($('image-decode-result'));
});

$('btn-download-decoded').addEventListener('click', () => {
  if (recoveredFileDataUrl && recoveredFilename) {
    triggerDownload(recoveredFileDataUrl, recoveredFilename);
  }
});
