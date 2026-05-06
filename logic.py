"""
logic.py — StegoVault Steganografiya Logikasi
==============================================

1. Matn steganografiyasi  : Zero-width belgilar (U+200C/200D)
2. Rasm steganografiyasi  : 2-bit LSB (fayl-rasmga)
3. Audio steganografiyasi : 1-bit LSB (WAV PCM namunalariga)
4. Video steganografiyasi : 1-bit LSB (kadr piksellariga) + lossless FFmpeg

Video header tuzilmasi:
  [0:8]   — yashirin fayl hajmi, uint64 big-endian
  [8:264] — yashirin fayl nomi, 256 bayt UTF-8 null-padded
  [264:]  — yashirin fayl ma'lumotlari
"""

# TO'G'RILANDI: barcha kerakli importlar bir joyda
import io
import os
import struct
import subprocess
import tempfile
import wave
import zipfile
from pathlib import Path           # ← avval yo'q edi → NameError chiqardi

import cv2
import numpy as np
from PIL import Image


# ===========================================================================
# ZERO-WIDTH BELGILAR (Matn steganografiyasi)
# ===========================================================================

ZW_ZERO  = "\u200c"   # Zero-width non-joiner  → bit 0
ZW_ONE   = "\u200d"   # Zero-width joiner       → bit 1
ZW_START = "\u200b"   # Zero-width space        → chegara (start/end)
ZW_SEP   = "\u2060"   # Word joiner             → bayt ajratuvchi


def _text_to_bits(text: str) -> str:
    encoded = text.encode("utf-8")
    return "".join(f"{byte:08b}" for byte in encoded)


def _bits_to_text(bits: str) -> str:
    raw = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = bits[i:i + 8]
        if len(byte) < 8:
            break
        raw.append(int(byte, 2))
    return raw.decode("utf-8")


def encode_text_zero_width(cover: str, secret: str) -> str:
    if not cover:  raise ValueError("Cover text bo'sh bo'lmasligi kerak.")
    if not secret: raise ValueError("Secret text bo'sh bo'lmasligi kerak.")

    bits = _text_to_bits(secret)
    payload_chars = [ZW_START]
    for i, bit in enumerate(bits):
        payload_chars.append(ZW_ONE if bit == "1" else ZW_ZERO)
        if (i + 1) % 8 == 0:
            payload_chars.append(ZW_SEP)
    payload_chars.append(ZW_START)

    payload = "".join(payload_chars)
    return cover[0] + payload + cover[1:]


def decode_text_zero_width(encoded: str) -> str:
    start = encoded.find(ZW_START)
    if start == -1:
        raise ValueError("Bu matda yashirin xabar topilmadi.")
    end = encoded.find(ZW_START, start + 1)
    if end == -1:
        raise ValueError("Buzilgan yashirin xabar: oxirgi chegara yo'q.")

    payload = encoded[start + 1:end]
    bits = []
    for ch in payload:
        if   ch == ZW_ZERO:  bits.append("0")
        elif ch == ZW_ONE:   bits.append("1")
        elif ch == ZW_SEP:   continue
        else: raise ValueError(f"Kutilmagan belgi: U+{ord(ch):04X}")

    if not bits:
        raise ValueError("Payload bo'sh — yashirin xabar yo'q.")

    trimmed = "".join(bits[: (len(bits) // 8) * 8])
    try:
        return _bits_to_text(trimmed)
    except Exception as exc:
        raise ValueError(f"Payloadni dekodlab bo'lmadi: {exc}") from exc


# ===========================================================================
# UMUMIY BIT KONVERSIYA YORDAMCHILARI
# (Rasm, Audio va Video uchun bir xil versiya — ikki xillik bartaraf etildi)
# ===========================================================================

def _to_bits(data: bytes) -> list:
    """bytes → bit ro'yxati (MSB birinchi)."""
    bits = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


# TO'G'RILANDI: avval ikki xil _bits_to_bytes() versiyasi bor edi.
# Endi yagona versiya — barcha modullar shu funksiyani ishlatadi.
def _bits_to_bytes(bits: list) -> bytes:
    """bit ro'yxati → bytes (MSB birinchi). Qo'shimcha bitlar e'tiborga olinmaydi."""
    result = bytearray()
    for i in range(0, len(bits) - 7, 8):
        val = 0
        for b in bits[i:i + 8]:
            val = (val << 1) | b
        result.append(val)
    return bytes(result)


# Alias — video qismida _bytes_to_bits nomi ishlatilgan edi
_bytes_to_bits = _to_bits


# ===========================================================================
# RASM STEGANOGRAFIYASI (2-bit LSB, fayl-rasmga)
# ===========================================================================

def image_capacity(cover_bytes: bytes) -> int:
    """Rasmning maksimal sig'imini baytlarda qaytaradi."""
    try:
        img = Image.open(io.BytesIO(cover_bytes))
        w, h = img.size
        return (w * h * 3 * 2) // 8
    except Exception as e:
        raise ValueError(f"Cover rasmni o'qib bo'lmadi: {e}")


def encode_file_in_image(cover_bytes: bytes, file_bytes: bytes, filename: str) -> bytes:
    """Har qanday faylni rasmga 2-bit LSB usulida yashiradi."""
    try:
        cover = Image.open(io.BytesIO(cover_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Noto'g'ri cover rasm formati: {e}")

    width, height = cover.size
    max_bytes = (width * height * 3 * 2) // 8

    fname_encoded = filename.encode("utf-8")[:255]
    header  = bytes([len(fname_encoded)]) + fname_encoded + struct.pack(">I", len(file_bytes))
    payload = header + file_bytes

    if len(payload) > max_bytes:
        usable = max_bytes - len(header)
        raise ValueError(
            f"Fayl rasm sig'imidan katta. "
            f"Maksimal fayl hajmi: {usable:,} bayt. "
            f"Sizning faylingiz: {len(file_bytes):,} bayt."
        )

    bits = _to_bits(payload)
    flat = []
    for r, g, b in cover.getdata():
        flat.extend([r, g, b])

    for i in range(0, len(bits) - 1, 2):
        ch_idx   = i // 2
        two_bits = (bits[i] << 1) | bits[i + 1]
        flat[ch_idx] = (flat[ch_idx] & 0xFC) | two_bits

    if len(bits) % 2 == 1:
        ch_idx = len(bits) // 2
        flat[ch_idx] = (flat[ch_idx] & 0xFE) | bits[-1]

    new_pixels = [(flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat), 3)]
    result_img = Image.new("RGB", (width, height))
    result_img.putdata(new_pixels)

    buf = io.BytesIO()
    result_img.save(buf, format="PNG")
    return buf.getvalue()


def decode_file_from_image(encoded_bytes: bytes) -> tuple:
    """2-bit LSB kodlangan PNG rasmdan yashirin faylni chiqaradi."""
    try:
        encoded = Image.open(io.BytesIO(encoded_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Noto'g'ri rasm fayli: {e}")

    flat = []
    for r, g, b in encoded.getdata():
        flat.extend([r, g, b])

    bits = []
    for val in flat:
        bits.append((val >> 1) & 1)
        bits.append(val & 1)

    def read_bytes(offset_bits: int, n: int) -> tuple:
        chunk = bits[offset_bits: offset_bits + n * 8]
        if len(chunk) < n * 8:
            raise ValueError("Payload noto'g'ri: ma'lumot tugadi.")
        return _bits_to_bytes(chunk), offset_bits + n * 8

    offset = 0
    try:
        fname_len_bytes, offset = read_bytes(offset, 1)
        fname_len = fname_len_bytes[0]

        if fname_len == 0 or fname_len > 255:
            raise ValueError("Bu rasmda StegoVault metadata topilmadi.")

        fname_data, offset = read_bytes(offset, fname_len)
        filename = fname_data.decode("utf-8")

        size_data, offset = read_bytes(offset, 4)
        file_size = struct.unpack(">I", size_data)[0]

        remaining = (len(bits) - offset) // 8
        if file_size > remaining:
            raise ValueError("Metadata buzilgan: e'lon qilingan hajm sig'imdan katta.")

        file_data, _ = read_bytes(offset, file_size)
        return file_data, filename

    except (ValueError, struct.error, UnicodeDecodeError):
        raise ValueError("Bu rasmda to'g'ri StegoVault yashirin fayl topilmadi.")


# ===========================================================================
# AUDIO STEGANOGRAFIYASI (1-bit LSB, WAV PCM)
# ===========================================================================

def encode_audio_lsb(audio_bytes: bytes, secret_bytes: bytes, secret_filename: str) -> bytes:
    buf_in = io.BytesIO(audio_bytes)
    try:
        wf_in = wave.open(buf_in, 'rb')
    except Exception as e:
        raise ValueError(f"WAV formatini o'qib bo'lmadi: {e}")

    params     = wf_in.getparams()
    n_frames   = wf_in.getnframes()
    sampwidth  = wf_in.getsampwidth()
    raw_data   = bytearray(wf_in.readframes(n_frames))
    wf_in.close()

    name_bytes   = secret_filename.encode('utf-8')
    full_payload = struct.pack(">I", len(name_bytes)) + name_bytes + secret_bytes
    header       = struct.pack(">I", len(full_payload))
    bits         = _to_bits(header + full_payload)

    total_samples = n_frames * params.nchannels
    if len(bits) > total_samples:
        raise ValueError("Audio hajmi yashirish uchun kichiklik qiladi.")

    arr     = np.frombuffer(raw_data, dtype=np.uint8).copy()
    bit_arr = np.array(bits, dtype=np.uint8)

    target_indices = np.arange(0, len(bit_arr) * sampwidth, sampwidth)
    arr[target_indices] = (arr[target_indices] & 0xFE) | bit_arr

    buf_out = io.BytesIO()
    with wave.open(buf_out, 'wb') as wf_out:
        wf_out.setparams(params)
        wf_out.writeframes(arr.tobytes())
    return buf_out.getvalue()


def decode_audio_lsb(audio_bytes: bytes) -> tuple:
    buf_in = io.BytesIO(audio_bytes)
    with wave.open(buf_in, 'rb') as wf_in:
        sampwidth = wf_in.getsampwidth()
        raw_data  = wf_in.readframes(wf_in.getnframes())

    arr      = np.frombuffer(raw_data, dtype=np.uint8)
    lsb_bits = (arr[::sampwidth] & 1).astype(np.uint8).tolist()

    if len(lsb_bits) < 32:
        raise ValueError("Ma'lumot topilmadi.")

    total_len    = struct.unpack(">I", _bits_to_bytes(lsb_bits[:32]))[0]
    payload_bits = lsb_bits[32: 32 + total_len * 8]

    if len(payload_bits) < total_len * 8:
        raise ValueError("Audio ma'lumoti to'liq emas.")

    payload_bytes = _bits_to_bytes(payload_bits)

    name_len  = struct.unpack(">I", payload_bytes[:4])[0]
    filename  = payload_bytes[4: 4 + name_len].decode('utf-8')
    secret    = payload_bytes[4 + name_len:]

    return secret, filename

"""
logic.py — StegoVault Steganografiya Logikasi
==============================================

1. Matn steganografiyasi  : Zero-width belgilar (U+200C/200D)
2. Rasm steganografiyasi  : 2-bit LSB (fayl-rasmga)
3. Audio steganografiyasi : 1-bit LSB (WAV PCM namunalariga)
4. Video steganografiyasi : 1-bit LSB (kadr piksellariga) + lossless FFmpeg

Video header tuzilmasi:
  [0:8]   — yashirin fayl hajmi, uint64 big-endian
  [8:264] — yashirin fayl nomi, 256 bayt UTF-8 null-padded
  [264:]  — yashirin fayl ma'lumotlari
"""

# TO'G'RILANDI: barcha kerakli importlar bir joyda
import io
import os
import struct
import subprocess
import tempfile
import wave
import zipfile
from pathlib import Path           # ← avval yo'q edi → NameError chiqardi

import cv2
import numpy as np
from PIL import Image


# ===========================================================================
# ZERO-WIDTH BELGILAR (Matn steganografiyasi)
# ===========================================================================

ZW_ZERO  = "\u200c"   # Zero-width non-joiner  → bit 0
ZW_ONE   = "\u200d"   # Zero-width joiner       → bit 1
ZW_START = "\u200b"   # Zero-width space        → chegara (start/end)
ZW_SEP   = "\u2060"   # Word joiner             → bayt ajratuvchi


def _text_to_bits(text: str) -> str:
    encoded = text.encode("utf-8")
    return "".join(f"{byte:08b}" for byte in encoded)


def _bits_to_text(bits: str) -> str:
    raw = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = bits[i:i + 8]
        if len(byte) < 8:
            break
        raw.append(int(byte, 2))
    return raw.decode("utf-8")


def encode_text_zero_width(cover: str, secret: str) -> str:
    if not cover:  raise ValueError("Cover text bo'sh bo'lmasligi kerak.")
    if not secret: raise ValueError("Secret text bo'sh bo'lmasligi kerak.")

    bits = _text_to_bits(secret)
    payload_chars = [ZW_START]
    for i, bit in enumerate(bits):
        payload_chars.append(ZW_ONE if bit == "1" else ZW_ZERO)
        if (i + 1) % 8 == 0:
            payload_chars.append(ZW_SEP)
    payload_chars.append(ZW_START)

    payload = "".join(payload_chars)
    return cover[0] + payload + cover[1:]


def decode_text_zero_width(encoded: str) -> str:
    start = encoded.find(ZW_START)
    if start == -1:
        raise ValueError("Bu matda yashirin xabar topilmadi.")
    end = encoded.find(ZW_START, start + 1)
    if end == -1:
        raise ValueError("Buzilgan yashirin xabar: oxirgi chegara yo'q.")

    payload = encoded[start + 1:end]
    bits = []
    for ch in payload:
        if   ch == ZW_ZERO:  bits.append("0")
        elif ch == ZW_ONE:   bits.append("1")
        elif ch == ZW_SEP:   continue
        else: raise ValueError(f"Kutilmagan belgi: U+{ord(ch):04X}")

    if not bits:
        raise ValueError("Payload bo'sh — yashirin xabar yo'q.")

    trimmed = "".join(bits[: (len(bits) // 8) * 8])
    try:
        return _bits_to_text(trimmed)
    except Exception as exc:
        raise ValueError(f"Payloadni dekodlab bo'lmadi: {exc}") from exc


# ===========================================================================
# UMUMIY BIT KONVERSIYA YORDAMCHILARI
# (Rasm, Audio va Video uchun bir xil versiya — ikki xillik bartaraf etildi)
# ===========================================================================

def _to_bits(data: bytes) -> list:
    """bytes → bit ro'yxati (MSB birinchi)."""
    bits = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


# TO'G'RILANDI: avval ikki xil _bits_to_bytes() versiyasi bor edi.
# Endi yagona versiya — barcha modullar shu funksiyani ishlatadi.
def _bits_to_bytes(bits: list) -> bytes:
    """bit ro'yxati → bytes (MSB birinchi). Qo'shimcha bitlar e'tiborga olinmaydi."""
    result = bytearray()
    for i in range(0, len(bits) - 7, 8):
        val = 0
        for b in bits[i:i + 8]:
            val = (val << 1) | b
        result.append(val)
    return bytes(result)


# Alias — video qismida _bytes_to_bits nomi ishlatilgan edi
_bytes_to_bits = _to_bits


# ===========================================================================
# RASM STEGANOGRAFIYASI (2-bit LSB, fayl-rasmga)
# ===========================================================================

def image_capacity(cover_bytes: bytes) -> int:
    """Rasmning maksimal sig'imini baytlarda qaytaradi."""
    try:
        img = Image.open(io.BytesIO(cover_bytes))
        w, h = img.size
        return (w * h * 3 * 2) // 8
    except Exception as e:
        raise ValueError(f"Cover rasmni o'qib bo'lmadi: {e}")


def encode_file_in_image(cover_bytes: bytes, file_bytes: bytes, filename: str) -> bytes:
    """Har qanday faylni rasmga 2-bit LSB usulida yashiradi."""
    try:
        cover = Image.open(io.BytesIO(cover_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Noto'g'ri cover rasm formati: {e}")

    width, height = cover.size
    max_bytes = (width * height * 3 * 2) // 8

    fname_encoded = filename.encode("utf-8")[:255]
    header  = bytes([len(fname_encoded)]) + fname_encoded + struct.pack(">I", len(file_bytes))
    payload = header + file_bytes

    if len(payload) > max_bytes:
        usable = max_bytes - len(header)
        raise ValueError(
            f"Fayl rasm sig'imidan katta. "
            f"Maksimal fayl hajmi: {usable:,} bayt. "
            f"Sizning faylingiz: {len(file_bytes):,} bayt."
        )

    bits = _to_bits(payload)
    flat = []
    for r, g, b in cover.getdata():
        flat.extend([r, g, b])

    for i in range(0, len(bits) - 1, 2):
        ch_idx   = i // 2
        two_bits = (bits[i] << 1) | bits[i + 1]
        flat[ch_idx] = (flat[ch_idx] & 0xFC) | two_bits

    if len(bits) % 2 == 1:
        ch_idx = len(bits) // 2
        flat[ch_idx] = (flat[ch_idx] & 0xFE) | bits[-1]

    new_pixels = [(flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat), 3)]
    result_img = Image.new("RGB", (width, height))
    result_img.putdata(new_pixels)

    buf = io.BytesIO()
    result_img.save(buf, format="PNG")
    return buf.getvalue()


def decode_file_from_image(encoded_bytes: bytes) -> tuple:
    """2-bit LSB kodlangan PNG rasmdan yashirin faylni chiqaradi."""
    try:
        encoded = Image.open(io.BytesIO(encoded_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Noto'g'ri rasm fayli: {e}")

    flat = []
    for r, g, b in encoded.getdata():
        flat.extend([r, g, b])

    bits = []
    for val in flat:
        bits.append((val >> 1) & 1)
        bits.append(val & 1)

    def read_bytes(offset_bits: int, n: int) -> tuple:
        chunk = bits[offset_bits: offset_bits + n * 8]
        if len(chunk) < n * 8:
            raise ValueError("Payload noto'g'ri: ma'lumot tugadi.")
        return _bits_to_bytes(chunk), offset_bits + n * 8

    offset = 0
    try:
        fname_len_bytes, offset = read_bytes(offset, 1)
        fname_len = fname_len_bytes[0]

        if fname_len == 0 or fname_len > 255:
            raise ValueError("Bu rasmda StegoVault metadata topilmadi.")

        fname_data, offset = read_bytes(offset, fname_len)
        filename = fname_data.decode("utf-8")

        size_data, offset = read_bytes(offset, 4)
        file_size = struct.unpack(">I", size_data)[0]

        remaining = (len(bits) - offset) // 8
        if file_size > remaining:
            raise ValueError("Metadata buzilgan: e'lon qilingan hajm sig'imdan katta.")

        file_data, _ = read_bytes(offset, file_size)
        return file_data, filename

    except (ValueError, struct.error, UnicodeDecodeError):
        raise ValueError("Bu rasmda to'g'ri StegoVault yashirin fayl topilmadi.")


# ===========================================================================
# AUDIO STEGANOGRAFIYASI (1-bit LSB, WAV PCM)
# ===========================================================================

def encode_audio_lsb(audio_bytes: bytes, secret_bytes: bytes, secret_filename: str) -> bytes:
    buf_in = io.BytesIO(audio_bytes)
    try:
        wf_in = wave.open(buf_in, 'rb')
    except Exception as e:
        raise ValueError(f"WAV formatini o'qib bo'lmadi: {e}")

    params     = wf_in.getparams()
    n_frames   = wf_in.getnframes()
    sampwidth  = wf_in.getsampwidth()
    raw_data   = bytearray(wf_in.readframes(n_frames))
    wf_in.close()

    name_bytes   = secret_filename.encode('utf-8')
    full_payload = struct.pack(">I", len(name_bytes)) + name_bytes + secret_bytes
    header       = struct.pack(">I", len(full_payload))
    bits         = _to_bits(header + full_payload)

    total_samples = n_frames * params.nchannels
    if len(bits) > total_samples:
        raise ValueError("Audio hajmi yashirish uchun kichiklik qiladi.")

    arr     = np.frombuffer(raw_data, dtype=np.uint8).copy()
    bit_arr = np.array(bits, dtype=np.uint8)

    target_indices = np.arange(0, len(bit_arr) * sampwidth, sampwidth)
    arr[target_indices] = (arr[target_indices] & 0xFE) | bit_arr

    buf_out = io.BytesIO()
    with wave.open(buf_out, 'wb') as wf_out:
        wf_out.setparams(params)
        wf_out.writeframes(arr.tobytes())
    return buf_out.getvalue()


def decode_audio_lsb(audio_bytes: bytes) -> tuple:
    buf_in = io.BytesIO(audio_bytes)
    with wave.open(buf_in, 'rb') as wf_in:
        sampwidth = wf_in.getsampwidth()
        raw_data  = wf_in.readframes(wf_in.getnframes())

    arr      = np.frombuffer(raw_data, dtype=np.uint8)
    lsb_bits = (arr[::sampwidth] & 1).astype(np.uint8).tolist()

    if len(lsb_bits) < 32:
        raise ValueError("Ma'lumot topilmadi.")

    total_len    = struct.unpack(">I", _bits_to_bytes(lsb_bits[:32]))[0]
    payload_bits = lsb_bits[32: 32 + total_len * 8]

    if len(payload_bits) < total_len * 8:
        raise ValueError("Audio ma'lumoti to'liq emas.")

    payload_bytes = _bits_to_bytes(payload_bits)

    name_len  = struct.unpack(">I", payload_bytes[:4])[0]
    filename  = payload_bytes[4: 4 + name_len].decode('utf-8')
    secret    = payload_bytes[4 + name_len:]

    return secret, filename


# ===========================================================================
# VIDEO STEGANOGRAFIYASI — rawvideo pipe + FFV1 MKV (haqiqiy lossless)
# ===========================================================================
#
# MUAMMO va YECHIM:
#   ✗ Eski yondashuv: PNG kadrlar → FFmpeg yuv444p/bgr24 MP4/MKV
#     MP4 da YUV↔BGR konversiyasi LSB bitlarni buzadi (13-15% xato)
#
#   ✓ Yangi yondashuv: OpenCV kadrlar → raw BGR bytes pipe → FFmpeg FFV1 MKV
#     raw BGR pipe: hech qanday piksel konversiyasi yo'q
#     FFV1 codec: matematikally lossless, bgr24 formatini to'g'ridan saqlaydi
#
#   Natija: har qanday kirish formati (.mp4, .avi, .mkv ...) →
#           chiqish: .mkv (FFV1 lossless, LSB 100% saqlanadi)
#
# Header tuzilmasi (264 bayt):
#   [0:8]   — yashirin fayl hajmi (uint64 big-endian)
#   [8:264] — yashirin fayl nomi  (256 bayt UTF-8 null-padded)
#   [264:]  — yashirin fayl ma'lumotlari
# ===========================================================================

FILENAME_FIELD_BYTES = 256
SIZE_FIELD_BYTES     = 8
HEADER_BYTES         = SIZE_FIELD_BYTES + FILENAME_FIELD_BYTES   # 264


def _write_bits_to_frame(frame: np.ndarray, bits: list, start: int) -> tuple:
    """Kadrning R kanaliga (BGR[...,2]) bitlarni LSB usulida yozadi."""
    frame  = frame.copy().astype(np.uint8)
    h, w   = frame.shape[:2]
    avail  = bits[start: start + h * w]
    if not avail:
        return frame, 0
    r_ch = frame[:, :, 2].flatten().astype(np.int32)
    for i, bit in enumerate(avail):
        r_ch[i] = (r_ch[i] & 0xFE) | bit
    frame[:, :, 2] = r_ch.reshape(h, w).astype(np.uint8)
    return frame, len(avail)


def _read_bits_from_frame(frame: np.ndarray, count: int) -> list:
    """Kadrning R kanalidan count ta LSB bit o'qiydi."""
    r_ch = frame[:, :, 2].flatten()
    n    = min(count, len(r_ch))
    return [int(r_ch[i]) & 1 for i in range(n)]


def get_video_capacity(video_path: str) -> int:
    """Videoning maksimal yashirish sig'imini baytlarda qaytaradi."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Video ochilmadi: {video_path}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width       = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height      = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return (frame_count * width * height) // 8


def encode_video(cover_path: str, secret_data: bytes, secret_filename: str) -> tuple:
    """
    Videoga yashirin faylni LSB usulida yashiradi.

    Yondashuv:
      1. OpenCV bilan cover videoni kadr-kadr o'qish
      2. LSB bitlarni R kanaliga yozish
      3. O'zgartirilgan kadrlarni raw BGR bytes sifatida FFmpeg pipe orqali yuborish
      4. FFmpeg FFV1 codec bilan MKV ga yig'ish (hech qanday piksel konversiyasi yo'q)

    Returns:
        (encoded_video_bytes: bytes, '.mkv')
    """
    # Header + payload
    size_field = struct.pack('>Q', len(secret_data))
    name_enc   = secret_filename.encode('utf-8')[:FILENAME_FIELD_BYTES]
    name_field = name_enc.ljust(FILENAME_FIELD_BYTES, b'\x00')
    payload    = size_field + name_field + secret_data
    all_bits   = _bytes_to_bits(payload)
    total_bits = len(all_bits)

    cap = cv2.VideoCapture(cover_path)
    if not cap.isOpened():
        raise ValueError("Cover video ochilmadi.")

    fps      = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total_bits > n_frames * width * height:
        cap.release()
        raise ValueError(
            f"Video sig'imi yetarli emas. "
            f"Kerak: {total_bits // 8:,} B, "
            f"Mavjud: {n_frames * width * height // 8:,} B"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_mkv = os.path.join(tmpdir, 'encoded.mkv')

        # FFmpeg process: stdin raw BGR → FFV1 MKV
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-f', 'rawvideo', '-pix_fmt', 'bgr24',
            '-s', f'{width}x{height}',
            '-r', str(fps),
            '-i', 'pipe:0',
            '-c:v', 'ffv1',
            '-level', '3',
            '-pix_fmt', 'bgr24',
            out_mkv
        ]

        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        bit_offset = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if bit_offset < total_bits:
                    frame, written = _write_bits_to_frame(frame, all_bits, bit_offset)
                    bit_offset += written
                ffmpeg_proc.stdin.write(frame.tobytes())
        finally:
            cap.release()
            ffmpeg_proc.stdin.close()

        stderr = ffmpeg_proc.stderr.read()
        ffmpeg_proc.wait()
        if ffmpeg_proc.returncode != 0:
            raise RuntimeError(
                f"FFmpeg encode xatosi:\n{stderr[-600:].decode(errors='replace')}"
            )

        with open(out_mkv, 'rb') as f:
            return f.read(), '.mkv'


def decode_video(encoded_path: str) -> tuple:
    """
    Kodlangan videodan yashirin faylni tiklaydi.

    Yondashuv:
      1. FFmpeg bilan videoni raw BGR bytes sifatida pipe orqali chiqarish
      2. Har kadrning R kanalidan LSB bitlarni o'qish
      3. Header (264 bayt) → fayl hajmi va nomi
      4. Payload → asl fayl ma'lumotlari

    Returns:
        (secret_data: bytes, secret_filename: str)
    """
    # Video o'lchamini aniqlaymiz
    probe = cv2.VideoCapture(encoded_path)
    if not probe.isOpened():
        raise ValueError("Kodlangan video ochilmadi.")
    width  = int(probe.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
    probe.release()

    if width == 0 or height == 0:
        raise ValueError("Video o'lchamini aniqlab bo'lmadi.")

    frame_size = width * height * 3   # BGR bytes per frame

    # FFmpeg: video → raw BGR pipe (hech qanday konversiya yo'q)
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-i', encoded_path,
        '-f', 'rawvideo',
        '-pix_fmt', 'bgr24',
        'pipe:1'
    ]
    ffmpeg_proc = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    header_bits  = HEADER_BYTES * 8   # 2112 bit
    collected    = []
    header_done  = False
    secret_size  = 0
    secret_fname = ''
    total_needed = header_bits

    try:
        while True:
            raw = ffmpeg_proc.stdout.read(frame_size)
            if len(raw) < frame_size:
                break

            # Har kadrdan TO'LIQ piksellarni o'qiymiz (encode bilan mos)
            # encode: frame_pixels = h*w bitlar har kadrga yoziladi
            # decode: xuddi shu h*w bitlarni o'qiymiz, keyin keraklilarini qirqamiz
            frame = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)

            # Bu kadrdan barcha piksel LSB larni olamiz
            extracted = _read_bits_from_frame(frame, height * width)
            collected.extend(extracted)

            # Header to'liq yig'ilganda parse qilamiz
            if not header_done and len(collected) >= header_bits:
                hdr_bytes    = _bits_to_bytes(collected[:header_bits])
                secret_size  = struct.unpack('>Q', hdr_bytes[:8])[0]
                name_raw     = hdr_bytes[8: 8 + FILENAME_FIELD_BYTES]
                secret_fname = name_raw.rstrip(b'\x00').decode('utf-8', errors='replace')
                total_needed = header_bits + secret_size * 8
                header_done  = True

            # Yetarli bit yig'ildimi?
            if header_done and len(collected) >= total_needed:
                break

    finally:
        ffmpeg_proc.stdout.close()
        ffmpeg_proc.wait()

    if not header_done:
        raise ValueError("Video juda qisqa — header o'qilmadi.")
    if len(collected) < total_needed:
        raise ValueError(
            f"Ma'lumot to'liq o'qilmadi. "
            f"Kerak: {total_needed} bit, o'qildi: {len(collected)} bit."
        )

    secret_data = _bits_to_bytes(collected[header_bits: total_needed])
    return secret_data, secret_fname