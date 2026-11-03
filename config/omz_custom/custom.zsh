#check if a binary exists in path
bin-exist() {[[ -n ${commands[$1]} ]]}

# Preserve the local SSH Host alias for tmux status/title formats.
ssh() {
    local ssh_alias ssh_status

    ssh_alias=$(command ssh -G "$@" 2>/dev/null | awk '$1 == "host" { print $2; exit }')
    if [[ -n "$TMUX_PANE" && -n "$ssh_alias" ]]; then
        tmux set-option -p -t "$TMUX_PANE" @ssh_alias "$ssh_alias"
    fi

    command ssh "$@"
    ssh_status=$?

    if [[ -n "$TMUX_PANE" ]]; then
        tmux set-option -pu -t "$TMUX_PANE" @ssh_alias 2>/dev/null
    fi
    return "$ssh_status"
}

# Keep agent setup and cleanup in a separate process.
# Remove the old alias when reloading an existing terminal.
unalias sshk 2>/dev/null
function sshk {
    "$ZSH_CUSTOM/../../bin/ssh-with-key" "$@"
}

_sshk() {
    local service=ssh
    local -a words=("${words[@]}")
    local CURRENT=$CURRENT
    if [[ ${words[3]} == --key ]] && (( CURRENT > 3 )); then
        if (( CURRENT == 4 )); then
            _files
            return
        fi
        words[3,4]=()
        (( CURRENT -= 2 ))
    fi
    words[1]=ssh
    if (( CURRENT == 3 )); then
        _alternative 'key:forwarded key option:((--key\:forwarded\ key))' 'ssh:SSH arguments:_ssh'
    else
        _ssh
    fi
}
(( $+functions[compdef] )) && compdef _sshk sshk

bindkey -e      #use emacs style keybindings

codex-whoami() {
    local auth_file="$HOME/.codex/auth.json"
    local login_status email name account_id

    if ! bin-exist codex; then
        echo "codex CLI not found in PATH"
        return 1
    fi

    login_status=$(codex login status 2>&1 || true)
    if [[ -z "$login_status" ]]; then
        login_status="Not logged in"
    fi

    if [[ -r "$auth_file" ]] && bin-exist node; then
        email=$(AUTH_FILE="$auth_file" node -e '
const fs = require("fs");
const auth = JSON.parse(fs.readFileSync(process.env.AUTH_FILE, "utf8"));
const token = auth?.tokens?.id_token;
if (!token) process.exit(0);
const [, payload] = token.split(".");
if (!payload) process.exit(0);
const claims = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
if (claims.email) process.stdout.write(claims.email);
' 2>/dev/null)

        name=$(AUTH_FILE="$auth_file" node -e '
const fs = require("fs");
const auth = JSON.parse(fs.readFileSync(process.env.AUTH_FILE, "utf8"));
const token = auth?.tokens?.id_token;
if (!token) process.exit(0);
const [, payload] = token.split(".");
if (!payload) process.exit(0);
const claims = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
if (claims.name) process.stdout.write(claims.name);
' 2>/dev/null)
    fi

    if [[ -r "$auth_file" ]]; then
        account_id=$(jq -r '.tokens.account_id // empty' "$auth_file" 2>/dev/null)
    fi

    echo "$login_status"
    [[ -n "$name" ]] && echo "Name: $name"
    [[ -n "$email" ]] && echo "Email: $email"
    [[ -n "$account_id" ]] && echo "Account ID: $account_id"
}

# The double ESC to prepend "sudo" functionality is now handled by the 'sudo' OMZ plugin.

export SUDO_PROMPT=$'[\e[31;5msudo\e[m] password for \e[33;1m%p\e[m: '

# Built-in history search key bindings
# Bind Ctrl+P and Ctrl+N to search history based on the current line as a prefix.
bindkey '^P' history-beginning-search-backward
bindkey '^N' history-beginning-search-forward

# Key bindings
# History search is handled by OMZ. For a better experience, 'zsh-autosuggestions' plugin is recommended.
# The following binding to edit the command in an external editor is kept as a personal preference.
autoload -U edit-command-line
zle -N edit-command-line
bindkey '\ee' edit-command-line

# Functions to change PWD color in prompt temporarily after a directory change.
# This provides a nice visual feedback. In nested remote tmux, it can cause issues.
if [[ -n "$TMUX" && -n "$SSH_CLIENT" ]]; then
    # Use a simpler, static RPROMPT for nested tmux over SSH to avoid display issues
    local prompt_time="%(?:$pfg_green:$pfg_red)%*$pR"
    RPROMPT='$pfg_magenta%~$pR $prompt_time'
else
    # Full-featured prompt for local sessions
    __PROMPT_PWD="$pfg_magenta%~$pR"
    pwd_color_chpwd() { [ $PWD = $OLDPWD ] || __PROMPT_PWD="$pU$pfg_cyan%~$pR" }
    pwd_color_preexec() { __PROMPT_PWD="$pfg_magenta%~$pR" }

    # Add custom functions to the hooks managed by Oh My Zsh.
    preexec_functions+=(pwd_color_preexec)
    chpwd_functions+=(pwd_color_chpwd)

    # Prompt configuration
    # The main prompt (PROMPT) is now managed by the selected OMZ theme.
    # We only override RPROMPT to keep the custom PWD color effect and the timestamp.
    local prompt_time="%(?:$pfg_green:$pfg_red)%*$pR"
    RPROMPT='$__PROMPT_PWD $prompt_time'
fi

# Syntax highlighting is now handled by the 'zsh-syntax-highlighting' plugin.

# Load bash aliases if they exist
if [ -f "$HOME/.bash_aliases" ]; then
    source "$HOME/.bash_aliases"
fi

# For WSL, no need to use this when NTP is up running
# sudo hwclock -s

__auto_conda_activate() {
    # If a .conda_config file exists in the current directory
    if [ -f ".conda_config" ]; then
        # Read the environment name from the file
        local env_name
        env_name=$(cat .conda_config)

        # Activate the environment if it's not already the active one
        if [[ "$CONDA_DEFAULT_ENV" != "$env_name" ]]; then
            conda activate "$env_name"
            # If activation is successful, store the path
            if [[ $? -eq 0 ]]; then
                export __CONDA_AUTO_ACTIVATED_DIR=$PWD
            fi
        # If the correct env is already active, ensure our tracking variable is set.
        # This handles cases where the shell is opened directly in the project directory.
        elif [[ "$CONDA_DEFAULT_ENV" == "$env_name" && -z "$__CONDA_AUTO_ACTIVATED_DIR" ]]; then
             export __CONDA_AUTO_ACTIVATED_DIR=$PWD
        fi
    # If no .conda_config, and an environment was auto-activated previously,
    # and we are no longer in that directory or its subdirectories...
    elif [[ -n "$__CONDA_AUTO_ACTIVATED_DIR" && "$PWD" != "$__CONDA_AUTO_ACTIVATED_DIR"* ]]; then
        # ...deactivate it and unset the tracking variable.
        conda deactivate
        unset __CONDA_AUTO_ACTIVATED_DIR
    fi
}

# For zsh, hook the function to run on every directory change.
if [[ -n "$ZSH_VERSION" ]]; then
    _add_conda_hook() {
      if ! (( ${+chpwd_functions} )) || [[ -z "${chpwd_functions[(r)__auto_conda_activate]}" ]]; then
          autoload -U add-zsh-hook
          add-zsh-hook chpwd __auto_conda_activate
      fi
    }
    _add_conda_hook
    unset -f _add_conda_hook

    # Initial run in case the shell starts inside a project directory.
    __auto_conda_activate
fi
# --- End Conda auto-activation script ---
