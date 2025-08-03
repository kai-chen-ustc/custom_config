# Custom Config

## Installation

1.  Clone this repository to your local machine.
2.  Run the setup script:
    ```bash
    ./setup.sh
    ```
3.  Restart your terminal or run `source ~/.zshrc` to apply the changes. Enjoy!

## What it does

The `setup.sh` script will automatically:
- Install Oh My Zsh if it's not already installed.
- Create backups of your existing dotfiles (`.zshrc`, `.vimrc`, `.tmux.conf`).
- Create symbolic links for `.vimrc`, `.tmux.conf`, and `.bash_aliases`.
- Configure `~/.zshrc` to use the custom plugins and settings from this repository.
- Install `zsh-autosuggestions` and `zsh-syntax-highlighting` plugins.
