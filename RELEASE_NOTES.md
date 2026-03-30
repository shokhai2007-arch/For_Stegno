# Release Information: StegoVault Professional (Windows)

- **Title**: StegoVault — Secure Digital Steganography System for Windows OS
- **Version**: 1.0.2
- **Platform**: Windows 10/11 (64-bit)

---

# 🚀 StegoVault — Windows Deployment Walkthrough

The StegoVault project has been packaged into a high-performance, standalone `.exe` file. This allows you to run the complete steganography suite on any Windows machine without needing to install Python or any dependencies.

## 📦 Package Details

- **File Name**: `StegoVault.exe` (Standalone)
- **Version**: 1.0.2
- **Port**: **9001** (Configured to avoid common local conflicts)
- **Engine**: Flask 3.1.0 (Embedded)
- **UI**: Glassmorphic Web Interface (Auto-launching)

## 🚀 How to Run

1. **Download**: Get the `StegoVault.exe` from the latest GitHub Release or Artifacts.
2. **Launch**: Simply double-click the `StegoVault.exe` file.
3. **Wait**: The application will start a background server and **automatically open your default web browser** to the interface.

> [!NOTE]
> **No Installation Required**: Unlike the Linux version, this is a "Portable" application. All logic, templates, and static assets are bundled inside the single EXE file.

## 🛠 Features in this Release

- **Zero-Width Text Encoding**: Hide secret messages inside plain-looking cover text.
- **2-bit LSB Image Steganography**: Hide files (images, PDFs, ZIPs) inside cover images with high capacity.
- **Improved UI**: Sleek, modern design with real-time capacity checking.
- **Browser Integration**: Automatic redirection to the tool upon startup on port **9001**.

## 📂 Management

### Stop the Application
- To stop the application, locate the `StegoVault` process in your system tray or Task Manager and terminate it.
- Alternatively, you can close the browser tab, but the background server will continue to run until the EXE process is ended.

## 📜 Uninstallation
- To "uninstall", simply delete the `StegoVault.exe` file. No registry keys or system files are modified.

---
> [!IMPORTANT]
> **Firewall Warning**: Upon the first launch, Windows Firewall may ask for permission to allow the app to communicate on the network. Please allow this so the browser can talk to the internal server on port **9001**.

> [!TIP]
> **Performance**: The "One-file" approach ensures maximum portability, but might take 2-3 seconds to start up as it extracts assets to a temporary directory.
