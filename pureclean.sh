#!/bin/bash

echo "🚀 StegoVault: Tizimni to'liq tozalash boshlandi..."

# 1. Paketni o'chirish
echo "📦 Paket o'chirilmoqda (purge)..."
sudo apt purge --autoremove -y stegovault 2>/dev/null || true
sudo dpkg -P stegovault 2>/dev/null || true

# 2. Systemd servislarini tozalash
echo "⚙️ Systemd qoldiqlari tekshirilmoqda..."
sudo systemctl stop stegovault.service 2>/dev/null || true
sudo systemctl disable stegovault.service 2>/dev/null || true
sudo find /etc/systemd/system/ /lib/systemd/system/ /usr/lib/systemd/system/ -name "*stegovault*" -delete
sudo systemctl daemon-reload
sudo systemctl reset-failed

# 3. Fayllar va papkalarni o'chirish
echo "📂 Fayllar tizimi tozalanmoqda..."
sudo rm -rf /usr/share/stegovault
sudo rm -f /usr/bin/stegovault
sudo rm -f /usr/share/applications/stegovault.desktop
sudo rm -rf /var/lib/stegovault
sudo rm -rf /etc/stegovault

# 4. Foydalanuvchi ma'lumotlarini tozalash (Logs, Cache, Config)
echo "👤 Foydalanuvchi qoldiqlari o'chirilmoqda..."
rm -f ~/.stegovault.log
rm -rf ~/.cache/stegovault
rm -rf ~/.local/share/stegovault

# 5. Jarayonlarni (Process) to'xtatish
echo "🛑 Fondagi jarayonlar tekshirilmoqda..."
# 9001 portini band qilgan python jarayonini o'ldirish
sudo fuser -k 9001/tcp 2>/dev/null || true
# Nomi bo'yicha qidirib o'ldirish
sudo pkill -f "app.py" || true
sudo pkill -f "stegovault" || true

# 6. Tekshiruv
echo "🔍 Yakuniy tekshiruv:"
RESULT=$(dpkg -l | grep stegovault)
if [ -z "$RESULT" ]; then
    echo "✅ Tizim StegoVault-dan to'liq tozalandi."
else
    echo "⚠️ Diqqat: Ba'zi qoldiqlar qolgan bo'lishi mumkin: $RESULT"
fi

echo "✨ PureClean yakunlandi."
