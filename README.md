# StegoVault Vault

**StegoVault** is a digital steganography application built with Python (Flask) and Pillow. It allows users to hide sensitive text within plain messages using invisible Unicode characters, and embed any generic file format (PDF, ZIP, DOCX, etc.) within images using advanced 2-bit Least Significant Bit (LSB) manipulation.

---

## 🚀 Features

- **Text-in-Text**: Hide messages inside plain text using non-rendering zero-width characters (`\u200b`, `\u200c`, `\u200d`, `\u2060`).
- **File-in-Image**: Embed any binary file within a host image.
- **2-bit LSB**: High-capacity encoding (2 bits per channel) that remains virtually invisible to the naked eye.
- **Metadata Restoration**: Automatically restores the original filename and file extension upon decoding.
- **Real-time Capacity Calculation**: Instantly see if your secret file fits within the selected carrier image.
- **Robust Error Handling**: Handles oversized files (413), server-side crashes (500), and network dropouts gracefully.
- **Modern UI**: A glassmorphic, dark-themed responsive interface.

---

## 🧠 How It Works

### 1. Image Steganography (2-bit LSB)

Unlike standard 1-bit LSB, StegoVault uses **2 bits per channel** (R, G, and B). This increases data capacity by 100% while maintaining high visual fidelity.

**Binary Header Format:**
| Length (Bytes) | Field | Description |
| :--- | :--- | :--- |
| 1 | Filename Length | Length of the original filename (max 255). |
| N | Filename | UTF-8 encoded filename. |
| 4 | File Size | 32-bit big-endian integer of the secret data size. |
| M | Payload | The actual binary file data. |

The decoder reads this header to perfectly reconstruct the file, including its name and MIME type for automatic downloads.

### 2. Text Steganography (Zero-Width)

StegoVault converts the secret message into a base-4 bitstream. Each 2-bit pair is mapped to one of four invisible Unicode characters:
- `00` ➔ `U+200B` (Zero Width Space)
- `01` ➔ `U+200C` (Zero Width Non-Joiner)
- `10` ➔ `U+200D` (Zero Width Joiner)
- `11` ➔ `U+2060` (Word Joiner)

These characters are stitched into the visible "cover" text. They are invisible in browsers and most text editors but can be extracted bit-by-bit to recover the original secret.

---

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/shokhai2007-arch/For_Stegno.git
   cd For_Stegno
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python app.py
   ```
   The app will be available at `http://127.0.0.1:5000`.

---

## 📂 Project Structure

- `app.py`: Flask server and API endpoints including global error handling.
- `logic.py`: Core steganography algorithms (Manual bit manipulation).
- `test_logic.py`: Comprehensive test suite for round-trip verification.
- `static/`: Frontend assets (CSS glassmorphism, JS interactivity).
- `templates/`: HTML5 layouts.

---

## ⚖️ License & Security

This tool is intended for educational purposes. While steganography provides "security through obscurity," it does not replace encryption. For high-stakes security, always encrypt your files *before* hiding them.

---
*Created with ❤️ by Antigravity AI.*
