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

3. Audio Steganography: 1-bit LSB on WAV PCM samples
   - Embeds data into the least significant bit of each audio sample.
   - Supports 8-bit and 16-bit PCM WAV files.
   - Header: [4 bytes] payload length (big-endian uint32)
   - Output preserves the original WAV format parameters.

4. Video Steganography: 1-bit LSB on video frame pixels
   - Uses OpenCV to read/write video frames.
   - Embeds data into the LSB of each pixel channel across frames.
   - Header: [4 bytes] payload length (big-endian uint32)
   - Output preserves the original codec/format.
"""

from PIL import Image
from pydub import AudioSegment
import io
import struct
import wave
import tempfile
import os
import cv2
import numpy as np


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
    raw = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = bits[i:i + 8]
        if len(byte) < 8:
            break
        raw.append(int(byte, 2))
    return raw.decode("utf-8")


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
    try:
        img = Image.open(io.BytesIO(cover_bytes))
        w, h = img.size
        return (w * h * 3 * 2) // 8
    except Exception as e:
        raise ValueError(f"Could not read cover image: {e}")


# Public API
# ─────────────

def encode_file_in_image(cover_bytes: bytes, file_bytes: bytes, filename: str) -> bytes:
    """
    Embed any binary file into a cover image using 2-bit LSB steganography.
    """
    try:
        cover = Image.open(io.BytesIO(cover_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Invalid cover image format: {e}")

    width, height = cover.size
    # ── Capacity check ──────────────────────────────────────────────────
    max_bytes = (width * height * 3 * 2) // 8

    fname_encoded = filename.encode("utf-8")[:255]
    header = bytes([len(fname_encoded)]) + fname_encoded + struct.pack(">I", len(file_bytes))
    payload = header + file_bytes

    if len(payload) > max_bytes:
        usable = max_bytes - len(header)
        raise ValueError(
            f"File is too large to hide in this image. "
            f"Maximum file size for this cover image: {usable:,} bytes. "
            f"Your file is {len(file_bytes):,} bytes."
        )

    # ── Embed ────────────────────────────────────────────────────────────
    bits = _to_bits(payload)
    flat = []
    for r, g, b in cover.getdata():
        flat.extend([r, g, b])

    for i in range(0, len(bits) - 1, 2):
        channel_idx = i // 2
        two_bits = (bits[i] << 1) | bits[i + 1]
        flat[channel_idx] = (flat[channel_idx] & 0xFC) | two_bits

    if len(bits) % 2 == 1:
        channel_idx = len(bits) // 2
        flat[channel_idx] = (flat[channel_idx] & 0xFE) | bits[-1]

    new_pixels = [(flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat), 3)]
    result_img = Image.new("RGB", (width, height))
    result_img.putdata(new_pixels)

    buf = io.BytesIO()
    result_img.save(buf, format="PNG")
    return buf.getvalue()


def decode_file_from_image(encoded_bytes: bytes) -> tuple:
    """
    Extract the hidden file from a 2-bit LSB encoded PNG.
    """
    try:
        encoded = Image.open(io.BytesIO(encoded_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Not a valid image file: {e}")

    width, height = encoded.size
    flat = []
    for r, g, b in encoded.getdata():
        flat.extend([r, g, b])

    # Extract 2 LSBs from every channel
    bits = []
    for val in flat:
        bits.append((val >> 1) & 1)
        bits.append(val & 1)

    def read_bytes(offset_bits: int, n: int) -> tuple:
        chunk = bits[offset_bits: offset_bits + n * 8]
        if len(chunk) < n * 8:
            raise ValueError("Payload extraction failed: end of data reached prematurely.")
        return _bits_to_bytes(chunk), offset_bits + n * 8

    offset = 0
    try:
        # Read filename length (1 byte)
        fname_len_bytes, offset = read_bytes(offset, 1)
        fname_len = fname_len_bytes[0]

        if fname_len == 0 or fname_len > 255:
            raise ValueError("No valid StegoVault metadata found in this image.")

        # Read filename
        fname_data, offset = read_bytes(offset, fname_len)
        filename = fname_data.decode("utf-8")

        # Read file data length (4 bytes)
        size_data, offset = read_bytes(offset, 4)
        file_size = struct.unpack(">I", size_data)[0]

        remaining_bytes = (len(bits) - offset) // 8
        if file_size > remaining_bytes:
            raise ValueError("Metadata corruption: declared size exceeds image capacity.")

        # Read actual file data
        file_data, _ = read_bytes(offset, file_size)
        return file_data, filename
    except (ValueError, struct.error, UnicodeDecodeError):
        raise ValueError("This image does not contain a valid or readable StegoVault hidden file.")


# ---------------------------------------------------------------------------
# Audio Steganography — 1-bit LSB on WAV PCM samples
# ---------------------------------------------------------------------------


def encode_audio_lsb(audio_bytes: bytes, secret_bytes: bytes, secret_filename: str) -> bytes:
    buf_in = io.BytesIO(audio_bytes)
    try:
        wf_in = wave.open(buf_in, 'rb')
    except Exception as e:
        raise ValueError(f"WAV formatini o'qib bo'lmadi: {e}")

    params = wf_in.getparams()
    n_frames = wf_in.getnframes()
    sampwidth = wf_in.getsampwidth()
    raw_data = bytearray(wf_in.readframes(n_frames))
    wf_in.close()

    # Metadata tayyorlash (Fayl nomi)
    name_bytes = secret_filename.encode('utf-8')
    # Struktura: [Nom uzunligi (4b)] + [Nom] + [Fayl mazmuni]
    full_payload = struct.pack(">I", len(name_bytes)) + name_bytes + secret_bytes

    # Header: Umumiy payload uzunligi
    header = struct.pack(">I", len(full_payload))
    bits = _to_bits(header + full_payload)

    total_samples = n_frames * params.nchannels
    if len(bits) > total_samples:
        raise ValueError("Audio hajmi kichiklik qiladi.")

    # Kodlash - NumPy orqali tezkor (Vectorized)
    arr = np.frombuffer(raw_data, dtype=np.uint8).copy()
    bit_arr = np.array(bits, dtype=np.uint8)
    
    # Faqat kerakli namunalar (samples) ning LSB bitini o'zgartiramiz
    # Sampwidth qadam bilan (masalan 16-bitda har 2-bayt)
    target_indices = np.arange(0, len(bit_arr) * sampwidth, sampwidth)
    arr[target_indices] = (arr[target_indices] & 0xFE) | bit_arr

    buf_out = io.BytesIO()
    with wave.open(buf_out, 'wb') as wf_out:
        wf_out.setparams(params)
        wf_out.writeframes(arr.tobytes())
    return buf_out.getvalue()


def decode_audio_lsb(audio_bytes: bytes):
    buf_in = io.BytesIO(audio_bytes)
    with wave.open(buf_in, 'rb') as wf_in:
        sampwidth = wf_in.getsampwidth()
        raw_data = wf_in.readframes(wf_in.getnframes())

    # LSB bitlarni yig'ish - NumPy orqali juda tez
    arr = np.frombuffer(raw_data, dtype=np.uint8)
    # Sampwidth qadam bilan birinchi baytlarni (LSB) olamiz
    lsb_bits = (arr[::sampwidth] & 1).astype(np.uint8).tolist()
    bits = lsb_bits

    # 1. Umumiy payload uzunligini o'qish (32 bit)
    if len(bits) < 32: raise ValueError("Ma'lumot topilmadi.")
    total_len = struct.unpack(">I", _bits_to_bytes(bits[:32]))[0]

    # 2. To'liq payloadni olish
    payload_bytes = _bits_to_bytes(bits[32:32 + total_len * 8])

    # 3. Nom uzunligi va nomni ajratish
    name_len = struct.unpack(">I", payload_bytes[:4])[0]
    filename = payload_bytes[4:4 + name_len].decode('utf-8')

    # 4. Asl fayl baytlari
    secret_data = payload_bytes[4 + name_len:]

    return secret_data, filename


# ============================================================================
# OPTIMIZED VIDEO STEGANOGRAPHY - GRAYSCALE + HIGH COMPRESSION
# ============================================================================

def _get_video_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lower() if ext else '.avi'


def convert_to_grayscale(input_path: str, output_path: str) -> str:
    """Videoni grayscale ga o'tkazish (rangli ma'lumotni o'chirish)"""
    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Grayscale uchun 1 kanal
    fourcc = cv2.VideoWriter_fourcc(*'HFYU')  # Lossless YUV (grayscale)
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height), isColor=False)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        out.write(gray)

    cap.release()
    out.release()
    return output_path


def resize_video(input_path: str, output_path: str, max_width=640, max_height=480) -> str:
    """Videoni kichraytirish (hajmni kamaytirish uchun)"""
    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Aspect ratio saqlash
    scale = min(max_width / original_width, max_height / original_height)
    new_width = int(original_width * scale)
    new_height = int(original_height * scale)

    fourcc = cv2.VideoWriter_fourcc(*'HFYU')
    out = cv2.VideoWriter(output_path, fourcc, fps, (new_width, new_height), isColor=False)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (new_width, new_height))
        out.write(resized)

    cap.release()
    out.release()
    return output_path


def encode_video_lsb_optimized(input_path: str, secret_bytes: bytes, output_path: str,
                               frame_step=1, resize_to=None) -> str:
    """
    Optimallashtirilgan LSB kodlash - FIXED VERSION
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise ValueError("Video faylni ochib bo'lmadi")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0  # Default

    original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"📹 Original video: {original_width}x{original_height}, {fps}fps")

    # Kichraytirish
    if resize_to:
        width, height = resize_to
    else:
        width, height = original_width, original_height

    # Payload tayyorlash
    header = struct.pack(">I", len(secret_bytes))
    payload = header + secret_bytes
    bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
    total_bits = len(bits)

    print(f"📦 Ma'lumot: {len(secret_bytes)} bayt → {total_bits} bit")

    # MUHIM: Turli kodeklarni sinab ko'rish (platformaga qarab)
    codecs_to_try = [
        ('FFV1', '.avi'),  # FFV1 lossless (eng yaxshi)
        ('HFYU', '.avi'),  # Huffman YUV
        ('PNG ', '.avi'),  # PNG har bir kadr
        ('DIB ', '.avi'),  # Raw RGB
        ('MJPG', '.avi'),  # MJPEG (near-lossless)
    ]

    writer = None
    used_codec = None
    used_ext = '.avi'

    for codec, ext in codecs_to_try:
        fourcc = cv2.VideoWriter_fourcc(*codec)
        test_path = tempfile.NamedTemporaryFile(suffix=ext, delete=False).name
        test_writer = cv2.VideoWriter(test_path, fourcc, fps, (width, height), isColor=False)

        if test_writer.isOpened():
            writer = test_writer
            used_codec = codec
            used_ext = ext
            print(f"✅ Kodek ishlaydi: {codec}")
            # Tozalash
            test_writer.release()
            os.unlink(test_path)
            break
        else:
            test_writer.release()
            os.unlink(test_path)
            print(f"❌ Kodek ishlamadi: {codec}")

    if not writer:
        # Fallback: MJPEG (deyarli lossless)
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height), isColor=False)
        used_codec = 'MJPG'
        print(f"⚠️ Fallback kodek: MJPG")

    bit_idx = 0
    frame_num = 0
    frames_modified = 0

    # Kesh uchun bitlarni saqlash
    frame_bits_cache = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Grayscale
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        # Resize
        if (width, height) != (original_width, original_height):
            gray = cv2.resize(gray, (width, height))

        # LSB yozish
        should_modify = (frame_num % frame_step == 0) and bit_idx < total_bits

        if should_modify:
            flat = gray.ravel()
            available_bits = flat.size
            to_modify = min(total_bits - bit_idx, available_bits)

            if to_modify > 0:
                frame_bits = bits[bit_idx:bit_idx + to_modify]
                flat[:to_modify] = (flat[:to_modify] & 0xFE) | frame_bits
                bit_idx += to_modify
                frames_modified += 1
                gray = flat.reshape(gray.shape)

                if frame_num < 5:  # Faqat birinchi 5 kadr uchun log
                    print(f"✏️ Kadr {frame_num}: {to_modify} bit yozildi")

        writer.write(gray)
        frame_num += 1

        if frame_num % 100 == 0:
            print(f"📊 Qayta ishlandi: {frame_num} kadr, {bit_idx}/{total_bits} bit")

        # Early stop
        if bit_idx >= total_bits and frame_num > 10:
            print(f"✅ Barcha ma'lumot yozildi! Davom etilmoqda...")

    cap.release()
    writer.release()

    print(f"\n📊 STATISTIKA:")
    print(f"   - Jami kadrlar: {frame_num}")
    print(f"   - O'zgartirilgan kadrlar: {frames_modified}")
    print(f"   - Yozilgan bitlar: {bit_idx}/{total_bits}")
    print(f"   - Ishlatilgan kodek: {used_codec}")

    # Faylni tekshirish
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        print(f"   - Chiqish fayl hajmi: {file_size / (1024 * 1024):.2f} MB")

        # VideoCapture bilan tekshirish
        test_cap = cv2.VideoCapture(output_path)
        if test_cap.isOpened():
            test_frames = int(test_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            print(f"   - VideoCapture kadrlar soni: {test_frames}")
            test_cap.release()
        else:
            print(f"   ⚠️ OGOHLANTIRISH: Chiqish faylni VideoCapture ocholmayapti!")
    else:
        print(f"   ❌ XATO: Chiqish fayl yaratilmadi!")

    return output_path


def decode_video_lsb_optimized(input_path: str, frame_step=1) -> bytes:
    """Optimallashtirilgan dekodlash - FIXED VERSION"""

    # Avval faylni tekshirish
    if not os.path.exists(input_path):
        raise ValueError(f"Fayl topilmadi: {input_path}")

    print(f"🔓 Dekodlash boshlandi: {input_path}")
    print(f"   Fayl hajmi: {os.path.getsize(input_path) / 1024:.2f} KB")

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        # Kodek haqida ma'lumot olish
        print("❌ VideoCapture ochilmadi!")
        print("   Mumkin sabablar:")
        print("   1. Video fayl buzuq")
        print("   2. Kodek qo'llab-quvvatlanmaydi")
        print("   3. Fayl formati noto'g'ri")

        # Fallback: ffmpeg bilan o'qish (agar mavjud bo'lsa)
        try:
            import subprocess
            print("🔄 ffmpeg bilan o'qishga urinish...")
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=width,height',
                                     '-of', 'default=noprint_wrappers=1', input_path],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ ffmpeg faylni taniydi")
            else:
                print("❌ ffmpeg ham o'qiy olmadi")
        except:
            pass

        raise ValueError("Video faylni ochib bo'lmadi. Fayl buzuq yoki kodek qo'llab-quvvatlanmaydi.")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"📹 Video ma'lumotlari:")
    print(f"   - Kadrlar soni: {total_frames}")
    print(f"   - O'lcham: {width}x{height}")
    print(f"   - FPS: {fps}")

    if total_frames == 0:
        cap.release()
        raise ValueError("VideoCapture kadrlarni o'qiy olmadi! Fayl formati noto'g'ri.")

    all_bits = []
    header_read = False
    payload_len = 0
    needed_bits = 32
    frame_num = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Grayscale o'qish
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        if frame_num % frame_step == 0:
            bits = (gray.ravel() & 1).astype(np.uint8)
            all_bits.extend(bits)

            # Header o'qish
            if not header_read and len(all_bits) >= 32:
                header_bytes = np.packbits(all_bits[:32]).tobytes()
                payload_len = struct.unpack(">I", header_bytes)[0]
                print(f"📦 Header: payload_len = {payload_len} bayt")

                if payload_len <= 0 or payload_len > 100 * 1024 * 1024:
                    raise ValueError(f"Yashirin ma'lumot topilmadi (payload_len={payload_len})")

                needed_bits = 32 + (payload_len * 8)
                header_read = True
                print(f"🎯 Kerak: {needed_bits} bit, Har bir kadr: {gray.size} bit")

        if header_read and len(all_bits) >= needed_bits:
            print(f"✅ Yetarli bit: {len(all_bits)}/{needed_bits}")
            break

        frame_num += 1
        if frame_num % 100 == 0:
            print(f"📖 O'qildi: {frame_num}/{total_frames} kadr, {len(all_bits)} bit")

    cap.release()

    if not header_read:
        raise ValueError(f"Header o'qilmadi! Jami: {len(all_bits)} bit, Kerak: 32")

    if len(all_bits) < needed_bits:
        raise ValueError(f"Ma'lumot to'liq emas! Bor: {len(all_bits)}, Kerak: {needed_bits}")

    data_bits = all_bits[32:needed_bits]
    result = np.packbits(data_bits).tobytes()
    print(f"✨ Tiklandi: {len(result)} bayt")

    return result

# def encode_video_lsb(video_bytes: bytes, secret_bytes: bytes,
#                      filename: str = "video.avi",
#                      progress_cb=None) -> bytes:
#
#
#
#     ext = _get_video_extension(filename)
#     tmp_in = None
#     tmp_out = None
#
#     try:
#         with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
#             f.write(video_bytes)
#             tmp_in = f.name
#
#         cap = cv2.VideoCapture(tmp_in)
#         if not cap.isOpened():
#             raise ValueError("Video faylni ochib bo'lmadi.")
#
#         fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
#         width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#         height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#         total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
#
#         # Payload: [Header: 4 byte] + [Data]
#         header = struct.pack(">I", len(secret_bytes))
#         payload = header + secret_bytes
#         bits = _to_bits(payload)
#         total_bits = len(bits)
#
#         # MUHIM: Lossless AVI fayl yaratish
#         # 'png ' (bo'sh joy bilan) kadrlarni yo'qotishsiz saqlaydi
#         with tempfile.NamedTemporaryFile(suffix='.avi', delete=False) as f:
#             tmp_out = f.name
#
#         # Kodeklar navbati: png (lossless), HFYU (lossless), DIB (raw)
#         codecs = ['png ', 'HFYU', 'DIB ']
#         writer = None
#         for c in codecs:
#             fourcc = cv2.VideoWriter_fourcc(*c)
#             writer = cv2.VideoWriter(tmp_out, fourcc, fps, (width, height))
#             if writer.isOpened():
#                 break
#
#         if not writer or not writer.isOpened():
#             raise ValueError("Tizimda lossless video kodek (PNG/HFYU) topilmadi.")
#
#         bit_idx = 0
#         frame_num = 0
#
#         while True:
#             ret, frame = cap.read()
#             if not ret:
#                 break
#
#             if frame_num % 10 == 0 and bit_idx < total_bits:
#                 # NumPy orqali massivga bitlarni yozish (tezkor)
#                 flat = frame.ravel()
#                 to_modify = min(total_bits - bit_idx, flat.size)
#
#                 # Shu kadr uchun bitlarni olamiz
#                 frame_bits = np.array(bits[bit_idx:bit_idx + to_modify], dtype=np.uint8)
#
#                 # Kadr piksellarining LSB bitini o'zgartirish
#                 flat[:to_modify] = (flat[:to_modify] & 0xFE) | frame_bits
#                 bit_idx += to_modify
#
#                 frame = flat.reshape(frame.shape)
#
#             writer.write(frame)
#             frame_num += 1
#
#             if progress_cb and total_frames > 0:
#                 progress_cb(min(int(frame_num / total_frames * 100), 99))
#
#         cap.release()
#         writer.release()
#
#         with open(tmp_out, 'rb') as f:
#             return f.read()
#
#     finally:
#         for p in [tmp_in, tmp_out]:
#             if p and os.path.exists(p):
#                 try:
#                     os.unlink(p)
#                 except:
#                     pass

#
# def decode_video_lsb(video_bytes: bytes, filename: str = "video.avi",
#                      progress_cb=None) -> bytes:
#     import cv2
#     import numpy as np
#     import tempfile
#     import os
#     import struct
#
#     ext = _get_video_extension(filename)
#     tmp_path = None
#
#     try:
#         with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
#             f.write(video_bytes)
#             tmp_path = f.name
#
#         cap = cv2.VideoCapture(tmp_path)
#         if not cap.isOpened():
#             raise ValueError("Video faylni ochib bo'lmadi.")
#
#         total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
#
#         all_bits = []
#         header_read = False
#         payload_len = 0
#         needed_bits = 32
#         frame_num = 0
#
#         while True:
#             ret, frame = cap.read()
#             if not ret:
#                 break
#
#             if frame_num % 10 == 0:
#                 # Tezlik uchun numpy raveldand foydalanamiz
#                 flat = frame.ravel()
#
#                 # Har bir pikselning LSB bitini bittada olamiz
#                 current_bits = (flat & 1).tolist()
#                 all_bits.extend(current_bits)
#
#                 # Header hali o'qilmagan bo'lsa
#                 if not header_read and len(all_bits) >= 32:
#                     header_bytes = _bits_to_bytes(all_bits[:32])
#                     payload_len = struct.unpack(">I", header_bytes)[0]
#
#                     # Tekshiruv: agar payload_len asossiz katta bo'lsa, demak ma'lumot yo'q
#                     if payload_len <= 0 or payload_len > 100 * 1024 * 1024:  # 100MB limit
#                         raise ValueError("Ushbu videoda yashirin ma'lumot topilmadi yoki u buzilgan.")
#
#                     needed_bits = 32 + (payload_len * 8)
#                     header_read = True
#
#             if header_read and len(all_bits) >= needed_bits:
#                 break
#
#             frame_num += 1
#             if progress_cb and total_frames > 0:
#                 progress_cb(min(int(frame_num / total_frames * 100), 99))
#
#         cap.release()
#
#         if not header_read or len(all_bits) < needed_bits:
#             raise ValueError("Yashirin ma'lumotni to'liq o'qib bo'lmadi (Video kesilgan yoki siqilgan).")
#
#         data_bits = all_bits[32:needed_bits]
#         return _bits_to_bytes(data_bits)
#
#     finally:
#         if tmp_path and os.path.exists(tmp_path):
#             os.unlink(tmp_path)