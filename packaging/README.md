# AudioGuard Packaging & Ecosystem Distribution

This directory contains package manifests for official package managers.

---

## 1. Windows Package Manager (`winget`)

### Option A: Using `wingetcreate` CLI (Automated PR)
Run from any Windows terminal (or CI):
```powershell
wingetcreate submit https://github.com/midimahdi/audioguard/releases/download/v1.5.5/AudioGuard-Setup-x64.exe
```

### Option B: Manual PR to `microsoft/winget-pkgs`
1. Fork [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs).
2. Copy files from `packaging/winget/` to:
   `manifests/m/MahdiDigital/AudioGuard/1.5.5/`
3. Commit and submit pull request.

---

## 2. macOS Homebrew Tap (`brew`)

To distribute via a custom tap (`midimahdi/homebrew-tap`):
1. Create a repository on GitHub named `homebrew-tap` under `midimahdi`.
2. Place `Casks/audioguard.rb` in that repository.
3. Users can then install via:
   ```bash
   brew install --cask midimahdi/tap/audioguard
   ```
