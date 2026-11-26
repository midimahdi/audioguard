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

echo [3.5/4] Compiling native Windows WASAPI loopback audio tap...
if not exist "bin\win" mkdir "bin\win"
if exist "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" (
    "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /optimize+ /platform:anycpu /target:exe /out:"bin\win\audioguard-wasapi-tap.exe" "packaging\win\audioguard-wasapi-tap.cs"
    if errorlevel 1 (
        echo [WARNING] Failed to compile audioguard-wasapi-tap.exe; using prebuilt binary if present.
    )
)

echo [4/4] Bundling standalone Windows executable with PyInstaller...
pyinstaller --noconfirm --onedir --windowed --noupx ^
    --version-file "version_info.txt" ^
    --name "AudioGuard" ^
    --add-binary "bin\win\audioguard-wasapi-tap.exe;bin\win" ^
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
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'AudioGuard.lnk')); $s.TargetPath = [System.IO.Path]::GetFullPath('dist\\AudioGuard\\AudioGuard.exe'); $s.Description = 'AudioGuard Audio Backup System'; $s.Save()"

echo Shortcut created on Windows Desktop.
echo.
pause
