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

Aliases are loaded through
Zsh/Oh My Zsh, not automatically by Bash. Optional commands referenced by custom
functions or tmux shortcuts (such as Conda, htop, ncmpcpp, and mysdcv) must be
installed separately if you use them.

To restore a backed-up file, remove its current replacement and copy the matching
file from the printed backup directory using `cp -Pp`. Files that did not exist
before setup will not appear in that backup directory.

## SSH with a temporary agent

After pulling this update, open a new Zsh terminal or run `source ~/.zshrc`.
No setup rerun is needed for an existing installation. Later changes to the
script take effect on the next invocation, without reloading Zsh.

```sh
sshk dev-server
sshk --key ~/.ssh/work_key dev-server
sshk dev-server --key ~/.ssh/work_key -L 8080:localhost:8080
sshk dev-server --key ~/.ssh/work_key git -C project pull
```

Put `--key path` before or immediately after the host, before SSH options or
the remote command. `sshk --<Tab>` lists wrapper options. `--key` selects the key loaded into the temporary agent; SSH's `-i`
selects a login identity. Key selection uses this priority:

1. Explicit `--key path`.
2. `GIT_KEY_PATH` from your environment.
3. The first readable file among `~/.ssh/id_ed25519`, then `~/.ssh/id_rsa`.

If neither standard file exists, the command asks you to specify a key. It does
not scan custom filenames or fall back when an explicitly selected key is invalid.
The selected path is printed before loading the key.
Set your own default for a terminal with `export GIT_KEY_PATH="$HOME/.ssh/work_key"`,
or put that export in your personal `~/.zshrc`. An explicit `--key` takes priority.
Use `sshk --help` for usage. `sshk <Tab>` lists SSH config hosts in a selection
menu. `sshk --key <Tab>` (or `sshk host --key <Tab>`) lists private keys in `~/.ssh`, identified by their
key header; public keys and config files are excluded. Selecting a key inserts
its full path. Type a path such as `./` or `~/` to browse another directory.
SSH options also support Tab completion. The `sshk` shell function launches
the standalone script, so its agent environment stays separate from your shell.

The POSIX shell script works with OpenSSH on Ubuntu and macOS, including
passphrase-protected keys (ssh-add prompts locally). Ubuntu needs `openssh-client`;
macOS includes OpenSSH. No Python is required to use the script. Outside Zsh,
run `bin/ssh-with-key` directly.

Each invocation starts its own agent, loads the selected key and explicitly
requests agent forwarding. It forces SSH to use this agent, disables automatic
loading of login keys into it, and disables connection sharing. The private key is never copied to the remote host.
OpenSSH manages the agent lifetime through `ssh-agent command`: it exits
automatically after SSH ends or key loading fails. This uses a periodic check,
so the local agent may remain for about 10 seconds after the forwarding connection
has closed. Use foreground SSH
sessions: backgrounding (`-f`) can outlive the temporary agent. Forced termination with SIGKILL cannot restore the tmux label.
Only forward to trusted hosts: during the connection, a compromised remote host
can use the forwarded agent to authenticate. The server must allow forwarding;
run `ssh-add -l` on the remote host to verify the expected key fingerprint.
Tmux panes retain the target host label while the SSH connection is active.

Run the local checks with Python 3 (no remote connections or private keys used):

```sh
python3 -m unittest discover -s tests -v
```
