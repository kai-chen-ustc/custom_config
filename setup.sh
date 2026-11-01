#!/bin/bash
set -euo pipefail

REPO_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ZSHRC_FILE="$HOME/.zshrc"
ZSH_CUSTOM_DIR="$REPO_DIR/config/omz_custom"
CUSTOM_PLUGINS_DIR="$ZSH_CUSTOM_DIR/plugins"

for dependency in zsh git curl awk; do
    command -v "$dependency" >/dev/null || {
        echo "Required command not found: $dependency" >&2
        exit 1
    }
done
for name in .zshrc .vimrc .tmux.conf .bash_aliases; do
    if [ -d "$HOME/$name" ]; then
        echo "Refusing to replace directory: $HOME/$name" >&2
        exit 1
    fi
done

# Back up original files BEFORE the Oh My Zsh installer can change anything.
# Each run has its own directory; preserve symlinks, including broken links.
BACKUP_DIR=$(mktemp -d "$HOME/.custom-config-backup-$(date +%Y%m%d-%H%M%S).XXXXXX")
chmod 700 "$BACKUP_DIR"
for name in .zshrc .vimrc .tmux.conf .bash_aliases; do
    if [ -e "$HOME/$name" ] || [ -L "$HOME/$name" ]; then
        cp -Pp "$HOME/$name" "$BACKUP_DIR/$name"
    fi
done
echo "Original dotfiles backed up to: $BACKUP_DIR"
WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/custom-config.XXXXXX")
trap 'rm -rf "$WORK_DIR"' EXIT
trap 'echo "Setup failed. Original dotfiles are in: $BACKUP_DIR" >&2' ERR

if [ ! -f "$HOME/.oh-my-zsh/oh-my-zsh.sh" ]; then
    # Download separately so a failed curl cannot be mistaken for success.
    curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh \
        -o "$WORK_DIR/install-omz.sh"
    ZSH="$HOME/.oh-my-zsh" KEEP_ZSHRC=yes CHSH=no RUNZSH=no \
        sh "$WORK_DIR/install-omz.sh" --unattended
fi
[ -f "$HOME/.oh-my-zsh/oh-my-zsh.sh" ]

mkdir -p "$CUSTOM_PLUGINS_DIR"
for plugin in zsh-autosuggestions zsh-syntax-highlighting; do
    if [ ! -e "$CUSTOM_PLUGINS_DIR/$plugin" ]; then
        git clone --depth 1 "https://github.com/zsh-users/$plugin.git" "$WORK_DIR/$plugin"
        mv "$WORK_DIR/$plugin" "$CUSTOM_PLUGINS_DIR/$plugin"
    fi
    [ -f "$CUSTOM_PLUGINS_DIR/$plugin/$plugin.plugin.zsh" ]
done

# Preserve personal settings, replacing only the settings managed here.
# awk avoids GNU/BSD sed -i differences. Multiline plugin arrays are supported.
ZSHRC_INPUT="$ZSHRC_FILE"
if [ ! -f "$ZSHRC_INPUT" ]; then
    ZSHRC_INPUT="$HOME/.oh-my-zsh/templates/zshrc.zsh-template"
fi
{
    printf 'export ZSH=%q\n' "$HOME/.oh-my-zsh"
    printf 'export ZSH_CUSTOM=%q\n' "$ZSH_CUSTOM_DIR"
    printf '%s\n' 'plugins=(git bazel sudo zsh-autosuggestions zsh-syntax-highlighting)'
    awk '
        /^[[:space:]]*(export[[:space:]]+)?(ZSH|ZSH_CUSTOM)=/ { next }
        /^[[:space:]]*plugins=\(/ {
            if ($0 !~ /\)/) in_plugins = 1
            next
        }
        in_plugins { if ($0 ~ /\)/) in_plugins = 0; next }
        { print }
        END { if (in_plugins) exit 1 }
    ' "$ZSHRC_INPUT"
    if ! grep -Eq '^[[:space:]]*(source|\.)[[:space:]].*oh-my-zsh\.sh' "$ZSHRC_INPUT"; then
        printf '\n%s\n' 'ZSH_THEME="${ZSH_THEME:-robbyrussell}"' 'source "$ZSH/oh-my-zsh.sh"'
    fi
} > "$WORK_DIR/zshrc"
zsh -n "$WORK_DIR/zshrc"

# Only activate the configuration once downloads and syntax validation succeed.
# Remove symlinks explicitly so a linked target is not overwritten.
rm -f "$ZSHRC_FILE"
cp "$WORK_DIR/zshrc" "$ZSHRC_FILE"
chmod 600 "$ZSHRC_FILE"
for pair in '.vimrc:vimrc' '.tmux.conf:tmux.conf' '.bash_aliases:bash_aliases'; do
    destination=${pair%%:*}
    source_file=${pair#*:}
    rm -f "$HOME/$destination"
    ln -s "$REPO_DIR/config/$source_file" "$HOME/$destination"
done

echo "Setup completed successfully. Backups: $BACKUP_DIR"
echo "Restart your terminal or run: exec zsh"
