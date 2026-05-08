#!/bin/bash
# build_linux.sh

VERSION="1.0.0"
PKG_DIR="../package"

# 1. Struktura yaratish
mkdir -p $PKG_DIR/usr/share/stegovault
mkdir -p $PKG_DIR/usr/bin
mkdir -p $PKG_DIR/usr/share/applications

# 2. Fayllarni nusxalash
cp -r . $PKG_DIR/usr/share/stegovault/
rm -rf $PKG_DIR/usr/share/stegovault/.git*

# 3. Wrapper script
cat <<EOF > $PKG_DIR/usr/bin/stegovault
#!/bin/bash
# Xatolarni ko'rish uchun log fayli (ixtiyoriy, troubleshoot uchun foydali)
LOG_FILE="\$HOME/.stegovault.log"

# Ilova papkasiga kirish
cd /usr/share/stegovault

# Python dasturini ishga tushirish va xatolarni logga yozish
python3 app.py >> "\$LOG_FILE" 2>&1 &
EOF
chmod +x $PKG_DIR/usr/bin/stegovault

# 4. Desktop entry
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

# 5. Paketlash
fpm -s dir -t deb \
  -n stegovault \
  -v $VERSION \
  -C $PKG_DIR \
  -p stegovault.deb \
  --depends python3 \
  --depends python3-tk \
  usr