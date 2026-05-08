#!/bin/bash
# postinst.sh

APP_DIR="/usr/share/stegovault"

echo "🌐 StegoVault: Kutubxonalar requirements.txt orqali o'rnatilmoqda..."

# 1. Virtual muhit yaratish (agar mavjud bo'lmasa)
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv $APP_DIR/venv
fi

# 2. Pipni yangilash
$APP_DIR/venv/bin/python3 -m pip install --upgrade pip

# 3. Requirements orqali o'rnatish
if [ -f "$APP_DIR/requirements.txt" ]; then
    echo "📄 requirements.txt topildi, o'rnatish boshlanmoqda..."
    $APP_DIR/venv/bin/python3 -m pip install -r $APP_DIR/requirements.txt
else
    echo "⚠️ requirements.txt topilmadi! Standart kutubxonalar o'rnatilmoqda..."
    $APP_DIR/venv/bin/python3 -m pip install flask pillow
fi

# 4. Ruxsatlarni to'g'rilash
chmod -R 755 $APP_DIR

# 5. Servisni faollashtirish
systemctl daemon-reload
systemctl enable stegovault.service
systemctl start stegovault.service

echo "✅ O'rnatish muvaffaqiyatli yakunlandi!"