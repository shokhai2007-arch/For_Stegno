#!/usr/bin/env python3
import tempfile
import os
import cv2
import numpy as np

# Test qilish
test_secret = b"Hello World!"
print(f"Original: {test_secret}")

# Test video yaratish
test_video = tempfile.NamedTemporaryFile(suffix='.avi', delete=False).name
out = cv2.VideoWriter(test_video, cv2.VideoWriter_fourcc(*'MJPG'), 30, (160, 120), False)
for _ in range(50):
    frame = np.random.randint(0, 255, (120, 160), dtype=np.uint8)
    out.write(frame)
out.release()

# Kodlash va dekodlash
from logic import encode_video_simple, decode_video_simple

encoded = tempfile.NamedTemporaryFile(suffix='.avi', delete=False).name
encode_video_simple(test_video, test_secret, encoded)

decoded = decode_video_simple(encoded)

print(f"\nNatija: {decoded}")
print(f"To'g'ri: {test_secret == decoded}")

# Tozalash
os.unlink(test_video)
os.unlink(encoded)