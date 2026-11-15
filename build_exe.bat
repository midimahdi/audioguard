@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo AudioGuard - Windows PyInstaller Standalone Build
echo =======================================================

echo [1/4] Checking Python environment...
python --version
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

echo [2/4] Installing required dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed!
    pause
    exit /b 1
)

echo [3/4] Running automated power-loss crash verification...
python verify_engine.py
if errorlevel 1 (
    echo [WARNING] Verification test had issues, check output above.
)

echo [4/4] Bundling standalone Windows executable with PyInstaller...
pyinstaller --noconfirm --onedir --windowed ^
    --name "AudioGuard" ^
    --collect-all "customtkinter" ^
    --collect-all "sounddevice" ^
    --collect-all "soundfile" ^
    --collect-all "pystray" ^
    --collect-all "PIL" ^
    main.py

if errorlevel 1 (
    echo [ERROR] PyInstaller packaging failed!
    pause
    exit /b 1
)

echo.
echo =======================================================
echo [SUCCESS] Build completed!
echo Binary output located at: dist\AudioGuard\AudioGuard.exe
echo =======================================================

rem Create Desktop Shortcut via PowerShell
echo Creating Windows Desktop Shortcut...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'MosqueAudioGuard.lnk')); $s.TargetPath = [System.IO.Path]::GetFullPath('dist\\MosqueAudioGuard\\MosqueAudioGuard.exe'); $s.Description = 'Mosque Audio Guard Backup System'; $s.Save()"

echo Shortcut created on Windows Desktop.
echo.
pause
