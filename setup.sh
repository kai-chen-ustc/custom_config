#!/bin/bash

# Automatically get the directory from which the script is run
REPO_DIR=$(pwd)

# Define the location of the files in the home directory
VIMRC="$HOME/.vimrc"
TMUX_CONF="$HOME/.tmux.conf"

# Backup .vimrc if it exists
if [ -f "$VIMRC" ]; then
    echo "Backing up .vimrc to .vimrc.bak"
    cp "$VIMRC" "${VIMRC}.bak"
fi

# Backup .tmux.conf if it exists
if [ -f "$TMUX_CONF" ]; then
    echo "Backing up .tmux.conf to .tmux.conf.bak"
    cp "$TMUX_CONF" "${TMUX_CONF}.bak"
fi

# Backup .zshrc if it exists
if [ -f "$HOME/.zshrc" ]; then
    echo "Backing up .zshrc to .zshrc.bak"
    cp "$HOME/.zshrc" "$HOME/.zshrc.bak"
fi

# Backup .bash_aliases if it exists
if [ -f "$HOME/.bash_aliases" ]; then
    echo "Backing up .bash_aliases to .bash_aliases.bak"
    cp "$HOME/.bash_aliases" "$HOME/.bash_aliases.bak"
fi

# Create symbolic links for .vimrc and .tmux.conf
ln -sf "$REPO_DIR/config/.vimrc" "$HOME/.vimrc"
ln -sf "$REPO_DIR/config/.tmux.conf" "$HOME/.tmux.conf"
ln -sf "$REPO_DIR/config/.bash_aliases" "$HOME/.bash_aliases"

# User defined custom config folder
ZSH_CUSTOM_DIR="$REPO_DIR/config"
CUSTOM_PLUGINS_DIR="$ZSH_CUSTOM_DIR/plugins"

# Install custom plugins for Oh My Zsh into the repository's custom folder
echo "Installing custom zsh plugins into $CUSTOM_PLUGINS_DIR..."
mkdir -p "$CUSTOM_PLUGINS_DIR"

# Install zsh-autosuggestions
if [ ! -d "$CUSTOM_PLUGINS_DIR/zsh-autosuggestions" ]; then
    git clone https://github.com/zsh-users/zsh-autosuggestions "$CUSTOM_PLUGINS_DIR/zsh-autosuggestions"
else
    echo "zsh-autosuggestions is already installed."
fi
# Install zsh-syntax-highlighting
if [ ! -d "$CUSTOM_PLUGINS_DIR/zsh-syntax-highlighting" ]; then
    git clone https://github.com/zsh-users/zsh-syntax-highlighting.git "$CUSTOM_PLUGINS_DIR/zsh-syntax-highlighting"
else
    echo "zsh-syntax-highlighting is already installed."
fi

# Define the plugins list and the line to be written to .zshrc
PLUGINS_LINE="plugins=(git bazel sudo zsh-syntax-highlighting zsh-autosuggestions)"

# Replace the plugins line in .zshrc
sed -i "/^plugins=/c\\$PLUGINS_LINE" "$ZSHRC"

# Replace the ZSH_CUSTOM line with the correct path
ZSH_CUSTOM_LINE="ZSH_CUSTOM=\"$ZSH_CUSTOM_DIR\""
# Use a different separator for sed to handle paths with slashes gracefully
sed -i "\:^ZSH_CUSTOM=:c\\$ZSH_CUSTOM_LINE" "$ZSHRC" || echo "$ZSH_CUSTOM_LINE" >> "$ZSHRC"

# Create a symbolic link for .zshrc
ln -sf "$ZSHRC" "$HOME/.zshrc"

# Ignore changes in .zshrc in the future
git update-index --assume-unchanged "config/.zshrc"

echo "Setup completed successfully."
