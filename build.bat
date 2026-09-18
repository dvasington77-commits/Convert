@echo off
chcp 65001 >nul
echo ====================================
echo   Сборка cd_envelope.exe
echo ====================================
echo.

echo [1/3] Устанавливаю зависимости...
pip install -r requirements.txt
if errorlevel 1 (
    echo ОШИБКА: не удалось установить зависимости
    pause
    exit /b 1
)

echo.
echo [2/3] Чищу старые сборки...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist cd_envelope.spec del cd_envelope.spec

echo.
echo [3/3] Собираю .exe...
if exist icon.ico (
    pyinstaller --onefile --noconsole --name cd_envelope --icon=icon.ico cd_envelope.py
) else (
    pyinstaller --onefile --noconsole --name cd_envelope cd_envelope.py
)

if errorlevel 1 (
    echo ОШИБКА: не удалось собрать .exe
    pause
    exit /b 1
)

echo.
echo ====================================
echo   ГОТОВО!
echo   Файл: dist\cd_envelope.exe
echo ====================================
echo.
pause
