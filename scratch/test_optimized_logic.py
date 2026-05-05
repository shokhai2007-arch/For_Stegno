import os
import numpy as np
import cv2
import wave
import struct
from logic import encode_audio_lsb, decode_audio_lsb, encode_video_lsb, decode_video_lsb

def test_audio():
    print("Testing Audio LSB...")
    # Create a dummy WAV file
    sample_rate = 44100
    duration = 1
    t = np.linspace(0, duration, sample_rate * duration, endpoint=False)
    data = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    
    import io
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())
    audio_bytes = buf.getvalue()
    
    secret = b"Hello Audio!"
    filename = "secret.txt"
    
    encoded = encode_audio_lsb(audio_bytes, secret, filename)
    recovered_data, recovered_name = decode_audio_lsb(encoded)
    
    assert recovered_data == secret
    assert recovered_name == filename
    print("Audio LSB Test Passed!")

def test_video():
    print("Testing Video LSB...")
    # Create a dummy video file
    width, height = 640, 480
    fps = 30
    duration = 1
    num_frames = fps * duration
    
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.avi', delete=False) as tmp:
        tmp_path = tmp.name
        
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    writer = cv2.VideoWriter(tmp_path, fourcc, fps, (width, height))
    for _ in range(num_frames):
        frame = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
        writer.write(frame)
    writer.release()
    
    with open(tmp_path, 'rb') as f:
        video_bytes = f.read()
    os.unlink(tmp_path)
    
    secret = b"Hello Video!"
    encoded = encode_video_lsb(video_bytes, secret, "test.avi")
    recovered_data = decode_video_lsb(encoded, "stego.avi")
    
    assert recovered_data == secret
    print("Video LSB Test Passed!")

if __name__ == "__main__":
    try:
        test_audio()
        test_video()
        print("All tests passed!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Tests failed: {e}")
