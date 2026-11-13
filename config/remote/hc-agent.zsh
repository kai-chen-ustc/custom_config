# >>> sshk hc agent forwarding >>>
# Source: custom_config/config/remote/hc-agent.zsh
# Setup and rollback: custom_config/docs/remote-config.md
# ssh-with-key --hc updates this link on each connection; no private key is stored here.
if [[ -n "$HC_TERMINAL_ID" && -L "$HOME/.ssh/hc-forwarded-agent.sock" ]]; then
    export SSH_AUTH_SOCK="$HOME/.ssh/hc-forwarded-agent.sock"
fi
# <<< sshk hc agent forwarding <<<
