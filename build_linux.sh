#!/bin/bash
# build_linux.sh

VERSION="1.0.0"
PKG_DIR="../package"

# 1. Eski build qoldiqlarini tozalash
rm -rf $PKG_DIR
mkdir -p $PKG_DIR/usr/share/stegovault
mkdir -p $PKG_DIR/usr/bin
mkdir -p $PKG_DIR/usr/share/applications
mkdir -p $PKG_DIR/etc/systemd/system/

# 2. Fayllarni nusxalash (venv-siz, shuning uchun yengil bo'ladi)
echo "📦 Fayllar nusxalanmoqda..."
cp -r ./* $PKG_DIR/usr/share/stegovault/
rm -rf $PKG_DIR/usr/share/stegovault/.git*
rm -f $PKG_DIR/usr/share/stegovault/stegovault.deb # Eski paketlarni kiritmaslik uchun

# 3. Wrapper script yaratish
echo "🛠 Wrapper yaratilmoqda..."
cat <<EOF > $PKG_DIR/usr/bin/stegovault
#!/bin/bash

show_help() {
    echo "StegoVault - Digital Steganography Tool"
    echo ""
    echo "Usage: stegovault [options]"
    echo "  --clean     Dasturni va barcha qoldiqlarni o'chirish"
    echo "  --help      Yordam menyusi"
    echo "  (no args)   Dasturni brauzerda ochish"
}

pure_clean() {
    echo "🧹 Tozalanmoqda..."
    sudo systemctl stop stegovault.service 2>/dev/null
    sudo systemctl disable stegovault.service 2>/dev/null
    sudo rm -f /etc/systemd/system/stegovault.service
    sudo rm -rf /usr/share/stegovault
    sudo rm -f /usr/share/applications/stegovault.desktop
    sudo rm -f /usr/bin/stegovault
    sudo fuser -k 9001/tcp 2>/dev/null || true
    echo "✅ Tozalandi. To'liq o'chirish uchun: sudo apt purge stegovault"
}

case "\$1" in
    --help) show_help ;;
    --clean) pure_clean ;;
    "")
        xdg-open "http://127.0.0.1:9001" || echo "Brauzerni ochib bo'lmadi. http://127.0.0.1:9001 ga kiring."
        ;;
    *) echo "Xato! --help yozing." ;;
esac
EOF
chmod +x $PKG_DIR/usr/bin/stegovault

# 4. Desktop Entry yaratish
cat <<EOF > $PKG_DIR/usr/share/applications/stegovault.desktop
[Desktop Entry]
Name=StegoVault
Comment=Steganography Tool
Exec=/usr/bin/stegovault
Icon=/usr/share/stegovault/static/image/logo.png
Terminal=false
Type=Application
Categories=Utility;
EOF

# 5. Systemd Service yaratish
cat <<EOF > $PKG_DIR/etc/systemd/system/stegovault.service
[Unit]
Description=StegoVault Flask Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/usr/share/stegovault
ExecStart=/usr/share/stegovault/venv/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 6. Paketlash (Lightweight - venv paketga kirmaydi)
echo "🛠 .DEB yig'ilmoqda..."
fpm -s dir -t deb \
  -n stegovault \
  -v $VERSION \
  -C $PKG_DIR \
  -p stegovault.deb \
  --depends python3 \
  --depends python3-venv \
  --depends python3-tk \
  --after-install ./postinst.sh \
  usr etc

echo "✅ Tayyor: stegovault.deb"