"""
Round-trip tests for the StegoVault steganography logic.
Run with: python test_logic.py
"""
import sys
import io
from PIL import Image
from logic import (
    encode_text_zero_width,
    decode_text_zero_width,
    encode_file_in_image,
    decode_file_from_image,
    image_capacity,
)

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"
PASS  = f"{GREEN}✓ PASS{RESET}"
FAIL  = f"{RED}✗ FAIL{RESET}"
errors = 0


def run(name, fn):
    global errors
    try:
        fn()
        print(f"{PASS}  {name}")
    except Exception as e:
        print(f"{FAIL}  {name}: {e}")
        errors += 1


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_image_bytes(color=(200, 200, 200), size=(64, 64)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Text Steganography ────────────────────────────────────────────────────────

def test_text_basic_roundtrip():
    cover  = "The weather is nice today."
    secret = "Meet me at midnight."
    encoded = encode_text_zero_width(cover, secret)
    assert encoded != cover, "Encoded text should differ from cover"
    decoded = decode_text_zero_width(encoded)
    assert decoded == secret, f"Expected '{secret}', got '{decoded}'"


def test_text_unicode_secret():
    cover  = "Random visible text here."
    secret = "Привет мир! こんにちは 🔒"
    encoded = encode_text_zero_width(cover, secret)
    decoded = decode_text_zero_width(encoded)
    assert decoded == secret, f"Unicode roundtrip failed: {decoded!r}"


def test_text_cover_preserved():
    cover  = "Hello World"
    secret = "42"
    encoded = encode_text_zero_width(cover, secret)
    zw_chars = {"\u200b", "\u200c", "\u200d", "\u2060"}
    visible = "".join(c for c in encoded if c not in zw_chars)
    assert visible == cover, f"Visible cover changed: got '{visible}'"


def test_text_empty_cover_raises():
    try:
        encode_text_zero_width("", "secret")
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass


def test_text_no_hidden_message():
    try:
        decode_text_zero_width("Just a normal string with no hidden data.")
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass


# ── Image / File-in-Image Steganography ──────────────────────────────────────

def test_capacity_function():
    img_bytes = _make_image_bytes(size=(100, 100))
    cap = image_capacity(img_bytes)
    # 100 x 100 x 3 channels x 2 bits / 8 = 7500 bytes
    assert cap == 7500, f"Expected 7500, got {cap}"


def test_file_text_roundtrip():
    cover_bytes = _make_image_bytes(size=(200, 200))
    secret_data = b"Hello, this is a secret text file!\nLine 2 here."
    filename    = "secret.txt"

    encoded = encode_file_in_image(cover_bytes, secret_data, filename)
    file_out, name_out = decode_file_from_image(encoded)

    assert name_out == filename,    f"Filename mismatch: {name_out!r}"
    assert file_out == secret_data, f"Data mismatch:\n{file_out!r}\nvs\n{secret_data!r}"


def test_file_binary_roundtrip():
    cover_bytes = _make_image_bytes(size=(300, 300))
    # Simulate binary file (e.g. small PNG header bytes)
    secret_data = bytes(range(256)) * 4   # 1024 random-ish bytes
    filename    = "data.bin"

    encoded = encode_file_in_image(cover_bytes, secret_data, filename)
    file_out, name_out = decode_file_from_image(encoded)

    assert name_out == filename,    f"Filename mismatch: {name_out!r}"
    assert file_out == secret_data, "Binary data roundtrip failed"


def test_file_unicode_filename():
    cover_bytes = _make_image_bytes(size=(200, 200))
    secret_data = b"test content"
    filename    = "secret_файл.txt"

    encoded = encode_file_in_image(cover_bytes, secret_data, filename)
    file_out, name_out = decode_file_from_image(encoded)
    assert name_out == filename, f"Unicode filename mismatch: {name_out!r}"
    assert file_out == secret_data


def test_file_too_large_raises():
    # 10x10 image → capacity = 10 * 10 * 3 * 2 / 8 = 75 bytes
    cover_bytes = _make_image_bytes(size=(10, 10))
    huge_data   = b"x" * 1000   # definitely too large
    try:
        encode_file_in_image(cover_bytes, huge_data, "big.bin")
        raise AssertionError("Should have raised ValueError for oversized file")
    except ValueError as e:
        assert "too large" in str(e).lower(), f"Wrong error message: {e}"


def test_encoded_output_is_png():
    cover_bytes = _make_image_bytes(size=(200, 200))
    encoded     = encode_file_in_image(cover_bytes, b"test", "t.txt")
    assert encoded[:8] == b'\x89PNG\r\n\x1a\n', "Output should be a valid PNG"


def test_cover_barely_altered():
    """
    2-bit LSB: the cover channel value can change by at most 3.
    Verify that pixel values are close to the original.
    """
    cover_bytes = _make_image_bytes(color=(128, 64, 200), size=(100, 100))
    encoded     = encode_file_in_image(cover_bytes, b"tiny", "t.txt")

    orig = Image.open(io.BytesIO(cover_bytes)).convert("RGB")
    enc  = Image.open(io.BytesIO(encoded)).convert("RGB")

    for (or_, og, ob), (er, eg, eb) in zip(orig.getdata(), enc.getdata()):
        assert abs(or_ - er) <= 3, f"R channel changed too much: {or_} → {er}"
        assert abs(og - eg) <= 3, f"G channel changed too much: {og} → {eg}"
        assert abs(ob - eb) <= 3, f"B channel changed too much: {ob} → {eb}"


def test_invalid_image_raises():
    bad_bytes = b"This is not an image at all."
    try:
        decode_file_from_image(bad_bytes)
        raise AssertionError("Should have raised on invalid image")
    except Exception:
        pass   # Any exception is acceptable — cannot decode a non-image


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== StegoVault Logic Tests ===\n")

    print("Text Steganography")
    print("──────────────────")
    run("Basic text roundtrip",          test_text_basic_roundtrip)
    run("Unicode secret roundtrip",      test_text_unicode_secret)
    run("Cover text preserved",          test_text_cover_preserved)
    run("Empty cover raises ValueError", test_text_empty_cover_raises)
    run("No hidden message raises",      test_text_no_hidden_message)

    print("\nFile-in-Image Steganography (2-bit LSB)")
    print("────────────────────────────────────────")
    run("Capacity calculation",          test_capacity_function)
    run("Text file roundtrip",           test_file_text_roundtrip)
    run("Binary file roundtrip",         test_file_binary_roundtrip)
    run("Unicode filename roundtrip",    test_file_unicode_filename)
    run("Oversized file raises",         test_file_too_large_raises)
    run("Output is valid PNG",           test_encoded_output_is_png)
    run("Cover pixels barely altered",   test_cover_barely_altered)
    run("Invalid image raises error",    test_invalid_image_raises)

    total    = 13
    passed   = total - errors
    verdict  = f"{GREEN}All {total} tests passed!{RESET}" if errors == 0 \
               else f"{RED}{errors} test(s) failed.{RESET}"
    print(f"\n{verdict}\n")
    sys.exit(0 if errors == 0 else 1)
