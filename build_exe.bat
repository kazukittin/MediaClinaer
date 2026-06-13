@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto :error
)

set "PYTHON=.venv\Scripts\python.exe"

"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :error

"%PYTHON%" -m pip install -e .[build]
if errorlevel 1 goto :error

if exist "build" rmdir /s /q "build"
if exist "dist\MediaClinaer" rmdir /s /q "dist\MediaClinaer"

"%PYTHON%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --name MediaClinaer ^
    --paths src ^
    src\media_clinaer\main.py
if errorlevel 1 goto :error

echo.
echo Build completed:
echo dist\MediaClinaer\MediaClinaer.exe
echo.
pause
exit /b 0

:error
echo.
echo Build failed.
echo.
pause
exit /b 1
