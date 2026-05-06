"""
Flask Application — StegoVault
================================
Barcha endpointlar main.js bilan mos:

  TEXT:
    POST /api/text/encode     { cover, secret }         → { ok, result }
    POST /api/text/decode     { encoded }               → { ok, secret }

  IMAGE:
    POST /api/image/capacity  cover (file)              → { ok, capacity_bytes }
    POST /api/image/encode    cover + secret_file       → { ok, image_b64 }
    POST /api/image/decode    encoded (file)            → { ok, file_b64, filename, mime, size }

  AUDIO:
    POST /api/audio/encode    cover + secret_file       → { ok, audio_b64 }
    POST /api/audio/decode    encoded (file)            → { ok, file_b64, filename, mime }

  VIDEO:
    POST /api/video/encode    cover + secret_file       → ZIP blob (application/zip)
    POST /api/video/decode    encoded (ZIP yoki video)  → fayl blob (as_attachment)
"""

import base64
import io
import logging
import mimetypes
import os
import tempfile
import traceback
import zipfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from logic import (
    decode_audio_lsb,
    decode_file_from_image,
    decode_text_zero_width,
    decode_video,
    encode_audio_lsb,
    encode_file_in_image,
    encode_text_zero_width,
    encode_video,
    get_video_capacity,
    image_capacity,
)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
# TO'G'RILANDI: 64 MB → 2 GB (video fayllar uchun)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv'}


# ---------------------------------------------------------------------------
# Yordamchi funksiyalar
# ---------------------------------------------------------------------------

def _allowed_video(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_VIDEO_EXTS


def _err(msg: str, code: int = 400):
    """Barcha xatolar uchun yagona JSON format: { ok: false, error: "..." }
    main.js apiPost() funksiyasi data.error dan o'qiydi."""
    return jsonify({"ok": False, "error": msg}), code


# ---------------------------------------------------------------------------
# Global xato handlerlari
# ---------------------------------------------------------------------------

@app.errorhandler(413)
def error_413(e):
    return jsonify({"ok": False, "error": "Fayl hajmi juda katta (maks: 2 GB)."}), 413


@app.errorhandler(404)
def error_404(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "API endpoint topilmadi."}), 404
    return render_template("index.html"), 404


@app.errorhandler(500)
def error_500(e):
    logger.error(f"Unhandled Exception: {e}", exc_info=True)
    return jsonify({"ok": False, "error": "Ichki server xatosi."}), 500


# ---------------------------------------------------------------------------
# Sahifa
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# TEXT API
# ---------------------------------------------------------------------------

@app.route("/api/text/encode", methods=["POST"])
def api_text_encode():
    try:
        data   = request.get_json(force=True)
        cover  = (data.get("cover")  or "").strip()
        secret = (data.get("secret") or "").strip()

        if not cover:  return _err("Cover text kiritilmadi.")
        if not secret: return _err("Secret text kiritilmadi.")

        result = encode_text_zero_width(cover, secret)
        return jsonify({"ok": True, "result": result})

    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        logger.error(f"text/encode: {e}", exc_info=True)
        return _err("Server xatosi.", 500)


@app.route("/api/text/decode", methods=["POST"])
def api_text_decode():
    try:
        data    = request.get_json(force=True)
        encoded = (data.get("encoded") or "").strip()

        if not encoded: return _err("Encoded text kiritilmadi.")

        secret = decode_text_zero_width(encoded)
        return jsonify({"ok": True, "secret": secret})

    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        logger.error(f"text/decode: {e}", exc_info=True)
        return _err("Server xatosi.", 500)


# ---------------------------------------------------------------------------
# IMAGE API
# ---------------------------------------------------------------------------

@app.route("/api/image/capacity", methods=["POST"])
def api_image_capacity():
    try:
        cover_file = request.files.get("cover")
        if not cover_file:
            return _err("Cover rasm yuklanmadi.")

        cap = image_capacity(cover_file.read())
        return jsonify({"ok": True, "capacity_bytes": cap})

    except Exception as e:
        logger.error(f"image/capacity: {e}", exc_info=True)
        return _err("Rasm sig'imini aniqlab bo'lmadi.", 400)


@app.route("/api/image/encode", methods=["POST"])
def api_image_encode():
    try:
        cover_file  = request.files.get("cover")
        secret_file = request.files.get("secret_file")

        if not cover_file:  return _err("Cover rasm yuklanmadi.")
        if not secret_file: return _err("Yashirin fayl yuklanmadi.")

        result_bytes = encode_file_in_image(
            cover_file.read(),
            secret_file.read(),
            secret_file.filename or "hidden_file"
        )
        return jsonify({"ok": True, "image_b64": base64.b64encode(result_bytes).decode()})

    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        logger.error(f"image/encode: {e}", exc_info=True)
        return _err("Kodlashda server xatosi.", 500)


@app.route("/api/image/decode", methods=["POST"])
def api_image_decode():
    try:
        encoded_file = request.files.get("encoded")
        if not encoded_file:
            return _err("Kodlangan rasm yuklanmadi.")

        file_bytes, filename = decode_file_from_image(encoded_file.read())
        mime, _ = mimetypes.guess_type(filename)

        return jsonify({
            "ok":       True,
            "file_b64": base64.b64encode(file_bytes).decode(),
            "filename": filename,
            "mime":     mime or "application/octet-stream",
            "size":     len(file_bytes),
        })

    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        logger.error(f"image/decode: {e}", exc_info=True)
        return _err("Dekodlashda xato. Fayl noto'g'ri bo'lishi mumkin.", 500)


# ---------------------------------------------------------------------------
# AUDIO API
# ---------------------------------------------------------------------------

@app.route("/api/audio/encode", methods=["POST"])
def api_audio_encode():
    try:
        cover_file  = request.files.get("cover")
        secret_file = request.files.get("secret_file")

        if not cover_file:  return _err("Cover audio yuklanmadi.")
        if not secret_file: return _err("Yashirin fayl yuklanmadi.")

        encoded_bytes = encode_audio_lsb(
            cover_file.read(),
            secret_file.read(),
            secret_file.filename or "hidden_file"
        )
        return jsonify({"ok": True, "audio_b64": base64.b64encode(encoded_bytes).decode()})

    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        traceback.print_exc()
        return _err(str(e), 500)


@app.route("/api/audio/decode", methods=["POST"])
def api_audio_decode():
    try:
        encoded_file = request.files.get("encoded")
        if not encoded_file:
            return _err("Kodlangan audio yuklanmadi.")

        secret_data, filename = decode_audio_lsb(encoded_file.read())
        mime, _ = mimetypes.guess_type(filename)

        return jsonify({
            "ok":       True,
            "file_b64": base64.b64encode(secret_data).decode(),
            "filename": filename,
            "mime":     mime or "application/octet-stream",
        })

    except Exception as e:
        traceback.print_exc()
        return _err("Stego ma'lumot topilmadi yoki fayl xato.", 500)


# ---------------------------------------------------------------------------
# VIDEO API
# ---------------------------------------------------------------------------

@app.route("/api/video/capacity", methods=["POST"])
def api_video_capacity():
    """
    Videoning maksimal yashirish sig'imini qaytaradi.
    main.js da cover video yuklanganda avtomatik chaqiriladi (image paneli kabi).

    Qabul qiladi : cover (video fayl)
    Qaytaradi    : { ok, capacity_bytes }
    """
    cover_file = request.files.get("cover")
    if not cover_file or not cover_file.filename:
        return _err("Cover video yuklanmadi.")

    if not _allowed_video(cover_file.filename):
        return _err("Qo'llab-quvvatlanmaydigan video format.")

    with tempfile.TemporaryDirectory() as tmpdir:
        ext        = Path(cover_file.filename).suffix.lower() or '.mp4'
        cover_path = os.path.join(tmpdir, f"cover{ext}")
        cover_file.save(cover_path)

        try:
            cap = get_video_capacity(cover_path)
            return jsonify({"ok": True, "capacity_bytes": cap})
        except Exception as e:
            logger.error(f"video/capacity: {e}", exc_info=True)
            return _err(f"Video sig'imini aniqlab bo'lmadi: {e}", 400)


@app.route("/api/video/encode", methods=["POST"])
def api_video_encode():
    """
    main.js kutayotgani:
      fetch('/api/video/encode', { method:'POST', body: fd })
      → response.blob()
      → a.download = 'stego_video.zip'

    Shuning uchun: ZIP blob qaytariladi, ichida stego_video.<asl_ext>
    """
    cover_file  = request.files.get("cover")
    secret_file = request.files.get("secret_file")

    if not cover_file  or not cover_file.filename:
        return _err("'cover' video fayli yuklanmadi.")
    if not secret_file or not secret_file.filename:
        return _err("'secret_file' yuklanmadi.")

    if not _allowed_video(cover_file.filename):
        return _err(
            f"Qo'llab-quvvatlanmaydigan video format. "
            f"Ruxsat etilganlar: {', '.join(sorted(ALLOWED_VIDEO_EXTS))}"
        )

    # encode_video natijasi va zip_buf with blokidan tashqarida saqlash uchun
    zip_buf  = None
    out_ext  = None

    with tempfile.TemporaryDirectory() as tmpdir:
        input_ext  = Path(cover_file.filename).suffix.lower()
        cover_path = os.path.join(tmpdir, f"cover{input_ext}")
        cover_file.save(cover_path)

        secret_data     = secret_file.read()
        secret_filename = secret_file.filename

        # Sig'im tekshiruvi
        try:
            capacity = get_video_capacity(cover_path)
        except Exception as e:
            return _err(f"Video o'qib bo'lmadi: {e}")

        needed = 8 + 256 + len(secret_data)
        if needed > capacity:
            return _err(
                f"Video sig'imi yetarli emas. "
                f"Kerak: {needed:,} B, mavjud: {capacity:,} B. "
                f"Kattaroq video yoki kichikroq fayl ishlating."
            )

        # Encode — natija xotiraga (bytes) qaytariladi, tmpdir ga bog'liq emas
        try:
            encoded_bytes, out_ext = encode_video(cover_path, secret_data, secret_filename)
        except (ValueError, RuntimeError) as e:
            return _err(str(e))
        except Exception as e:
            logger.error(f"video/encode: {e}", exc_info=True)
            return _err(f"Kutilmagan xato: {e}", 500)

        # ZIP ni xotiraga yig'amiz (tmpdir ichida emas, to'g'ridan BytesIO)
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"stego_video{out_ext}", encoded_bytes)
        zip_buf.seek(0)

    # ← with bloki tugadi, tmpdir o'chirildi
    # zip_buf xotirada — xavfsiz, send_file ishlaydi

    # send_file with blokidan TASHQARIDA — stream muammosi yo'q
    return send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="stego_video.zip",
    )

import mimetypes

def debug_secret(data, filename=None):
    print("Size:", len(data))

    # MIME aniqlash
    if filename:
        mime, _ = mimetypes.guess_type(filename)
        print("MIME:", mime)

    # Textga urinib ko‘rish
    try:
        text = data.decode("utf-8")
        print("\n--- TEXT ---")
        print(text[:500])
        return
    except:
        pass

    # Printable stringlarni ajratish
    import re
    strings = re.findall(rb'[ -~]{4,}', data)
    if strings:
        print("\n--- STRINGS ---")
        for s in strings[:10]:
            print(s.decode(errors="ignore"))

    else:
        print("\n❌ O‘qiladigan text topilmadi (binary fayl)")

@app.route("/api/video/decode", methods=["POST"])
def api_video_decode():
    """
    Qabul qiladi : encoded (ZIP yoki to'g'ridan video)
    Qaytaradi    : yashirin fayl (blob, Content-Disposition: attachment; filename=...)

    MUAMMO TUZATILDI:
      send_file(io.BytesIO(...)) ni `with TemporaryDirectory()` ichidan chaqirish
      Flask streamini `tmpdir` tozalanishidan oldin uzib qo'yadi →
      ERR_INVALID_HTTP_RESPONSE.
      Yechim: barcha ma'lumotlarni `with` ichida xotiraga yuklab,
      `send_file` ni `with` TASHQARISIDA chaqirish.
    """
    encoded_file = request.files.get("encoded")
    if not encoded_file or not encoded_file.filename:
        return _err("'encoded' fayli yuklanmadi.")

    # Natijalarni with blokidan tashqarida saqlash uchun
    secret_data     = None
    secret_filename = None
    mime            = None

    with tempfile.TemporaryDirectory() as tmpdir:
        safe_name   = Path(encoded_file.filename).name
        upload_path = os.path.join(tmpdir, safe_name)
        encoded_file.save(upload_path)

        video_path = upload_path
        upload_ext = Path(safe_name).suffix.lower()

        # ZIP bo'lsa, ichidan videoni chiqaramiz
        if upload_ext == ".zip":
            try:
                with zipfile.ZipFile(upload_path, "r") as zf:
                    video_name = next(
                        (n for n in zf.namelist()
                         if Path(n).suffix.lower() in ALLOWED_VIDEO_EXTS),
                        None
                    )
                    if not video_name:
                        return _err("ZIP ichida video fayl topilmadi.")
                    zf.extract(video_name, tmpdir)
                    video_path = os.path.join(tmpdir, video_name)
            except zipfile.BadZipFile:
                return _err("Noto'g'ri ZIP fayl.")

        elif not _allowed_video(safe_name):
            return _err(
                f"Qo'llab-quvvatlanmaydigan format. "
                f"ZIP yoki video fayl yuboring: {', '.join(sorted(ALLOWED_VIDEO_EXTS))}"
            )

        # Decode — natija xotiraga yuklanadi (tmpdir hali mavjud)
        try:
            secret_data, secret_filename = decode_video(video_path)
        except ValueError as e:
            return _err(str(e))
        except Exception as e:
            logger.error(f"video/decode: {e}", exc_info=True)
            return _err(f"Dekodlashda xato: {e}", 500)

    # ← with bloki tugadi, tmpdir o'chirildi
    # secret_data xotirada — xavfsiz

    if not secret_filename:
        secret_filename = "recovered_file.bin"

    mime, _ = mimetypes.guess_type(secret_filename)
    mime = mime or "application/octet-stream"

    debug_secret(secret_data, secret_filename)
    print(secret_data[:20])
    # send_file with blokidan TASHQARIDA — stream muammosi yo'q
    return send_file(
        io.BytesIO(secret_data),
        mimetype=mime,
        as_attachment=True,
        download_name=secret_filename,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)