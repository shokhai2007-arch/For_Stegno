/**
 * StegoVault — Main JavaScript
 * HTML bilan to'liq mos. Barcha nomuvofiqliklar to'g'irlandi.
 *
 * TO'G'RILANGAN MUAMMOLAR:
 *  1. Audio drop-zone: .drop-hint optional — HTML da ba'zi zonalarda yo'q
 *  2. Audio encode: progress bar animatsiyasi qo'shildi (HTML da bor edi, JS da yo'q edi)
 *  3. Audio decode: progress bar animatsiyasi qo'shildi (HTML da bor edi, JS da yo'q edi)
 *  4. Video decode: a.download hardcode 'recovered_file.bin' edi →
 *                   Content-Disposition headerdan asl fayl nomi o'qiladi
 *  5. Video encoded input: accept="video/*" ZIP yuklab bo'lmaydi →
 *                          JS orqali accept atributi kengaytirildi
 *  6. Progress yordamchi funksiyalari: showProgress / hideProgress — takroriy kod yo'q
 *  7. Audio encode: apiPost ishlatardi, lekin blob qaytarilishi kerak bo'lganda
 *                   to'g'ridan fetch ishlatiladi (video bilan bir xil pattern)
 */

'use strict';

/* ═══════════════════════════════════════════════════════════════════════════
   YORDAMCHI FUNKSIYALAR
═══════════════════════════════════════════════════════════════════════════ */

const $ = id => document.getElementById(id);

function show(el) { if (el) el.hidden = false; }
function hide(el) { if (el) el.hidden = true;  }

function setLoading(btn, isLoading) {
    if (!btn) return;
    const label   = btn.querySelector('.btn-label');
    const spinner = btn.querySelector('.btn-spinner');
    btn.disabled = isLoading;
    if (label)   label.hidden   = isLoading;
    if (spinner) spinner.hidden = !isLoading;
}

function showError(boxId, msg) {
    const box = $(boxId);
    if (!box) return;
    box.textContent = '⚠  ' + msg;
    show(box);
}

function clearError(boxId) {
    hide($(boxId));
}

function fmtBytes(n) {
    if (n < 1024)         return `${n} B`;
    if (n < 1024 * 1024)  return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

/** Blob yuklab olish — asl fayl nomini Content-Disposition dan oladi */
function triggerBlobDownload(blob, fallbackName) {
    const url = URL.createObjectURL(blob);
    const a   = document.createElement('a');
    a.href     = url;
    a.download = fallbackName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/** Data URL yuklab olish (image/audio base64 uchun) */
function triggerDownload(dataUrl, filename) {
    const a = Object.assign(document.createElement('a'), {
        href: dataUrl, download: filename
    });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

/**
 * Response headeridan fayl nomini ajratib oladi.
 * Content-Disposition: attachment; filename="secret.pdf"
 */
function getFilenameFromResponse(response, fallback) {
    const cd    = response.headers.get('Content-Disposition') || '';
    const match = cd.match(/filename\*?=(?:UTF-8'')?["']?([^;"'\r\n]+)["']?/i);
    return match ? decodeURIComponent(match[1].trim()) : fallback;
}

/* ── Progress yordamchilari ───────────────────────────────────────────── */

function showProgress(containerId, fillId) {
    const container = $(containerId);
    const fill      = $(fillId);
    if (container) { container.hidden = false; }
    if (fill)      { fill.style.width = '0%';  }
}

function finishProgress(containerId, fillId) {
    const container = $(containerId);
    const fill      = $(fillId);
    if (fill) fill.style.width = '100%';
    setTimeout(() => {
        if (container) container.hidden = true;
        if (fill)      fill.style.width = '0%';
    }, 800);
}

function hideProgress(containerId) {
    const container = $(containerId);
    if (container) container.hidden = true;
}

/* ── Toast bildirishi ─────────────────────────────────────────────────── */

function showToast(message, isError = false) {
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed; bottom: 24px; right: 24px;
        background: ${isError ? '#e53e3e' : '#38a169'};
        color: white; padding: 12px 24px; border-radius: 10px;
        z-index: 10000; font-size: 14px; font-weight: 500;
        box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        animation: sv-slideIn 0.3s ease;
    `;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'sv-slideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Toast animatsiya CSS
const _toastStyle = document.createElement('style');
_toastStyle.textContent = `
    @keyframes sv-slideIn {
        from { transform: translateX(120%); opacity: 0; }
        to   { transform: translateX(0);   opacity: 1; }
    }
    @keyframes sv-slideOut {
        from { transform: translateX(0);   opacity: 1; }
        to   { transform: translateX(120%); opacity: 0; }
    }
`;
document.head.appendChild(_toastStyle);

/* ═══════════════════════════════════════════════════════════════════════════
   TAB ALMASHTIRISH
═══════════════════════════════════════════════════════════════════════════ */

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

/* ═══════════════════════════════════════════════════════════════════════════
   API YORDAMCHISI (JSON javoblar uchun)
═══════════════════════════════════════════════════════════════════════════ */

async function apiPost(url, body, isJson = true) {
    const options = { method: 'POST', body: isJson ? JSON.stringify(body) : body };
    if (isJson) options.headers = { 'Content-Type': 'application/json' };

    try {
        const resp = await fetch(url, options);
        let data;
        const ct = resp.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
            data = await resp.json();
        }

        if (resp.ok) return data || { ok: true };

        if (resp.status === 413) return { ok: false, error: 'Fayl juda katta (maks: 2 GB).' };
        if (resp.status === 404) return { ok: false, error: 'API endpoint topilmadi (404).' };
        if (resp.status >= 500)  return { ok: false, error: 'Server xatosi. Qayta urinib ko\'ring.' };

        return { ok: false, error: (data?.error) || `Xato: ${resp.statusText} (${resp.status})` };

    } catch (err) {
        console.error('Fetch xatosi:', err);
        return { ok: false, error: 'Ulanish xatosi. Server ishlaётganini tekshiring.' };
    }
}

/* ═══════════════════════════════════════════════════════════════════════════
   DROP-ZONE SOZLASH
═══════════════════════════════════════════════════════════════════════════ */

/**
 * Drop-zone ni file input bilan ulaydi.
 * onFile(file) — fayl tanlanganda chaqiriladi.
 *
 * TO'G'RILANDI: .drop-hint optional — HTML da ba'zi zonalarda yo'q
 */
function setupDropZone(zoneId, inputId, onFile) {
    const zone  = $(zoneId);
    const input = $(inputId);
    if (!zone || !input) return;

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

function syncInput(input, file) {
    try {
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
    } catch (e) { /* eski brauzerlar uchun */ }
}

/** Rasm preview ko'rsatish */
function previewImage(file, imgId, zoneId, innerId) {
    const reader = new FileReader();
    reader.onload = e => {
        const img  = $(imgId);
        const zone = $(zoneId);
        if (img)  { img.src = e.target.result; img.hidden = false; }
        if (innerId) { const inner = $(innerId); if (inner) inner.style.display = 'none'; }
        if (zone) zone.classList.add('has-file');
    };
    reader.readAsDataURL(file);
}

/**
 * Drop-zone matnini va ikonkasini yangilaydi.
 * TO'G'RILANDI: .drop-text, .drop-hint, .drop-icon hammasi optional tekshiriladi.
 * Audio/video drop-zone larda .drop-hint yo'q — null-check bilan xato berilmaydi.
 * TO'G'RILANDI: .drop-icon ham yangilanadi (fayl kengaytmasiga mos emoji).
 */
function updateDropZoneText(zoneId, name, hint) {
    const zone = $(zoneId);
    if (!zone) return;
    const textEl = zone.querySelector('.drop-text');
    const hintEl = zone.querySelector('.drop-hint');
    const iconEl = zone.querySelector('.drop-icon');
    if (textEl) textEl.textContent = name;
    if (hintEl && hint !== undefined) hintEl.textContent = hint;
    if (iconEl) iconEl.textContent = fileIcon(name);   // ← fayl turiga mos ikonka
    zone.classList.add('has-file');
}

function resetDropZone(zoneId, inputId, defaultText, defaultHint) {
    const zone  = $(zoneId);
    const input = $(inputId);
    if (zone) {
        const textEl = zone.querySelector('.drop-text');
        const hintEl = zone.querySelector('.drop-hint');
        if (textEl) textEl.textContent = defaultText;
        if (hintEl && defaultHint !== undefined) hintEl.textContent = defaultHint;
        zone.classList.remove('has-file');
    }
    if (input) input.value = '';
}

/* ═══════════════════════════════════════════════════════════════════════════
   MATN — ENCODE
═══════════════════════════════════════════════════════════════════════════ */

$('btn-text-encode').addEventListener('click', async () => {
    clearError('text-encode-error');
    hide($('text-encode-result'));

    const cover  = $('txt-cover').value;
    const secret = $('txt-secret').value;

    if (!cover.trim())  { showError('text-encode-error', 'Cover text kiritilmadi.');  return; }
    if (!secret.trim()) { showError('text-encode-error', 'Secret text kiritilmadi.'); return; }

    setLoading($('btn-text-encode'), true);
    const data = await apiPost('/api/text/encode', { cover, secret });
    setLoading($('btn-text-encode'), false);

    if (!data.ok) { showError('text-encode-error', data.error); return; }
    $('text-encode-output').textContent = data.result;
    show($('text-encode-result'));
});

/* ── Clipboard nusxa ──────────────────────────────────────────────────── */

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
    if (toast) {
        toast.hidden = false;
        toast.style.animation = 'none';
        toast.offsetHeight;
        toast.style.animation = '';
        setTimeout(() => hide(toast), 2100);
    }
});

/* ═══════════════════════════════════════════════════════════════════════════
   MATN — DECODE
═══════════════════════════════════════════════════════════════════════════ */

$('btn-text-decode').addEventListener('click', async () => {
    clearError('text-decode-error');
    hide($('text-decode-result'));

    const encoded = $('txt-encoded').value;
    if (!encoded.trim()) { showError('text-decode-error', 'Encoded text kiritilmadi.'); return; }

    setLoading($('btn-text-decode'), true);
    const data = await apiPost('/api/text/decode', { encoded });
    setLoading($('btn-text-decode'), false);

    if (!data.ok) { showError('text-decode-error', data.error); return; }
    $('text-decode-output').textContent = data.secret;
    show($('text-decode-result'));
});

/* ═══════════════════════════════════════════════════════════════════════════
   RASM — COVER DROP-ZONE + SIG'IM
═══════════════════════════════════════════════════════════════════════════ */

let coverCapacityBytes = null;

setupDropZone('drop-cover', 'img-cover', async file => {
    previewImage(file, 'cover-preview', 'drop-cover', 'drop-cover-inner');
    hide($('capacity-badge'));
    coverCapacityBytes = null;
    updateSizeWarning();

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

/* ═══════════════════════════════════════════════════════════════════════════
   RASM — SECRET FILE DROP-ZONE
═══════════════════════════════════════════════════════════════════════════ */

let secretFileSize = null;

setupDropZone('drop-secret', 'img-secret-file', file => {
    secretFileSize = file.size;
    syncInput($('img-secret-file'), file);

    $('secret-file-name').textContent = file.name;
    $('secret-file-size').textContent = fmtBytes(file.size);
    show($('secret-file-info'));

    const zone  = $('drop-secret');
    const inner = $('drop-secret-inner');
    if (inner) {
        const icon = inner.querySelector('.drop-icon');
        const text = inner.querySelector('.drop-text');
        const hint = inner.querySelector('.drop-hint');
        if (icon) icon.textContent = fileIcon(file.name);
        if (text) text.textContent = file.name;
        if (hint) hint.textContent = fmtBytes(file.size);
    }
    if (zone) zone.classList.add('has-file');
    updateSizeWarning();
});

function fileIcon(name) {
    const ext = name.split('.').pop().toLowerCase();
    const map = {
        pdf: '📄', zip: '📦', rar: '📦', '7z': '📦',
        mp3: '🎵', wav: '🎵', flac: '🎵', ogg: '🎵',
        mp4: '🎬', avi: '🎬', mkv: '🎬', mov: '🎬',
        png: '🖼', jpg: '🖼', jpeg: '🖼', gif: '🖼', webp: '🖼',
        doc: '📝', docx: '📝', txt: '📝', md: '📝',
        xls: '📊', xlsx: '📊', csv: '📊',
        exe: '⚙️', sh: '⚙️', py: '🐍', js: '📜',
    };
    return map[ext] || '📎';
}

function updateSizeWarning() {
    const warning  = $('size-warning');
    const warnText = $('size-warning-text');
    if (!warning || !warnText) return;

    if (secretFileSize === null || coverCapacityBytes === null) {
        hide(warning);
        return;
    }

    const overhead    = 260;
    const neededBytes = secretFileSize + overhead;

    if (neededBytes > coverCapacityBytes) {
        const deficit = neededBytes - coverCapacityBytes;
        warnText.textContent =
            `Fayl ${fmtBytes(deficit)} oshib ketadi. ` +
            `Kattaroq rasm yoki kichikroq fayl ishlating. ` +
            `Joriy sig'im: ${fmtBytes(coverCapacityBytes - overhead)}.`;
        show(warning);
    } else {
        hide(warning);
    }
}

/* ═══════════════════════════════════════════════════════════════════════════
   RASM — ENCODE
═══════════════════════════════════════════════════════════════════════════ */

let encodedImageDataUrl = null;

$('btn-image-encode').addEventListener('click', async () => {
    clearError('image-encode-error');
    hide($('image-encode-result'));
    encodedImageDataUrl = null;

    const coverInput  = $('img-cover');
    const secretInput = $('img-secret-file');

    if (!coverInput.files[0])  { showError('image-encode-error', 'Cover rasm yuklanmadi.');  return; }
    if (!secretInput.files[0]) { showError('image-encode-error', 'Yashirin fayl yuklanmadi.'); return; }

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
    triggerDownload(encodedImageDataUrl, 'stego_encoded.png');
    showToast('🔒 Rasm muvaffaqiyatli kodlandi!');
});

$('btn-download-encoded').addEventListener('click', () => {
    if (encodedImageDataUrl) triggerDownload(encodedImageDataUrl, 'stego_encoded.png');
});

/* ═══════════════════════════════════════════════════════════════════════════
   RASM — DECODE
═══════════════════════════════════════════════════════════════════════════ */

setupDropZone('drop-encoded', 'img-encoded', file => {
    previewImage(file, 'encoded-preview', 'drop-encoded', 'drop-encoded-inner');
});

let recoveredFileDataUrl = null;
let recoveredFilename    = null;

$('btn-image-decode').addEventListener('click', async () => {
    clearError('image-decode-error');
    hide($('image-decode-result'));
    recoveredFileDataUrl = null;
    recoveredFilename    = null;

    const encodedInput = $('img-encoded');
    if (!encodedInput.files[0]) {
        showError('image-decode-error', 'Kodlangan rasm yuklanmadi.');
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

    $('recover-filename').textContent = data.filename;
    $('recover-size').textContent     = fmtBytes(data.size);

    const iconEl = $('file-recover-info')?.querySelector('.file-recover-icon');
    if (iconEl) iconEl.textContent = fileIcon(data.filename);

    show($('image-decode-result'));
    showToast('🔓 Yashirin fayl topildi!');
});

$('btn-download-decoded').addEventListener('click', () => {
    if (recoveredFileDataUrl && recoveredFilename) {
        triggerDownload(recoveredFileDataUrl, recoveredFilename);
    }
});

/* ═══════════════════════════════════════════════════════════════════════════
   AUDIO — ENCODE
   TO'G'RILANDI:
    - apiPost emas, fetch blob (server WAV qaytaradi)
    - progress bar animatsiyasi qo'shildi (HTML da bor edi)
    - .drop-hint optional
═══════════════════════════════════════════════════════════════════════════ */

setupDropZone('drop-audio-cover', 'audio-cover', file => {
    // TO'G'RILANDI: .drop-hint yo'q bo'lsa xato bermasligi uchun updateDropZoneText ishlatiladi
    updateDropZoneText('drop-audio-cover', file.name, fmtBytes(file.size));
});

setupDropZone('drop-audio-secret', 'audio-secret-file', file => {
    updateDropZoneText('drop-audio-secret', file.name, fmtBytes(file.size));
});

$('btn-audio-encode').addEventListener('click', async () => {
    const btn = $('btn-audio-encode');
    clearError('audio-encode-error');

    const coverInput  = $('audio-cover');
    const secretInput = $('audio-secret-file');

    if (!coverInput.files[0])  { showError('audio-encode-error', 'Cover audio yuklanmadi.');  return; }
    if (!secretInput.files[0]) { showError('audio-encode-error', 'Yashirin fayl yuklanmadi.'); return; }

    const fd = new FormData();
    fd.append('cover',       coverInput.files[0]);
    fd.append('secret_file', secretInput.files[0]);

    try {
        setLoading(btn, true);
        // TO'G'RILANDI: progress bar HTML da bor, lekin JS da ishlatilmagan edi
        showProgress('audio-encode-progress-container', 'audio-encode-progress');

        const response = await fetch('/api/audio/encode', { method: 'POST', body: fd });

        if (!response.ok) {
            let errMsg = 'Server xatosi';
            try { const e = await response.json(); errMsg = e.error || errMsg; } catch {}
            throw new Error(errMsg);
        }

        // Server { ok, audio_b64 } qaytaradi → base64 dan yuklab olish
        const data = await response.json();
        if (!data.ok) throw new Error(data.error || 'Kodlash xatosi');

        const audioUrl = `data:audio/wav;base64,${data.audio_b64}`;
        triggerDownload(audioUrl, 'stego_audio_encoded.wav');

        finishProgress('audio-encode-progress-container', 'audio-encode-progress');

        // Drop zonalarni tozalash
        resetDropZone('drop-audio-cover',  'audio-cover',       'Click or drag-and-drop WAV file', undefined);
        resetDropZone('drop-audio-secret', 'audio-secret-file', 'Any file to hide',                undefined);

        showToast('🔒 Audio muvaffaqiyatli kodlandi!');

    } catch (err) {
        showError('audio-encode-error', err.message);
        hideProgress('audio-encode-progress-container');
    } finally {
        setLoading(btn, false);
    }
});

/* ═══════════════════════════════════════════════════════════════════════════
   AUDIO — DECODE
   TO'G'RILANDI:
    - progress bar animatsiyasi qo'shildi (HTML da audio-decode-progress bor edi)
    - xato ko'rsatish yaxshilandi
═══════════════════════════════════════════════════════════════════════════ */

setupDropZone('drop-audio-encoded', 'audio-encoded', file => {
    updateDropZoneText('drop-audio-encoded', file.name, undefined);
});

$('btn-audio-decode').addEventListener('click', async () => {
    const btn = $('btn-audio-decode');
    clearError('audio-decode-error');

    const encodedInput = $('audio-encoded');
    if (!encodedInput.files?.[0]) {
        showError('audio-decode-error', 'Kodlangan audio yuklanmadi.');
        return;
    }

    const fd = new FormData();
    fd.append('encoded', encodedInput.files[0]);

    try {
        setLoading(btn, true);
        // TO'G'RILANDI: progress bar HTML da bor edi, JS da yo'q edi
        showProgress('audio-decode-progress-container', 'audio-decode-progress');

        const data = await apiPost('/api/audio/decode', fd, false);

        if (!data.ok) throw new Error(data.error || 'Dekodlash xatosi');

        // YANGI: natija panelini ko'rsatish
        const recoverName = $('audio-recover-filename');
        const recoverSize = $('audio-recover-size');
        const recoverIcon = $('audio-recover-info')?.querySelector('.file-recover-icon');
        if (recoverName) recoverName.textContent = data.filename || 'recovered_file';
        if (recoverSize) recoverSize.textContent = fmtBytes(data.file_b64 ? Math.round(data.file_b64.length * 3/4) : 0);
        if (recoverIcon) recoverIcon.textContent = fileIcon(data.filename || '');
        show($('audio-decode-result'));

        // Download tugmasi
        const dlBtn = $('btn-audio-download-decoded');
        if (dlBtn) {
            dlBtn.onclick = () => triggerDownload(`data:${data.mime};base64,${data.file_b64}`, data.filename || 'recovered_file');
        }

        const fileUrl = `data:${data.mime};base64,${data.file_b64}`;
        triggerDownload(fileUrl, data.filename || 'recovered_file');

        finishProgress('audio-decode-progress-container', 'audio-decode-progress');

        resetDropZone('drop-audio-encoded', 'audio-encoded', 'Upload encoded WAV', undefined);

        showToast('🔓 Yashirin fayl tiklandi: ' + (data.filename || 'fayl'));

    } catch (err) {
        showError('audio-decode-error', err.message);
        hideProgress('audio-decode-progress-container');
    } finally {
        setLoading(btn, false);
    }
});

/* ═══════════════════════════════════════════════════════════════════════════
   VIDEO — DROP-ZONE SOZLASH
   TO'G'RILANDI: video-encoded input accept="video/*,.zip" — ZIP ham yuklansin
═══════════════════════════════════════════════════════════════════════════ */

// TO'G'RILANDI: HTML da accept="video/*" edi, ZIP yuklab bo'lmasdi
const videoEncodedInput = $('video-encoded');
if (videoEncodedInput) {
    videoEncodedInput.accept = 'video/*,.zip,application/zip';
}

/* ── Video sig'im badge (image paneli kabi) ────────────────────────────── */
let videoCapacityBytes = null;

setupDropZone('drop-video-cover', 'video-cover', async file => {
    updateDropZoneText('drop-video-cover', file.name, fmtBytes(file.size));

    // Sig'im badge ni reset
    const badge = $('video-capacity-badge');
    const text  = $('video-capacity-text');
    if (badge) badge.hidden = true;
    videoCapacityBytes = null;
    updateVideoSizeWarning();

    // Serverdan sig'imni so'rash
    const fd = new FormData();
    fd.append('cover', file);
    const data = await apiPost('/api/video/capacity', fd, false);
    if (data.ok) {
        videoCapacityBytes = data.capacity_bytes;
        if (text)  text.textContent = `Sig'im: ${fmtBytes(videoCapacityBytes)}`;
        if (badge) badge.hidden = false;
        updateVideoSizeWarning();
    }
});

let videoSecretFileSize = null;

setupDropZone('drop-video-secret', 'video-secret-file', file => {
    updateDropZoneText('drop-video-secret', file.name, fmtBytes(file.size));
    videoSecretFileSize = file.size;
    updateVideoSizeWarning();
});

setupDropZone('drop-video-encoded', 'video-encoded', file => {
    updateDropZoneText('drop-video-encoded', file.name, undefined);
});

/** Video sig'im ogohlantirish (image paneli kabi) */
function updateVideoSizeWarning() {
    const warning  = $('video-size-warning');
    const warnText = $('video-size-warning-text');
    if (!warning || !warnText) return;

    if (videoSecretFileSize === null || videoCapacityBytes === null) {
        hide(warning); return;
    }
    const needed = 8 + 256 + videoSecretFileSize;
    if (needed > videoCapacityBytes) {
        const deficit = needed - videoCapacityBytes;
        warnText.textContent =
            `Fayl ${fmtBytes(deficit)} oshib ketadi. ` +
            `Kattaroq video yoki kichikroq fayl ishlating. ` +
            `Joriy sig'im: ${fmtBytes(videoCapacityBytes - 264)}.`;
        show(warning);
    } else {
        hide(warning);
    }
}

/* ═══════════════════════════════════════════════════════════════════════════
   VIDEO — ENCODE
═══════════════════════════════════════════════════════════════════════════ */

$('btn-video-encode').addEventListener('click', async () => {
    const btn = $('btn-video-encode');
    clearError('video-encode-error');

    const coverInput  = $('video-cover');
    const secretInput = $('video-secret-file');

    if (!coverInput.files[0])  { showError('video-encode-error', 'Video yuklanmadi.');          return; }
    if (!secretInput.files[0]) { showError('video-encode-error', 'Yashirin fayl yuklanmadi.');  return; }

    const fd = new FormData();
    fd.append('cover',       coverInput.files[0]);
    fd.append('secret_file', secretInput.files[0]);

    try {
        setLoading(btn, true);
        showProgress('video-encode-progress-container', 'video-encode-progress');

        const response = await fetch('/api/video/encode', { method: 'POST', body: fd });

        if (!response.ok) {
            let errMsg = 'Server xatosi';
            try { const e = await response.json(); errMsg = e.error || errMsg; } catch {}
            throw new Error(errMsg);
        }

        // ZIP blob yuklab olish
        const blob = await response.blob();
        triggerBlobDownload(blob, 'stego_video.zip');

        finishProgress('video-encode-progress-container', 'video-encode-progress');

        resetDropZone('drop-video-cover',  'video-cover',       'Upload Video (MP4, AVI)', undefined);
        resetDropZone('drop-video-secret', 'video-secret-file', 'File to hide',            undefined);

        showToast('🔒 Video muvaffaqiyatli kodlandi!');

    } catch (err) {
        console.error('Video Encode Error:', err);
        showError('video-encode-error', err.message);
        hideProgress('video-encode-progress-container');
    } finally {
        setLoading(btn, false);
    }
});

/* ═══════════════════════════════════════════════════════════════════════════
   VIDEO — DECODE
   TO'G'RILANDI:
    - a.download = 'recovered_file.bin' hardcode edi → Content-Disposition dan o'qiladi
    - YANGI: video-decode-result paneli ko'rsatiladi (image decode kabi)
═══════════════════════════════════════════════════════════════════════════ */

$('btn-video-decode').addEventListener('click', async () => {
    const btn = $('btn-video-decode');
    clearError('video-decode-error');
    hide($('video-decode-result'));

    const encodedInput = $('video-encoded');
    if (!encodedInput.files[0]) {
        showError('video-decode-error', 'Kodlangan video yuklanmadi.');
        return;
    }

    const fd = new FormData();
    fd.append('encoded', encodedInput.files[0]);

    try {
        setLoading(btn, true);
        showProgress('video-decode-progress-container', 'video-decode-progress');

        const response = await fetch('/api/video/decode', { method: 'POST', body: fd });

        if (!response.ok) {
            let errMsg = 'Server xatosi';
            try { const e = await response.json(); errMsg = e.error || errMsg; } catch {}
            throw new Error(errMsg);
        }

        // Content-Disposition dan asl fayl nomini olamiz
        const filename = getFilenameFromResponse(response, 'recovered_file.bin');
        const blob     = await response.blob();

        // YANGI: natija panelini to'ldirish
        const recoverName = $('video-recover-filename');
        const recoverSize = $('video-recover-size');
        const recoverIcon = $('video-recover-info')?.querySelector('.file-recover-icon');
        if (recoverName) recoverName.textContent = filename;
        if (recoverSize) recoverSize.textContent = fmtBytes(blob.size);
        if (recoverIcon) recoverIcon.textContent = fileIcon(filename);
        show($('video-decode-result'));

        // Download tugmasi uchun blob saqlash
        const dlBtn = $('btn-video-download-decoded');
        if (dlBtn) {
            dlBtn.onclick = () => triggerBlobDownload(blob, filename);
        }

        finishProgress('video-decode-progress-container', 'video-decode-progress');
        resetDropZone('drop-video-encoded', 'video-encoded', 'Upload encoded Video', undefined);
        showToast('🔓 Yashirin fayl tiklandi: ' + filename);

    } catch (err) {
        console.error('Video Decode Error:', err);
        showError('video-decode-error', err.message);
        hideProgress('video-decode-progress-container');
    } finally {
        setLoading(btn, false);
    }
});