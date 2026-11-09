# macOS applications and tools: brew bundle install --file=Brewfile
# Command-line tools; Homebrew resolves their dependencies.
brew "fnm"
brew "gh"
brew "git"
brew "jq"
brew "ripgrep"
brew "tmux"
brew "uv"

# Desktop apps (macOS only).
cask "chatgpt"
cask "clash-verge-rev"
cask "discord"
cask "docker-desktop"
cask "google-chrome"
cask "seafile-client"
# Package installers can replace apps even without --force.
cask "uuremote" unless File.exist?("/Applications/UURemote.app")
cask "wetype"

# Communication and notes.
cask "feishu"
cask "wechat"
cask "joplin"
cask "microsoft-teams" unless File.exist?("/Applications/Microsoft Teams.app")

# ego lite has no official Homebrew cask; install from https://ego.app/.
