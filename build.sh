#!/bin/bash
set -e

echo "===================================="
echo "  Сборка cd_envelope"
echo "===================================="
echo

echo "[1/3] Устанавливаю зависимости..."
pip install -r requirements.txt

echo
echo "[2/3] Чищу старые сборки..."
rm -rf build dist cd_envelope.spec

echo
echo "[3/3] Собираю бинарник..."
if [ -f icon.ico ]; then
    pyinstaller --onefile --name cd_envelope --icon=icon.ico cd_envelope.py
else
    pyinstaller --onefile --name cd_envelope cd_envelope.py
fi

echo
echo "===================================="
echo "  ГОТОВО!"
echo "  Файл: dist/cd_envelope"
echo "===================================="
