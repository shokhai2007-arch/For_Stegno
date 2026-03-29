/**
 * StegoVault — Main JavaScript
 * Handles:
 *  - Tab switching
 *  - AJAX API calls for text/image encode & decode
 *  - Copy-to-clipboard for text results
 *  - Drag-and-drop and file input for images
 *  - Auto-download for encoded images
 */

/* ── Utilities ────────────────────────────────────────────────────────── */

function show(el) { el.hidden = false; }
function hide(el) { el.hidden = true; }

function setLoading(btn, loading) {
  const label   = btn.querySelector('.btn-label');
  const spinner = btn.querySelector('.btn-spinner');
  btn.disabled = loading;
  if (loading) { hide(label); show(spinner); }
  else         { show(label); hide(spinner); }
}

function showError(box, msg) {
  box.textContent = '⚠ ' + msg;
  show(box);
}

function clearError(box) {
  hide(box);
  box.textContent = '';
}

function triggerDownload(dataUrl, filename) {
  const a = document.createElement('a');
  a.href     = dataUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/* ── Tab Switching ────────────────────────────────────────────────────── */

const tabBtns  = document.querySelectorAll('.tab-btn');
const panels   = document.querySelectorAll('.panel');

tabBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.dataset.panel;

    tabBtns.forEach(b => {
      b.classList.remove('active');
      b.setAttribute('aria-selected', 'false');
    });
    btn.classList.add('active');
    btn.setAttribute('aria-selected', 'true');

    panels.forEach(panel => {
      if (panel.id === `panel-${target}`) {
        panel.hidden = false;
        panel.classList.add('active');
      } else {
        panel.hidden = true;
        panel.classList.remove('active');
      }
    });
  });
});

/* ── Text Encode ──────────────────────────────────────────────────────── */

const btnTextEncode   = document.getElementById('btn-text-encode');
const txtCover        = document.getElementById('txt-cover');
const txtSecret       = document.getElementById('txt-secret');
const textEncodeRes   = document.getElementById('text-encode-result');
const textEncodeOut   = document.getElementById('text-encode-output');
const textEncodeErr   = document.getElementById('text-encode-error');

btnTextEncode.addEventListener('click', async () => {
  clearError(textEncodeErr);
  hide(textEncodeRes);

  const cover  = txtCover.value;
  const secret = txtSecret.value;

  if (!cover.trim())  { showError(textEncodeErr, 'Please enter cover text.'); return; }
  if (!secret.trim()) { showError(textEncodeErr, 'Please enter a secret message.'); return; }

  setLoading(btnTextEncode, true);

  try {
    const resp = await fetch('/api/text/encode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cover, secret }),
    });
    const data = await resp.json();

    if (!data.ok) { showError(textEncodeErr, data.error || 'Encoding failed.'); return; }

    textEncodeOut.textContent = data.result;
    show(textEncodeRes);
  } catch (err) {
    showError(textEncodeErr, 'Network error: ' + err.message);
  } finally {
    setLoading(btnTextEncode, false);
  }
});

/* ── Copy to Clipboard ────────────────────────────────────────────────── */

const btnCopyText = document.getElementById('btn-copy-text');
const copyToast   = document.getElementById('copy-toast');

btnCopyText.addEventListener('click', async () => {
  const text = textEncodeOut.textContent;
  if (!text) return;

  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Fallback for older contexts
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity  = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }

  hide(copyToast);
  // Force re-animation
  copyToast.hidden = false;
  copyToast.style.animation = 'none';
  copyToast.offsetHeight;  // reflow
  copyToast.style.animation = '';

  // Hide after the animation finishes
  setTimeout(() => hide(copyToast), 2100);
});

/* ── Text Decode ──────────────────────────────────────────────────────── */

const btnTextDecode  = document.getElementById('btn-text-decode');
const txtEncoded     = document.getElementById('txt-encoded');
const textDecodeRes  = document.getElementById('text-decode-result');
const textDecodeOut  = document.getElementById('text-decode-output');
const textDecodeErr  = document.getElementById('text-decode-error');

btnTextDecode.addEventListener('click', async () => {
  clearError(textDecodeErr);
  hide(textDecodeRes);

  const encoded = txtEncoded.value;
  if (!encoded.trim()) { showError(textDecodeErr, 'Please paste encoded text.'); return; }

  setLoading(btnTextDecode, true);

  try {
    const resp = await fetch('/api/text/decode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ encoded }),
    });
    const data = await resp.json();

    if (!data.ok) { showError(textDecodeErr, data.error || 'Decoding failed.'); return; }

    textDecodeOut.textContent = data.secret;
    show(textDecodeRes);
  } catch (err) {
    showError(textDecodeErr, 'Network error: ' + err.message);
  } finally {
    setLoading(btnTextDecode, false);
  }
});

/* ── Image Drop Zone Helper ───────────────────────────────────────────── */

function setupDropZone(dropZoneId, inputId, previewId) {
  const zone    = document.getElementById(dropZoneId);
  const input   = document.getElementById(inputId);
  const preview = document.getElementById(previewId);

  // Click zone → trigger file input
  zone.addEventListener('click', () => input.click());
  zone.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') input.click();
  });

  // Drag events
  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('dragover');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) applyFile(file, input, preview, zone);
  });

  // File input change
  input.addEventListener('change', () => {
    const file = input.files[0];
    if (file) applyFile(file, input, preview, zone);
  });
}

function applyFile(file, input, preview, zone) {
  // Sync to the file input DataTransfer (so FormData picks it up)
  const dt = new DataTransfer();
  dt.items.add(file);
  input.files = dt.files;

  const reader = new FileReader();
  reader.onload = e => {
    preview.src = e.target.result;
    preview.hidden = false;
    zone.querySelector('.drop-inner').style.display = 'none';
  };
  reader.readAsDataURL(file);
}

setupDropZone('drop-cover',   'img-cover',   'cover-preview');
setupDropZone('drop-secret',  'img-secret',  'secret-preview');
setupDropZone('drop-encoded', 'img-encoded', 'encoded-preview');

/* ── Image Encode ─────────────────────────────────────────────────────── */

const btnImageEncode     = document.getElementById('btn-image-encode');
const imgEncodeRes       = document.getElementById('image-encode-result');
const imgEncodeOut       = document.getElementById('image-encode-output');
const imgEncodeErr       = document.getElementById('image-encode-error');
const btnDownloadEncoded = document.getElementById('btn-download-encoded');

let encodedImageDataUrl = null;

btnImageEncode.addEventListener('click', async () => {
  clearError(imgEncodeErr);
  hide(imgEncodeRes);
  encodedImageDataUrl = null;

  const coverInput  = document.getElementById('img-cover');
  const secretInput = document.getElementById('img-secret');

  if (!coverInput.files[0])  { showError(imgEncodeErr, 'Please upload a cover image.'); return; }
  if (!secretInput.files[0]) { showError(imgEncodeErr, 'Please upload a secret image.'); return; }

  const formData = new FormData();
  formData.append('cover',  coverInput.files[0]);
  formData.append('secret', secretInput.files[0]);

  setLoading(btnImageEncode, true);

  try {
    const resp = await fetch('/api/image/encode', { method: 'POST', body: formData });
    const data = await resp.json();

    if (!data.ok) { showError(imgEncodeErr, data.error || 'Encoding failed.'); return; }

    encodedImageDataUrl = `data:${data.mime};base64,${data.image}`;
    imgEncodeOut.src = encodedImageDataUrl;
    show(imgEncodeRes);

    // Auto-download
    triggerDownload(encodedImageDataUrl, 'stego_encoded.png');
  } catch (err) {
    showError(imgEncodeErr, 'Network error: ' + err.message);
  } finally {
    setLoading(btnImageEncode, false);
  }
});

btnDownloadEncoded.addEventListener('click', () => {
  if (encodedImageDataUrl) triggerDownload(encodedImageDataUrl, 'stego_encoded.png');
});

/* ── Image Decode ─────────────────────────────────────────────────────── */

const btnImageDecode     = document.getElementById('btn-image-decode');
const imgDecodeRes       = document.getElementById('image-decode-result');
const imgDecodeOut       = document.getElementById('image-decode-output');
const imgDecodeErr       = document.getElementById('image-decode-error');
const btnDownloadDecoded = document.getElementById('btn-download-decoded');

let decodedImageDataUrl = null;

btnImageDecode.addEventListener('click', async () => {
  clearError(imgDecodeErr);
  hide(imgDecodeRes);
  decodedImageDataUrl = null;

  const encodedInput = document.getElementById('img-encoded');
  if (!encodedInput.files[0]) { showError(imgDecodeErr, 'Please upload an encoded image.'); return; }

  const formData = new FormData();
  formData.append('encoded', encodedInput.files[0]);

  setLoading(btnImageDecode, true);

  try {
    const resp = await fetch('/api/image/decode', { method: 'POST', body: formData });
    const data = await resp.json();

    if (!data.ok) { showError(imgDecodeErr, data.error || 'Decoding failed.'); return; }

    decodedImageDataUrl = `data:${data.mime};base64,${data.image}`;
    imgDecodeOut.src = decodedImageDataUrl;
    show(imgDecodeRes);
  } catch (err) {
    showError(imgDecodeErr, 'Network error: ' + err.message);
  } finally {
    setLoading(btnImageDecode, false);
  }
});

btnDownloadDecoded.addEventListener('click', () => {
  if (decodedImageDataUrl) triggerDownload(decodedImageDataUrl, 'stego_revealed.png');
});
