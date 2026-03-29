"""
Steganography Logic — Manual Implementation
-------------------------------------------
1. Text Steganography: Zero-width character encoding
   - Maps each bit of the secret message to invisible Unicode
     zero-width characters hidden inside a cover text.
   - Zero-width non-joiner (U+200C) = bit 0
   - Zero-width joiner      (U+200D) = bit 1
   The hidden sequence is sandwiched between two zero-width space
   delimiters (U+200B) so the decoder can locate it reliably even
   when the carrier text is copied partially.

2. Image Steganography: 2-bit LSB (file-in-image)
   - Any binary file can be hidden inside a cover PNG/JPG image.
   - Header format embedded before the file data:
       [1 byte]  filename length  (max 255)
       [N bytes] filename (UTF-8)
       [4 bytes] file data length (big-endian uint32)
   - 2 LSBs of each RGB channel carry the payload bits.
   - Capacity: W × H × 3 channels × 2 bits  per pixel.
   - A ValueError is raised if the file exceeds capacity.
   - Output is always a lossless PNG.
"""

from PIL import Image
import io
import struct

# ---------------------------------------------------------------------------
# Zero-width character constants
# ---------------------------------------------------------------------------
ZW_ZERO  = "\u200c"   # Zero-width non-joiner  → bit 0
ZW_ONE   = "\u200d"   # Zero-width joiner       → bit 1
ZW_START = "\u200b"   # Zero-width space        → delimiter (start / end)
ZW_SEP   = "\u2060"   # Word joiner             → byte separator (readability)


# ---------------------------------------------------------------------------
# Text steganography helpers
# ---------------------------------------------------------------------------

def _text_to_bits(text: str) -> str:
    """Convert a UTF-8 string to a binary string (one char per bit)."""
    encoded = text.encode("utf-8")
    return "".join(f"{byte:08b}" for byte in encoded)


def _bits_to_text(bits: str) -> str:
    """Convert a binary string back to a UTF-8 string."""
    chars = []
    for i in range(0, len(bits), 8):
        byte = bits[i:i + 8]
        if len(byte) < 8:
            break
        chars.append(chr(int(byte, 2)))
    return "".join(chars)


def encode_text_zero_width(cover: str, secret: str) -> str:
    """
    Embed *secret* invisibly into *cover* text using zero-width characters.

    The zero-width payload is inserted right after the first character of
    the cover text so it cannot accidentally be stripped from the start/end.
    """
    if not cover:
        raise ValueError("Cover text must not be empty.")
    if not secret:
        raise ValueError("Secret text must not be empty.")

    bits = _text_to_bits(secret)

    # Build the invisible payload
    payload_chars = [ZW_START]
    for i, bit in enumerate(bits):
        payload_chars.append(ZW_ONE if bit == "1" else ZW_ZERO)
        # Insert a visual separator every 8 bits (not visible; aids debugging)
        if (i + 1) % 8 == 0:
            payload_chars.append(ZW_SEP)
    payload_chars.append(ZW_START)

    payload = "".join(payload_chars)

    # Insert the payload after the first character
    return cover[0] + payload + cover[1:]


def decode_text_zero_width(encoded: str) -> str:
    """
    Extract the hidden message from a zero-width encoded string.
    Returns the decoded secret or raises ValueError if none is found.
    """
    # Extract content between the two ZW_START delimiters
    start = encoded.find(ZW_START)
    if start == -1:
        raise ValueError("No hidden message found in this text.")
    end = encoded.find(ZW_START, start + 1)
    if end == -1:
        raise ValueError("Malformed hidden message: missing end delimiter.")

    payload = encoded[start + 1:end]

    # Strip byte-separator characters and collect bits
    bits = []
    for ch in payload:
        if ch == ZW_ZERO:
            bits.append("0")
        elif ch == ZW_ONE:
            bits.append("1")
        elif ch == ZW_SEP:
            continue  # separator — ignore
        else:
            raise ValueError(f"Unexpected character in payload: U+{ord(ch):04X}")

    if not bits:
        raise ValueError("Payload is empty — no hidden message found.")

    # Trim to a multiple of 8 (safety)
    trimmed = "".join(bits[: (len(bits) // 8) * 8])
    try:
        return _bits_to_text(trimmed)
    except Exception as exc:
        raise ValueError(f"Failed to decode payload: {exc}") from exc


# ---------------------------------------------------------------------------
# Image steganography helpers (2-bit LSB — file-in-image)
# ---------------------------------------------------------------------------

# Internal helpers
# ─────────────────

def _to_bits(data: bytes) -> list[int]:
    """Convert bytes to a flat list of bits (MSB first)."""
    bits = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def _bits_to_bytes(bits: list[int]) -> bytes:
    """Convert a flat list of bits (MSB first) back to bytes."""
    result = bytearray()
    for i in range(0, len(bits) - 7, 8):
        val = 0
        for b in bits[i:i + 8]:
            val = (val << 1) | b
        result.append(val)
    return bytes(result)


def image_capacity(cover_bytes: bytes) -> int:
    """
    Return the maximum number of bytes that can be hidden in the cover image
    using 2-bit LSB encoding (2 bits per channel × 3 channels per pixel).
    """
    img = Image.open(io.BytesIO(cover_bytes))
    w, h = img.size
    return (w * h * 3 * 2) // 8


# Public API
# ─────────────

def encode_file_in_image(cover_bytes: bytes, file_bytes: bytes, filename: str) -> bytes:
    """
    Embed any binary file into a cover image using 2-bit LSB steganography.

    Payload layout
    ──────────────
    [1 byte]  filename length (max 255)
    [N bytes] filename (UTF-8)
    [4 bytes] file data length (big-endian uint32)
    [M bytes] file data

    Two LSBs of each R, G, B channel carry the payload bit-stream.

    Raises ValueError if the file is too large for the cover image.
    """
    cover = Image.open(io.BytesIO(cover_bytes)).convert("RGB")
    width, height = cover.size

    # ── Capacity check ──────────────────────────────────────────────────
    max_bytes = (width * height * 3 * 2) // 8   # 2 bits per channel

    fname_encoded = filename.encode("utf-8")[:255]
    # Header: 1 (fname len) + N (fname) + 4 (data len)
    header = bytes([len(fname_encoded)]) + fname_encoded + struct.pack(">I", len(file_bytes))
    payload = header + file_bytes

    if len(payload) > max_bytes:
        usable = max_bytes - len(header)
        raise ValueError(
            f"File is too large to hide in this image. "
            f"Maximum file size for this cover image: {usable:,} bytes "
            f"({usable / 1024:.1f} KB). "
            f"Your file is {len(file_bytes):,} bytes "
            f"({len(file_bytes) / 1024:.1f} KB). "
            f"Please use a larger cover image or a smaller file."
        )

    # ── Embed ────────────────────────────────────────────────────────────
    bits = _to_bits(payload)

    # Flatten pixel channels to a mutable list
    flat = []
    for r, g, b in cover.getdata():
        flat.extend([r, g, b])

    # Write 2 bits into the 2 LSBs of each channel value
    for i in range(0, len(bits) - 1, 2):
        channel_idx = i // 2
        two_bits = (bits[i] << 1) | bits[i + 1]
        flat[channel_idx] = (flat[channel_idx] & 0xFC) | two_bits

    # Handle an odd trailing bit (rare)
    if len(bits) % 2 == 1:
        channel_idx = len(bits) // 2
        flat[channel_idx] = (flat[channel_idx] & 0xFE) | bits[-1]

    # Rebuild image
    new_pixels = [(flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat), 3)]
    result_img = Image.new("RGB", (width, height))
    result_img.putdata(new_pixels)

    buf = io.BytesIO()
    result_img.save(buf, format="PNG")
    return buf.getvalue()


def decode_file_from_image(encoded_bytes: bytes) -> tuple:
    """
    Extract the hidden file from a 2-bit LSB encoded PNG.

    Returns
    ───────
    (file_bytes: bytes, filename: str)

    Raises ValueError if the image does not contain a valid StegoVault payload.
    """
    encoded = Image.open(io.BytesIO(encoded_bytes)).convert("RGB")
    width, height = encoded.size

    # Flatten channels
    flat = []
    for r, g, b in encoded.getdata():
        flat.extend([r, g, b])

    # Extract 2 LSBs from every channel
    bits = []
    for val in flat:
        bits.append((val >> 1) & 1)
        bits.append(val & 1)

    def read_bytes(offset_bits: int, n: int) -> tuple:
        """Read n bytes from bits starting at offset_bits. Returns (data, new_offset)."""
        chunk = bits[offset_bits: offset_bits + n * 8]
        if len(chunk) < n * 8:
            raise ValueError("Encoded image appears corrupted or was not created by StegoVault.")
        return _bits_to_bytes(chunk), offset_bits + n * 8

    offset = 0

    # Read filename length (1 byte)
    fname_len_bytes, offset = read_bytes(offset, 1)
    fname_len = fname_len_bytes[0]

    if fname_len == 0 or fname_len > 255:
        raise ValueError("Encoded image appears corrupted or was not created by StegoVault.")

    # Read filename
    fname_data, offset = read_bytes(offset, fname_len)
    try:
        filename = fname_data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Corrupted filename in encoded image.") from exc

    # Read file data length (4 bytes, big-endian)
    size_data, offset = read_bytes(offset, 4)
    file_size = struct.unpack(">I", size_data)[0]

    # Sanity check: the declared size must fit within remaining bits
    remaining_bytes = (len(bits) - offset) // 8
    if file_size > remaining_bytes:
        raise ValueError(
            f"Corrupted payload: declared size ({file_size:,} bytes) exceeds "
            f"remaining image capacity ({remaining_bytes:,} bytes)."
        )

    # Read actual file data
    file_data, _ = read_bytes(offset, file_size)
    return file_data, filename
