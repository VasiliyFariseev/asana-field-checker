@echo off
chcp 65001 >nul 2>&1
title Field Checker
cd /d "%~dp0"

echo ----------------------------------------------
echo   Field Checker - checking environment
echo ----------------------------------------------

REM ---- 1. Find Python 3 ----
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo.
    echo [X] Python 3 not found / Python 3 ne naiden.
    echo     Install Python 3 from python.org, tick "Add python.exe to PATH",
    echo     then run this file again.
    start "" "https://www.python.org/downloads/windows/"
    pause
    exit /b 1
)

%PY% -V
if errorlevel 1 (
    echo [X] Python is broken. Reinstall from python.org.
    pause
    exit /b 1
)

REM ---- 2. tkinter (GUI) ----
%PY% -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [X] tkinter is missing. Reinstall Python from python.org
    echo     and keep the "tcl/tk and IDLE" option checked.
    start "" "https://www.python.org/downloads/windows/"
    pause
    exit /b 1
)
echo [OK] tkinter

REM ---- 4. Run ----
echo [..] Starting Field Checker...
echo.
%PY% field_checker_ui.py
if errorlevel 1 (
    echo.
    echo [X] Exited with an error. Copy the text above.
    pause
)
