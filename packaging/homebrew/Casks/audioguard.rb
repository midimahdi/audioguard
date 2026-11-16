cask "audioguard" do
  arch arm: "AppleSilicon", intel: "Intel"

  version "1.5.5"
  sha256 arm:   "f9e4c8a9a4e54d1777c75c5dd624e74e31598b8dac79fd8cb60290f36c4d18d1",
         intel: "836fccc1d65ee781d167906c67ed83f69e690e7a3ecebff3bcb5a62d91ebd8e7"

  url "https://github.com/midimahdi/audioguard/releases/download/v#{version}/AudioGuard-macOS-#{arch}.dmg"
  name "AudioGuard"
  desc "Automatic lossless audio backup appliance that survives sudden power cuts"
  homepage "https://github.com/midimahdi/audioguard"

  livecheck do
    url :url
    strategy :github_latest
  end

  app "AudioGuard.app"

  zap trash: [
    "~/.audioguard",
    "~/Library/Saved Application State/com.mahdi.audioguard.savedState",
  ]
end
