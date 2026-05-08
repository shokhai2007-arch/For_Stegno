#!/bin/bash
# build_linux.sh

VERSION="1.0.0"
PKG_DIR="../package"

# 0. Eski build qoldiqlarini tozalash
rm -rf $PKG_DIR
mkdir -p $PKG_DIR/usr/share/stegovault
mkdir -p $PKG_DIR/usr/bin
mkdir -p $PKG_DIR/usr/share/applications

# 1. Fayllarni nusxalash
echo "📂 Fayllar nusxalanmoqda..."
cp -r ./* $PKG_DIR/usr/share/stegovault/
rm -rf $PKG_DIR/usr/share/stegovault/.git*

# 2. Virtual muhit yaratish va kutubxonalarni o'rnatish
# Bu dasturni boshqa kompyuterlarda "kutubxona topilmadi" xatosisiz ishlashini ta'minlaydi
echo "🐍 Virtual muhit (venv) tayyorlanmoqda..."
python3 -m venv $PKG_DIR/usr/share/stegovault/venv
source $PKG_DIR/usr/share/stegovault/venv/bin/activate
pip install --upgrade pip
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
else
    pip install flask pillow
fi
deactivate

# 3. Wrapper script (Terminal argumentlari bilan)
echo "🛠 Wrapper script yaratilmoqda..."
cat <<EOF > $PKG_DIR/usr/bin/stegovault
#!/bin/bash

# Yordam menyusi
show_help() {
    echo "StegoVault - Digital Steganography Tool"
    echo ""
    echo "Usage: stegovault [options]"
    echo ""
    echo "Options:"
    echo "  --clean     Tizimdagi barcha qoldiqlar va dastur fayllarini o'chirish"
    echo "  --help      Ushbu yordam menyusini ko'rsatish"
    echo "  (no args)   Dasturni GUI rejimida brauzerda ishga tushirish"
    echo ""
}

# O'chirish funksiyasi
pure_clean() {
    echo "🧹 StegoVault tizimdan tozalanmoqda..."
    echo "⚠️  To'liq o'chirish uchun 'sudo apt purge stegovault' tavsiya etiladi."

    sudo rm -rf /usr/share/stegovault
    sudo rm -f /usr/share/applications/stegovault.desktop
    rm -f ~/.stegovault.log
    # Portni band qilgan jarayonni o'ldirish
    sudo fuser -k 9001/tcp 2>/dev/null || true

    echo "✅ Fayllar o'chirildi."
    # Oxirida o'zini o'chiradi
    sudo rm -f /usr/bin/stegovault
}

# Argumentlar mantig'i
case "\$1" in
    --help)
        show_help
        ;;
    --clean)
        pure_clean
        ;;
    "")
        # Ilovani ishga tushirish
        cd /usr/share/stegovault
        # Venv ichidagi pythonni ishlatish
        ./venv/bin/python3 app.py > /dev/null 2>&1 &
        sleep 2
        xdg-open "http://127.0.0.1:9001"
        ;;
    *)
        echo "Noma'lum argument: \$1"
        show_help
        exit 1
        ;;
esac
EOF
chmod +x $PKG_DIR/usr/bin/stegovault

# 4. Desktop entry (Iconka uchun)
echo "🖼 Desktop entry yaratilmoqda..."
cat <<EOF > $PKG_DIR/usr/share/applications/stegovault.desktop
[Desktop Entry]
Name=StegoVault
Comment=Steganography Tool
Exec=/usr/bin/stegovault
Icon=/usr/share/stegovault/static/image/logo.png
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=true
EOF

# 5. Paketlash (FPM)
echo "📦 .DEB paket yig'ilmoqda..."
fpm -s dir -t deb \
  -n stegovault \
  -v $VERSION \
  -C $PKG_DIR \
  -p stegovault.deb \
  --depends python3 \
  --depends python3-tk \
  usr

echo "✨ Bajarildi! stegovault.deb tayyor."