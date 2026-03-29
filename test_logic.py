"""
Round-trip tests for the manual steganography logic.
Run with: python test_logic.py
"""
import sys
import io
from PIL import Image
from logic import (
    encode_text_zero_width,
    decode_text_zero_width,
    encode_image_lsb,
    decode_image_lsb,
)

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
errors = 0


def run(name, fn):
    global errors
    try:
        fn()
        print(f"{PASS}  {name}")
    except Exception as e:
        print(f"{FAIL}  {name}: {e}")
        errors += 1


# ── Text steganography tests ──────────────────────────────────────────────

def test_text_basic_roundtrip():
    cover  = "The weather is nice today."
    secret = "Meet me at midnight."
    encoded = encode_text_zero_width(cover, secret)
    assert encoded != cover, "Encoded should differ from cover"
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
    # Strip zero-width characters and compare visible text
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


# ── Image steganography tests ──────────────────────────────────────────────

def _make_image_bytes(color=(100, 150, 200), size=(64, 64)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_image_encode_decode_roundtrip():
    cover_bytes  = _make_image_bytes(color=(200, 200, 200))
    secret_bytes = _make_image_bytes(color=(255, 0, 0))

    encoded = encode_image_lsb(cover_bytes, secret_bytes)
    revealed = decode_image_lsb(encoded)

    # The revealed image should be reddish (upper nibble of 255 = 0xF0 → 0xF0 = 240)
    img = Image.open(io.BytesIO(revealed)).convert("RGB")
    px  = img.getpixel((10, 10))
    # Red channel of secret was 255 → after 4-bit encoding, decoded red ≈ 240
    assert px[0] >= 224, f"Red channel should be high, got {px[0]}"
    assert px[1] <= 32,  f"Green channel should be low, got {px[1]}"
    assert px[2] <= 32,  f"Blue channel should be low, got {px[2]}"


def test_image_output_is_png():
    cover_bytes  = _make_image_bytes()
    secret_bytes = _make_image_bytes()
    encoded = encode_image_lsb(cover_bytes, secret_bytes)
    assert encoded[:8] == b'\x89PNG\r\n\x1a\n', "Output should be PNG"


def test_image_cover_visually_unchanged():
    """Ensure cover pixel's top nibble is preserved."""
    cover_bytes  = _make_image_bytes(color=(160, 80, 240))
    secret_bytes = _make_image_bytes(color=(0, 0, 0))

    encoded = encode_image_lsb(cover_bytes, secret_bytes)
    img = Image.open(io.BytesIO(encoded)).convert("RGB")
    px = img.getpixel((10, 10))

    # Top 4 bits of 160 = 0xA0 = 160; secret is 0 so lower nibble = 0
    assert px[0] == 160, f"Red channel top nibble changed: {px[0]}"
    assert px[1] == 80,  f"Green channel top nibble changed: {px[1]}"
    # 0xF0 = 240 → stays 240, but actual is 240 not 0xF0 ... Pillow stores 0–255 integers.
    # 240 & 0xF0 = 240; secret=0 → (240 & 0xF0) | 0 = 240
    assert px[2] == 240, f"Blue channel top nibble changed: {px[2]}"


# ── Run all ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== StegoVault Logic Tests ===\n")

    run("Text: basic roundtrip",          test_text_basic_roundtrip)
    run("Text: unicode secret roundtrip", test_text_unicode_secret)
    run("Text: cover text preserved",     test_text_cover_preserved)
    run("Text: empty cover raises",       test_text_empty_cover_raises)
    run("Text: no hidden msg raises",     test_text_no_hidden_message)
    run("Image: encode/decode roundtrip", test_image_encode_decode_roundtrip)
    run("Image: output is PNG",           test_image_output_is_png)
    run("Image: cover visually preserved",test_image_cover_visually_unchanged)

    print(f"\n{'All tests passed!' if errors == 0 else f'{errors} test(s) failed.'}\n")
    sys.exit(0 if errors == 0 else 1)
