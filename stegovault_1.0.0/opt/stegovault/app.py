"""
Flask Application — StegoVault
"""
import base64
import mimetypes
from flask import Flask, render_template, request, jsonify

from logic import (
    encode_text_zero_width,
    decode_text_zero_width,
    encode_file_in_image,
    decode_file_from_image,
    image_capacity,
)

from flask import Flask, render_template, request, jsonify, abort
import logging

# ---------------------------------------------------------------------------
# Setup & Config
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB max upload

# Configure basic logging to see server errors in console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Global Error Handlers (JSON-friendly)
# ---------------------------------------------------------------------------

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
        data   = request.get_json(force=True)
        cover  = (data.get("cover")  or "").strip()
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
        data    = request.get_json(force=True)
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
        cover_file  = request.files.get("cover")
        secret_file = request.files.get("secret_file")

        if not cover_file:
            return jsonify({"ok": False, "error": "Cover image is required."}), 400
        if not secret_file:
            return jsonify({"ok": False, "error": "Secret file is required."}), 400

        filename = secret_file.filename or "hidden_file"
        cover_bytes  = cover_file.read()
        file_bytes   = secret_file.read()

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
            "ok":       True,
            "file_b64": b64,
            "filename": filename,
            "mime":     mime,
            "size":     len(file_bytes),
        })
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"Image decode error: {exc}", exc_info=True)
        return jsonify({"ok": False, "error": "Decoding failed. The file may be corrupted or not a valid StegoVault image."}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 9001))
    app.run(debug=False, host="0.0.0.0", port=port)
