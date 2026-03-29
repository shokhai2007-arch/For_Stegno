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

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB max upload


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
    data   = request.get_json(force=True)
    cover  = (data.get("cover")  or "").strip()
    secret = (data.get("secret") or "").strip()

    if not cover:
        return jsonify({"ok": False, "error": "Cover text is required."}), 400
    if not secret:
        return jsonify({"ok": False, "error": "Secret text is required."}), 400

    try:
        result = encode_text_zero_width(cover, secret)
        return jsonify({"ok": True, "result": result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/text/decode", methods=["POST"])
def api_text_decode():
    data    = request.get_json(force=True)
    encoded = (data.get("encoded") or "").strip()

    if not encoded:
        return jsonify({"ok": False, "error": "Encoded text is required."}), 400

    try:
        secret = decode_text_zero_width(encoded)
        return jsonify({"ok": True, "secret": secret})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


# ---------------------------------------------------------------------------
# Image Steganography API  (file-in-image)
# ---------------------------------------------------------------------------

@app.route("/api/image/capacity", methods=["POST"])
def api_image_capacity():
    """Return max bytes that can be hidden in the uploaded cover image."""
    cover_file = request.files.get("cover")
    if not cover_file:
        return jsonify({"ok": False, "error": "Cover image required."}), 400
    try:
        cap = image_capacity(cover_file.read())
        return jsonify({"ok": True, "capacity_bytes": cap})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/image/encode", methods=["POST"])
def api_image_encode():
    cover_file  = request.files.get("cover")
    secret_file = request.files.get("secret_file")

    if not cover_file:
        return jsonify({"ok": False, "error": "Cover image is required."}), 400
    if not secret_file:
        return jsonify({"ok": False, "error": "Secret file is required."}), 400

    filename = secret_file.filename or "hidden_file"

    try:
        cover_bytes  = cover_file.read()
        file_bytes   = secret_file.read()
        result_bytes = encode_file_in_image(cover_bytes, file_bytes, filename)
        b64 = base64.b64encode(result_bytes).decode()
        return jsonify({"ok": True, "image_b64": b64})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Unexpected error: {exc}"}), 500


@app.route("/api/image/decode", methods=["POST"])
def api_image_decode():
    encoded_file = request.files.get("encoded")

    if not encoded_file:
        return jsonify({"ok": False, "error": "Encoded image is required."}), 400

    try:
        file_bytes, filename = decode_file_from_image(encoded_file.read())

        # Guess MIME type from the recovered filename
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
        return jsonify({"ok": False, "error": f"Unexpected error: {exc}"}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
