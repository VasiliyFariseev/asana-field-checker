#!/bin/bash
# Собирает архив для раздачи: dist/Field-Checker.zip
set -e
cd "$(dirname "$0")"
rm -rf dist/Field-Checker dist/Field-Checker.zip
mkdir -p dist/Field-Checker
cp START_MAC.command START_WINDOWS.bat field_checker_ui.py field_checker.py \
   config.py README.md dist/Field-Checker/
chmod +x dist/Field-Checker/START_MAC.command
cd dist && zip -r -X Field-Checker.zip Field-Checker >/dev/null && cd ..
echo "✅ Готово: dist/Field-Checker.zip"
echo "⚠️  Внутри рабочий токен Asana — раздавать только личным сообщением."
