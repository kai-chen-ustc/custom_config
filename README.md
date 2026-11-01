# Custom Config

## Installation

Supports macOS (including Apple Silicon and the system Bash 3.2), Ubuntu,
and WSL distributions with Bash/Zsh. On WSL, run inside Linux, not PowerShell.

1. Install `git`, `curl`, and `zsh`. Vim and tmux are optional:
   - macOS: the system provides Git (Command Line Tools), curl, Zsh and Vim;
     install tmux with `brew install tmux` if desired.
   - Ubuntu / Ubuntu on WSL: `sudo apt update && sudo apt install git curl zsh vim tmux`.
2. Clone this repository into a permanent location and run:
   ```bash
   ./setup.sh
   ```
   Run as your normal user, **without sudo**. The script needs HTTPS access to
   GitHub and raw.githubusercontent.com; GitHub SSH keys are not required.
3. Run `exec zsh` or open a terminal configured to launch Zsh. The installer does
   not change your login shell; on Linux, optionally run `chsh -s "$(command -v zsh)"`
   and log in again to make Zsh the default.

## What it does

- Backs up existing `.zshrc`, `.vimrc`, `.tmux.conf`, and `.bash_aliases` before
  installation, preserving symlinks in a unique `~/.custom-config-backup-*`
  directory on every run.
- Installs Oh My Zsh if missing, preserving the existing `.zshrc`.
- Downloads `zsh-autosuggestions` and `zsh-syntax-highlighting` over HTTPS.
- Preserves personal `.zshrc` content while setting `ZSH`, `ZSH_CUSTOM`, and the
  managed plugin list; adds the Oh My Zsh source command if missing.
- Links Vim, tmux, and alias configuration to this repository. Keep the repository
  in place after installation. The `df` alias uses macOS or Linux options as needed.
- Stops on errors and prints the backup location. Download/validation failures
  occur before activating the new configuration; this is not a full rollback.

The legacy `config/.zshrc` is not used by the installer. Aliases are loaded through
Zsh/Oh My Zsh, not automatically by Bash. Optional commands referenced by custom
functions or tmux shortcuts (such as Conda, htop, ncmpcpp, and mysdcv) must be
installed separately if you use them.

To restore a backed-up file, remove its current replacement and copy the matching
file from the printed backup directory using `cp -Pp`. Files that did not exist
before setup will not appear in that backup directory.
