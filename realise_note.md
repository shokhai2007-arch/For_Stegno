
# Release Information: StegoVault Professional

* **Title**: StegoVault – Secure Digital Steganography System
* **Version**: 1.0.2
* **Platforms**: Windows 10/11 (64-bit), Linux (Debian/Ubuntu)

---

## 🟢 Features

* **Zero-Width Text Encoding**: Hide secret messages inside plain-looking cover text.
* **2-bit LSB Image Steganography**: Embed files (images, PDFs, ZIPs) inside cover images with high capacity.
* **Metadata Restoration**: Automatically restores original filename and extension.
* **Real-time Capacity Calculation**: Instantly check if secret files fit within carrier images.
* **Modern UI**: Glassmorphic, dark-themed responsive interface.
* **Robust Error Handling**: Handles oversized files (413), server crashes (500), and network dropouts gracefully.

---

## 🟢 How It Works

### 1. Image Steganography (2-bit LSB)

* Uses 2 bits per channel (R, G, B) to increase capacity while keeping images visually unchanged.
* **Binary Header Format**:
  | Length (Bytes) | Field | Description |
  | :--- | :--- | :--- |
  | 1 | Filename Length | Max 255 bytes |
  | N | Filename | UTF-8 encoded |
  | 4 | File Size | 32-bit big-endian integer |
  | M | Payload | Actual file data |

### 2. Text Steganography (Zero-Width)

* Converts secret messages into base-4 bitstream.
* Each 2-bit pair maps to a Unicode character:

  * `00` → `U+200B` (Zero Width Space)
  * `01` → `U+200C` (Zero Width Non-Joiner)
  * `10` → `U+200D` (Zero Width Joiner)
  * `11` → `U+2060` (Word Joiner)

These characters are embedded invisibly in the cover text and can be extracted to recover the secret.

---

## 🟢 Windows Release (Standalone EXE)

* **File Name**: `StegoVault.exe`
* **Port**: 9001
* **Engine**: Flask 3.1.0 (Embedded)
* **UI**: Auto-launching web interface

**How to Run**:

1. Download `StegoVault.exe` from GitHub Release or Artifacts.
2. Double-click to launch.
3. The app starts a background server and opens your default browser.

**Stop the Application**:

* Terminate `StegoVault` in Task Manager.
* Closing the browser tab will **not** stop the server.

**Uninstallation**:

* Delete the `StegoVault.exe` file. No registry changes occur.

> **Note**: Windows Firewall may prompt on first launch. Allow access.

> **Tip**: Single-file design may take 2–3 seconds to start as assets are extracted.

---

## 🟢 Linux Release (DEB Package)

* **File Name**: `stegovault_*_amd64.deb`
* **Installation**:

```bash
sudo dpkg -i stegovault_*_amd64.deb
```

* **Executable**: `/usr/local/bin/stegovault`
* **UI**: Open a browser and navigate to `http://127.0.0.1:5000` after launch.

**How to Run**:

```bash
stegovault --help
```

**Uninstallation**:

```bash
sudo dpkg -r stegovault
```

> **Tip**: Ensure required dependencies are installed (`python3-tk`, `libgl1`, `libglib2.0-0`) before running.

---

## 🟢 License & Security

* Educational use only.
* Steganography provides "security through obscurity" but **does not replace encryption**. Encrypt files before hiding for real security.
* `.sig` digital signature ensures logo integrity.
