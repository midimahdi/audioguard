$WshShell = New-Object -comObject WScript.Shell
$TargetPath = "C:\AudioGuard\dist\AudioGuard\AudioGuard.exe"
$WorkingDir = "C:\AudioGuard\dist\AudioGuard"
$Description = "AudioGuard - Lossless Audio Backup System"

# 1. Start Menu (Current User)
$StartMenuUser = [System.IO.Path]::Combine($env:APPDATA, "Microsoft\Windows\Start Menu\Programs", "AudioGuard.lnk")
$s1 = $WshShell.CreateShortcut($StartMenuUser)
$s1.TargetPath = $TargetPath
$s1.WorkingDirectory = $WorkingDir
$s1.Description = $Description
$s1.Save()
Write-Host "Created User Start Menu shortcut: $StartMenuUser"

# 2. Start Menu (All Users / ProgramData)
$StartMenuCommon = [System.IO.Path]::Combine($env:ProgramData, "Microsoft\Windows\Start Menu\Programs", "AudioGuard.lnk")
try {
    $s2 = $WshShell.CreateShortcut($StartMenuCommon)
    $s2.TargetPath = $TargetPath
    $s2.WorkingDirectory = $WorkingDir
    $s2.Description = $Description
    $s2.Save()
    Write-Host "Created Common Start Menu shortcut: $StartMenuCommon"
} catch {
    Write-Host "Skipped common start menu: $_"
}

# 3. Desktop (Public Desktop)
$DesktopPublic = "C:\Users\Public\Desktop\AudioGuard.lnk"
try {
    $s3 = $WshShell.CreateShortcut($DesktopPublic)
    $s3.TargetPath = $TargetPath
    $s3.WorkingDirectory = $WorkingDir
    $s3.Description = $Description
    $s3.Save()
    Write-Host "Created Public Desktop shortcut: $DesktopPublic"
} catch {
    Write-Host "Skipped public desktop: $_"
}

# 4. User Desktop (OneDrive or Local)
$UserDesktop = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop", "AudioGuard.lnk")
try {
    $s4 = $WshShell.CreateShortcut($UserDesktop)
    $s4.TargetPath = $TargetPath
    $s4.WorkingDirectory = $WorkingDir
    $s4.Description = $Description
    $s4.Save()
    Write-Host "Created User Desktop shortcut: $UserDesktop"
} catch {}

$UserODDesktop = [System.IO.Path]::Combine($env:USERPROFILE, "OneDrive\Desktop", "AudioGuard.lnk")
try {
    $s5 = $WshShell.CreateShortcut($UserODDesktop)
    $s5.TargetPath = $TargetPath
    $s5.WorkingDirectory = $WorkingDir
    $s5.Description = $Description
    $s5.Save()
    Write-Host "Created OneDrive Desktop shortcut: $UserODDesktop"
} catch {}

Write-Host "ALL_SHORTCUTS_OK"
