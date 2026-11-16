cask "audioguard" do
  arch arm: "AppleSilicon", intel: "Intel"

  version "1.5.5"
  sha256 arm:   "4639d5aea20309b262f7c527c6fa02c668db2b76689c9d18d19dd3f7af2c7cc3",
         intel: "6bc0884a013abf0e64fe19bd30ca521a6d4ae4a4282f1f1ae688fb2f263ae9be"

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
