"""
Flask Application — StegoVault
"""
import base64
import mimetypes
import traceback
import tempfile
import os
from logic import (
    encode_text_zero_width,
    decode_text_zero_width,
    encode_file_in_image,
    decode_file_from_image,
    image_capacity,
    encode_audio_lsb,
    decode_audio_lsb,
    encode_video_lsb_optimized,
    decode_video_lsb_optimized
)

from flask import Flask, render_template, request, jsonify, send_file
import logging

# ---------------------------------------------------------------------------
# Setup & Config
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB max upload


# Configure basic logging to see server errors in console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Global Error Handlers (JSON-friendly)
# ---------------------------------------------------------------------------

def save_upload_to_temp(file_storage, suffix):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    file_storage.save(temp.name)  # to‘g‘ridan-to‘g‘ri diskka yozadi
    temp.close()
    return temp.name

@app.errorhandler(413)
def error_413(e):
    """Handle files exceeding MAX_CONTENT_LENGTH."""
    return jsonify({
        "ok": False,
        "error": "File is too large. Maximum allowed size is 32MB."
    }), 413


@app.errorhandler(404)
def error_404(e):
    """Handle invalid API paths."""
    if request.path.startswith('/api/'):
        return jsonify({"ok": False, "error": "API endpoint not found."}), 404
    return render_template("index.html"), 404


@app.errorhandler(500)
def error_500(e):
    """Handle unexpected server-side crashes."""
    logger.error(f"Unhandled Exception: {e}", exc_info=True)
    return jsonify({
        "ok": False,
        "error": "A critical server error occurred. Please try again later."
    }), 500


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Text Steganography API
# ---------------------------------------------------------------------------

@app.route("/api/text/encode", methods=["POST"])
def api_text_encode():
    try:
        data = request.get_json(force=True)
        cover = (data.get("cover") or "").strip()
        secret = (data.get("secret") or "").strip()

        if not cover:
            return jsonify({"ok": False, "error": "Cover text is required."}), 400
        if not secret:
            return jsonify({"ok": False, "error": "Secret text is required."}), 400

        result = encode_text_zero_width(cover, secret)
        return jsonify({"ok": True, "result": result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"Text encode error: {exc}", exc_info=True)
        return jsonify({"ok": False, "error": "Failed to encode text due to a server error."}), 500


@app.route("/api/text/decode", methods=["POST"])
def api_text_decode():
    try:
        data = request.get_json(force=True)
        encoded = (data.get("encoded") or "").strip()

        if not encoded:
            return jsonify({"ok": False, "error": "Encoded text is required."}), 400

        secret = decode_text_zero_width(encoded)
        return jsonify({"ok": True, "secret": secret})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"Text decode error: {exc}", exc_info=True)
        return jsonify({"ok": False, "error": "Failed to decode text due to a server error."}), 500


# ---------------------------------------------------------------------------
# Image Steganography API  (file-in-image)
# ---------------------------------------------------------------------------

@app.route("/api/image/capacity", methods=["POST"])
def api_image_capacity():
    """Return max bytes that can be hidden in the uploaded cover image."""
    try:
        cover_file = request.files.get("cover")
        if not cover_file:
            return jsonify({"ok": False, "error": "Cover image required."}), 400

        cap = image_capacity(cover_file.read())
        return jsonify({"ok": True, "capacity_bytes": cap})
    except Exception as exc:
        logger.error(f"Capacity check error: {exc}", exc_info=True)
        return jsonify({"ok": False, "error": "Could not read image capacity. Ensure it is a valid PNG/JPG."}), 400


@app.route("/api/image/encode", methods=["POST"])
def api_image_encode():
    try:
        cover_file = request.files.get("cover")
        secret_file = request.files.get("secret_file")

        if not cover_file:
            return jsonify({"ok": False, "error": "Cover image is required."}), 400
        if not secret_file:
            return jsonify({"ok": False, "error": "Secret file is required."}), 400

        filename = secret_file.filename or "hidden_file"
        cover_bytes = cover_file.read()
        file_bytes = secret_file.read()

        result_bytes = encode_file_in_image(cover_bytes, file_bytes, filename)
        b64 = base64.b64encode(result_bytes).decode()
        return jsonify({"ok": True, "image_b64": b64})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"Image encode error: {exc}", exc_info=True)
        return jsonify({"ok": False, "error": "An unexpected server error occurred during encoding."}), 500


@app.route("/api/image/decode", methods=["POST"])
def api_image_decode():
    try:
        encoded_file = request.files.get("encoded")

        if not encoded_file:
            return jsonify({"ok": False, "error": "Encoded image is required."}), 400

        file_bytes, filename = decode_file_from_image(encoded_file.read())

        # Guess MIME type
        mime, _ = mimetypes.guess_type(filename)
        if not mime:
            mime = "application/octet-stream"

        b64 = base64.b64encode(file_bytes).decode()
        return jsonify({
            "ok": True,
            "file_b64": b64,
            "filename": filename,
            "mime": mime,
            "size": len(file_bytes),
        })
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"Image decode error: {exc}", exc_info=True)
        return jsonify(
            {"ok": False, "error": "Decoding failed. The file may be corrupted or not a valid StegoVault image."}), 500


@app.route('/api/audio/encode', methods=['POST'])
def api_audio_encode():
    try:
        if 'cover' not in request.files or 'secret_file' not in request.files:
            return jsonify({"ok": False, "error": "Fayllar yuklanmadi."}), 400

        cover_file = request.files['cover']
        secret_file = request.files['secret_file']

        cover_file.seek(0)
        cover_bytes = cover_file.read()
        secret_bytes = secret_file.read()

        # secret_file.filename orqali asl nomni yuboramiz
        encoded_audio_bytes = encode_audio_lsb(
            cover_bytes,
            secret_bytes,
            secret_file.filename
        )

        encoded_b64 = base64.b64encode(encoded_audio_bytes).decode('utf-8')

        return jsonify({
            "ok": True,
            "audio_b64": encoded_b64
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/audio/decode', methods=['POST'])
def api_audio_decode():
    try:
        if 'encoded' not in request.files:
            return jsonify({"ok": False, "error": "Fayl topilmadi."}), 400

        encoded_file = request.files['encoded']
        encoded_bytes = encoded_file.read()

        # Dekodlash: endi funksiya ikki qiymat qaytaradi
        secret_data, filename = decode_audio_lsb(encoded_bytes)

        # MIME turini fayl nomiga qarab aniqlash
        mime_type, _ = mimetypes.guess_type(filename)
        file_b64 = base64.b64encode(secret_data).decode('utf-8')

        return jsonify({
            "ok": True,
            "file_b64": file_b64,
            "filename": filename,
            "mime": mime_type or "application/octet-stream"
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": "Stego ma'lumot topilmadi yoki fayl xato."}), 500


# ============================================================================
# FLASK ENDPOINTS (Optimized)
# ============================================================================

@app.route('/api/video/encode', methods=['POST'])
def api_video_encode():
    try:
        cover_video = request.files['cover']
        secret_file = request.files['secret_file']

        # Vaqtinchalik fayllar
        temp_input = tempfile.NamedTemporaryFile(suffix='.avi', delete=False).name
        cover_video.save(temp_input)

        secret_bytes = secret_file.read()

        # Kodlash opsiyalari (frontend dan olish mumkin)
        frame_step = int(request.form.get('frame_step', 5))  # har 5-kadr
        resize = request.form.get('resize', '640x480')  # kichraytirish

        if resize and 'x' in resize:
            w, h = map(int, resize.split('x'))
            resize_to = (w, h)
        else:
            resize_to = None

        output_path = tempfile.NamedTemporaryFile(suffix='.avi', delete=False).name

        encode_video_lsb_optimized(
            temp_input,
            secret_bytes,
            output_path,
            frame_step=frame_step,
            resize_to=resize_to
        )

        # Tozalash
        os.unlink(temp_input)

        # Faylni jo'natish
        return send_file(
            output_path,
            as_attachment=True,
            download_name='stego_video.avi',
            mimetype='video/x-msvideo'
        )

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/video/decode', methods=['POST'])
def api_video_decode():
    try:
        encoded_video = request.files['encoded']
        frame_step = int(request.form.get('frame_step', 5))

        temp_input = tempfile.NamedTemporaryFile(suffix='.avi', delete=False).name
        encoded_video.save(temp_input)

        secret_data = decode_video_lsb_optimized(temp_input, frame_step=frame_step)

        os.unlink(temp_input)

        return send_file(
            io.BytesIO(secret_data),
            as_attachment=True,
            download_name='recovered_file.bin',
            mimetype='application/octet-stream'
        )

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# @app.route('/api/video/encode', methods=['POST'])
# def api_video_encode():
#     try:
#         cover_video = request.files['cover']
#         secret_file = request.files['secret_file']
#
#         # cover_video.filename o'rniga .avi kengaytmasini ishlatamiz
#         encoded_video_bytes = encode_video_lsb(
#             cover_video.read(),
#             secret_file.read(),
#             "stego.avi"
#         )
#
#         video_b64 = base64.b64encode(encoded_video_bytes).decode('utf-8')
#
#         return jsonify({
#             "ok": True,
#             "video_b64": video_b64,
#             "filename": "stego_video.avi" # Frontend yuklab olayotganda shu nom bilan saqlasin
#         })
#     except Exception as e:
#         return jsonify({"ok": False, "error": str(e)}), 500
#
#
#
# @app.route('/api/video/decode', methods=['POST'])
# def api_video_decode():
#     try:
#         if 'encoded' not in request.files:
#             return jsonify({"ok": False, "error": "Fayl yuklanmadi"}), 400
#
#         encoded_video = request.files['encoded']
#         # ASOSIY: original fayl nomini uzatish shart
#         secret_data = decode_video_lsb(encoded_video.read(), filename=encoded_video.filename)
#
#         # Base64 va javob qaytarish...
#         file_b64 = base64.b64encode(secret_data).decode('utf-8')
#         return jsonify({
#             "ok": True,
#             "file_b64": file_b64,
#             "filename": "recovered_file.bin",
#             "mime": "application/octet-stream"
#         })
#     except Exception as e:
#         import traceback
#         traceback.print_exc() # Terminalda xatoni ko'rish uchun
#         return jsonify({"ok": False, "error": str(e)}), 500
#

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
