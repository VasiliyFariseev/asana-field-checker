#!/bin/bash
# Field Checker — запуск на macOS.
# Двойной клик по этому файлу. Первый запуск может занять минуту:
# скрипт проверит Python и доустановит библиотеку requests.

cd "$(dirname "$0")" || exit 1

echo "──────────────────────────────────────────────"
echo "  Field Checker — подготовка окружения"
echo "──────────────────────────────────────────────"

alert() {
    /usr/bin/osascript -e "display alert \"Field Checker\" message \"$1\"" >/dev/null 2>&1
}

# ── 1. Ищем Python 3 ──
PY=""
for CAND in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3 /usr/bin/python3; do
    if command -v "$CAND" >/dev/null 2>&1; then
        PY="$(command -v "$CAND")"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "❌ Python 3 не найден."
    alert "Нужен Python 3. Сейчас откроется страница загрузки — установите Python 3 и запустите файл снова."
    open "https://www.python.org/downloads/macos/"
    read -r -p "Нажмите Enter, чтобы закрыть окно..."
    exit 1
fi
echo "✅ Python: $PY ($("$PY" -V 2>&1))"

# ── 2. Проверяем tkinter (графическое окно) ──
if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
    echo "❌ В этом Python нет tkinter."
    alert "В установленном Python нет модуля tkinter. Поставьте Python с python.org (там tkinter уже внутри) и запустите файл снова."
    open "https://www.python.org/downloads/macos/"
    read -r -p "Нажмите Enter, чтобы закрыть окно..."
    exit 1
fi
echo "✅ tkinter на месте"

# ── 3. Ставим requests, если его нет ──
ensure_requests() {
    "$PY" -c "import requests" >/dev/null 2>&1 && return 0
    echo "📦 Ставлю библиотеку requests..."
    "$PY" -m pip install --user requests >/dev/null 2>&1 && return 0
    "$PY" -m pip install --user --break-system-packages requests >/dev/null 2>&1 && return 0
    echo "📦 Создаю отдельное окружение .venv..."
    "$PY" -m venv .venv >/dev/null 2>&1 || return 1
    PY="$PWD/.venv/bin/python"
    "$PY" -m pip install --upgrade pip >/dev/null 2>&1
    "$PY" -m pip install requests >/dev/null 2>&1
    "$PY" -c "import requests" >/dev/null 2>&1
}

if ! ensure_requests; then
    echo "❌ Не удалось поставить requests."
    alert "Не удалось установить библиотеку requests. Покажите это окно тому, кто настраивал скрипт."
    read -r -p "Нажмите Enter, чтобы закрыть окно..."
    exit 1
fi
echo "✅ requests на месте"


# ── 4. Запуск ──
echo "🚀 Запускаю окно «Field Checker»..."
echo
"$PY" field_checker_ui.py
STATUS=$?

if [ $STATUS -ne 0 ]; then
    echo
    echo "⛔ Программа завершилась с ошибкой (код $STATUS). Скопируйте текст выше."
    read -r -p "Нажмите Enter, чтобы закрыть окно..."
fi
