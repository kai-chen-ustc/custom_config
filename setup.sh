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

# Create symbolic links for .vimrc and .tmux.conf
ln -sf "$REPO_DIR/config/.vimrc" "$HOME/.vimrc"
ln -sf "$REPO_DIR/config/.tmux.conf" "$HOME/.tmux.conf"

# Replace the ZSH_CUSTOM line with the correct path
ZSHRC="$REPO_DIR/config/.zshrc"
ZSH_CUSTOM_LINE="ZSH_CUSTOM=$REPO_DIR/config"
sed -i "/^ZSH_CUSTOM=/c\\$ZSH_CUSTOM_LINE" "$ZSHRC" || echo "$ZSH_CUSTOM_LINE" >> "$ZSHRC"

# Create a symbolic link for .zshrc
ln -sf "$ZSHRC" "$HOME/.zshrc"

# Ignore changes in .zshrc in the future
git update-index --assume-unchanged "config/.zshrc"

echo "Setup completed successfully."
