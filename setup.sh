#!/bin/bash

# Get the directory of the script
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
REPO_DIR="$SCRIPT_DIR"

# --- Function to backup files ---
backup_file() {
    if [ -e "$1" ] && [ ! -L "$1" ]; then
        echo "Backing up $1 to $1.bak"
        cp -L "$1" "$1.bak"
    fi
}

# --- Install Oh My Zsh ---
if [ ! -d "$HOME/.oh-my-zsh" ]; then
    echo "Installing Oh My Zsh..."
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
else
    echo "Oh My Zsh is already installed."
fi

# --- Configure .zshrc ---
ZSHRC_FILE="$HOME/.zshrc"

# Check if .zshrc exists, if not, create it from the template
if [ ! -f "$ZSHRC_FILE" ]; then
    echo "Creating .zshrc from template..."
    cp "$HOME/.oh-my-zsh/templates/zshrc.zsh-template" "$ZSHRC_FILE"
fi

# --- Backup existing dotfiles ---
backup_file "$HOME/.vimrc"
backup_file "$HOME/.tmux.conf"
backup_file "$HOME/.bash_aliases"
backup_file "$ZSHRC_FILE"


# --- Create symbolic links for vim, tmux, and bash ---
echo "Creating symbolic links for vim, tmux, and bash..."
ln -sf "$REPO_DIR/config/vimrc" "$HOME/.vimrc"
ln -sf "$REPO_DIR/config/tmux.conf" "$HOME/.tmux.conf"
ln -sf "$REPO_DIR/config/bash_aliases" "$HOME/.bash_aliases"


# --- Configure .zshrc content ---
ZSH_CUSTOM_DIR="$REPO_DIR/config/omz_custom"
CUSTOM_PLUGINS_DIR="$ZSH_CUSTOM_DIR/plugins"

echo "Configuring .zshrc..."

# 1. Set ZSH_CUSTOM path
ZSH_CUSTOM_LINE="export ZSH_CUSTOM=\"$ZSH_CUSTOM_DIR\""
if ! grep -q "export ZSH_CUSTOM=" "$ZSHRC_FILE"; then
    # Insert the line after the ZSH installation path export
    sed -i "/^export ZSH=.*$/a $ZSH_CUSTOM_LINE" "$ZSHRC_FILE"
else
    sed -i "s|export ZSH_CUSTOM=.*|$ZSH_CUSTOM_LINE|" "$ZSHRC_FILE"
fi

# 2. Set plugins
PLUGINS_LINE="plugins=(git bazel sudo zsh-syntax-highlighting zsh-autosuggestions)"
if ! grep -q "^plugins=" "$ZSHRC_FILE"; then
    echo "$PLUGINS_LINE" >> "$ZSHRC_FILE"
else
    sed -i "/^plugins=/c\\$PLUGINS_LINE" "$ZSHRC_FILE"
fi


# --- Install custom plugins for Oh My Zsh ---
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

echo "Setup completed successfully."
echo "Please restart your shell or run 'source ~/.zshrc' to apply the changes."
