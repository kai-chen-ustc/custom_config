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
   On macOS, after terminal setup finishes, you can optionally restore the
   applications and tools in `Brewfile` with the two confirmations described below.
   The final optional step on every platform offers shared SSH configuration;
   Enter skips it. No shared directory is required for terminal setup.
3. Run `exec zsh` or open a terminal configured to launch Zsh. The installer does
   not change your login shell; on Linux, optionally run `chsh -s "$(command -v zsh)"`
   and log in again to make Zsh the default.

## Restore applications on a new Mac

After cloning this repository on a Mac, run `./setup.sh` as your normal user.
It installs the terminal configuration first, then offers to restore the apps
and tools in the root `Brewfile`:

1. Answer `y` to the restore question (Enter skips).
2. Review the displayed Brewfile and installation reminder, then type `INSTALL`
   to confirm (anything else skips).

Only an interactive macOS run shows these prompts. Ubuntu, WSL and redirected
stdin skip application restoration. The choice is offered on each interactive
macOS run, so you can decline initially and run setup again later.

After both confirmations, setup uses your existing Homebrew or downloads and
runs the [official Homebrew installer](https://brew.sh/) if it is missing.
For a new Homebrew installation, follow its printed `brew shellenv` instructions
to make `brew` available in future terminals; setup configures its own process.
It then runs `bash bin/restore-apps`, which installs the complete Brewfile with
`brew bundle install --no-upgrade`. The list contains 12 desktop apps and seven
command-line tools; dependencies are resolved by brew.

The restore script reports and skips existing desktop apps that Homebrew does
not manage. It checks known app names in `/Applications`, `~/Applications`,
and the system/user `Library/Input Methods` directories (for WeType).
Skipped apps stay under their existing update mechanism; they are not adopted
by Homebrew. Detection does not verify app versions or health, and renamed apps
or custom installation locations may still cause conflicts.

Already-managed packages remain in the installation request and are not explicitly
upgraded (dependency installation can still require updates). No `--force` option
is used. The Brewfile always keeps every entry, so listing and cleanup do not
change based on which apps happen to exist. The skip list applies only to the
restore command and preserves any existing `HOMEBREW_BUNDLE_CASK_SKIP` setting.
Some installers need
administrator authentication or first-launch setup, so this is one command,
not unattended migration. Logins and application data are not restored.
If application restoration fails, terminal setup remains installed; inspect the
error and retry the application step without rerunning terminal setup:

```sh
bash bin/restore-apps
```

This direct command requires Homebrew on PATH and bypasses setup's two confirmations.
Running `brew bundle install` directly bypasses the manual-app protection.
`brew bundle check` still reports skipped, unmanaged apps as missing from Homebrew. This application list is
macOS-only; `setup.sh` remains usable on macOS, Ubuntu, and WSL.

| Application | Homebrew cask |
| --- | --- |
| ChatGPT desktop | `chatgpt` |
| Clash Verge Rev | `clash-verge-rev` |
| Discord | `discord` |
| Docker Desktop | `docker-desktop` |
| Google Chrome | `google-chrome` |
| Seafile Client | `seafile-client` |
| UU Remote / UU 远程助手 | `uuremote` |
| WeChat Input / 微信输入法 | `wetype` |
| Feishu / 飞书 | `feishu` |
| WeChat / 微信 | `wechat` |
| Joplin | `joplin` |
| Microsoft Teams | `microsoft-teams` |
| ego lite | Install manually from [ego.app](https://ego.app/) |

Safari and other macOS system apps are excluded. The official cask index has no
ego lite entry; its upstream
[packaging request](https://github.com/citrolabs/ego-lite/issues/58) remains open.

On the existing Mac, listing a manually installed app here does not register it
with Homebrew. `brew install --cask --adopt NAME` can adopt an existing app only
when its contents match the downloaded package. A mismatch needs a separately
planned replacement; do not force-replace running apps just to register them.

Application logins, browser profiles, WeChat history, Seafile sync configuration,
Joplin notes, Docker images/volumes, input-method activation, macOS privacy
permissions, and `~/Library/KeyBindings/DefaultKeyBinding.dict` are not backed up
by Brewfile. Migrate or sync these separately. Keep the Brewfile in your repository
backup; this file alone is not a backup of application data.

Use `brew bundle list --all --file=Brewfile` to inspect the list, and
`brew bundle check --no-upgrade --file=Brewfile` to check installation status.
Most of these apps update themselves. `brew upgrade --cask --greedy` also includes
self-updating casks when checking for upgrades; review available updates before
running it. Avoid `brew bundle cleanup` unless you intend to remove packages
outside this list.

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

## Shared SSH configuration (optional)

At the end of an interactive `./setup.sh`, answer the final question
`是否配置共享 SSH 配置？[y/N]` to opt in. Non-interactive setup skips this step.
The helper looks for `config/ssh/hosts.conf` under `~/Seafile/server-sync`,
`~/server-sync`, `~/projects/server-sync`, and `~/Projects/server-sync`.
It confirms one candidate, asks you to choose among multiple candidates, or lets
you enter a path or skip. It never creates a sync library or writes to the source.
The file can live anywhere; Seafile is just one common location.

Prepare your shared file explicitly, using only portable host settings, for example:

```sshconfig
Host dev-server
    HostName example.com
    User example-user
    IdentityFile ~/.ssh/example_key
    IdentitiesOnly yes
```

For machines already set up, use the independent commands:

```sh
bin/setup-ssh install --source /absolute/path/to/hosts.conf
bin/setup-ssh status
bin/setup-ssh status --source /absolute/path/to/hosts.conf
# Explicitly back up and replace conflicting files, or refresh a copied configuration:
bin/setup-ssh replace --source /absolute/path/to/hosts.conf
```

`install` creates `~/.ssh/config` as an Include entry point and
`~/.ssh/config.shared` as a link to the source. An optional `~/.ssh/config.local`
is read first and is never created, merged, or replaced. Put machine-specific
Keychain, agent socket, and proxy settings there. Most SSH options use the first
value found; `IdentityFile` entries accumulate, so avoid conflicting identity
declarations across the local and shared files. Each device supplies its own local
keys; this feature never copies keys, `known_hosts`, or `authorized_keys`.

Keep account-specific GitHub aliases (for example, `github-work` and
`github-personal`) in the shared file. Choose the default account for
`git@github.com:...` separately on each machine in `~/.ssh/config.local`:

```sshconfig
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/example_work_key
    IdentitiesOnly yes
```

Remove the corresponding `Host github.com` identity block from the shared file;
adding a local identity does not override a shared `IdentityFile`, because those
entries accumulate. Each new machine must prepare its own keys and default-account
block; setup does not select an account automatically. Without that local block,
SSH falls back to its usual key selection, which may authenticate a different
account. Use an explicit account alias until the local default is configured.

An exact existing entry and matching shared link/copy are a no-op on repeat runs.
Other existing files, modified entries, different/broken links, and directories
stop default installation. Directories and a symlinked `~/.ssh` are never replaced,
even with `replace`. Keep the source outside `~/.ssh` and pass the actual source
file, not a symlink to it. Source availability and hostname resolution remain
requirements for using the configured hosts.
Home directories with spaces are supported. A physical SSH configuration directory
containing `*`, `?`, `[` or `]` is rejected before changes, because OpenSSH expands
Include paths as glob patterns even when quoted. These characters may still appear
in the shared source's path, which is reached through the installed link or copy.
For the generated entry, the common host completer used by `ssh`, `scp`, and
`sshk` reads `config.local` and `config.shared` directly to work around macOS
Zsh's quoted-Include parsing. Explicit `-F` configuration files retain native completion.

`replace` validates the new Include configuration with `ssh -G`, then backs up
affected files to a unique `~/.ssh-config-backup-*` directory before activation.
Backups preserve original symlinks and also snapshot readable regular-file targets.
A failed activation restores the affected files; existing `config.local` stays intact.
An ordinary SSH configuration is not automatically imported into the shared source
or into `config.local`: prepare those files before explicitly replacing the entry.
Both successful SSH installation and skipping preserve the earlier terminal setup;
a selected SSH step that fails reports a nonzero exit without undoing terminal setup.

On macOS and Linux filesystems, link mode makes shared edits available immediately.
On WSL, a source under `/mnt/<drive>/...` defaults to copy mode, so the installed
file has Linux permissions. `--mode link|copy` overrides the default.
Copy mode is a snapshot: refresh with `replace`; `status --source ...` compares
against the source, while plain `status` checks only the installed copy.
There is no background sync job or installation database. Configuration checks
parse SSH settings; they do not test logins or guarantee every conditional block.
If an interrupted operation leaves `~/.ssh/.setup-ssh.lock`, ensure no installer is
running, inspect any backup and target files, then remove the empty lock directory
before retrying. Power loss and SIGKILL cannot trigger automatic rollback.

## SSH with a temporary agent

Open a new Zsh terminal or run `source ~/.zshrc` to load the `sshk` function
and completion. Script changes take effect on the next invocation.

```sh
sshk dev-server
sshk --key ~/.ssh/work_key dev-server
sshk -p 2222 --key ~/.ssh/work_key dev-server
sshk dev-server -p 2222 --key ~/.ssh/work_key
sshk dev-server --key ~/.ssh/work_key -L 8080:localhost:8080
sshk dev-server --key ~/.ssh/work_key git -C project pull
```

SSH options and `--key path` may appear before or after the host, in any order,
before the remote command. Attached options such as `-p2222` and grouped options
such as `-vp 2222` also work. Once the remote command starts, its arguments are
passed through unchanged, including `--key`. Use `--` to end wrapper option parsing.
`sshk --<Tab>` lists wrapper options. `--key` selects the key loaded into the temporary agent; SSH's `-i`
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

The script uses Bash 3.2 or newer (including macOS system Bash) and OpenSSH on
Ubuntu and macOS. It supports passphrase-protected keys (ssh-add prompts locally).
Ubuntu needs `openssh-client`;
macOS includes OpenSSH. No Python is required to use the script. Outside Zsh,
run `bin/ssh-with-key` directly.

Each invocation starts its own agent, loads the selected key and explicitly
requests agent forwarding. It fixes both the login and forwarded agent sockets
to this agent, overriding `IdentityAgent` and `ForwardAgent` in SSH config.
It disables automatic loading of login keys into the agent and connection sharing.
The private key is never copied to the remote host.
OpenSSH manages the agent lifetime through `ssh-agent command`: it exits
automatically after SSH ends or key loading fails. This uses a periodic check,
so the local agent may remain for about 10 seconds after the forwarding connection
has closed. Use foreground SSH
sessions: backgrounding (`-f`) can outlive the temporary agent. Forced termination with SIGKILL cannot restore the tmux label.
Only forward to trusted hosts: during the connection, a compromised remote host
can use the forwarded agent to authenticate. The server must allow forwarding;
run `ssh-add -l` on the remote host to verify the expected key fingerprint.

Setup, verification, and rollback are documented in
[Remote configuration](docs/remote-config.md). Keep host-specific deployment
records in the private synced `server-sync/deploy/herdr/README.md`, outside this
public repository. The remote shell block is tracked
in [config/remote/hc-agent.zsh](config/remote/hc-agent.zsh).

For a Windows Herdr window with agents and SSH kept in WSL, first see
[Windows Herdr with a WSL backend](docs/remote-config.md#windows-herdr-with-a-wsl-backend).
That local connection uses `wsl.exe` and does not require Windows SSH keys.

For a Herdr desktop / `hc` connection to an SSH server, use the script's absolute
path with `--hc`:

```sh
hc machine add --name dev \
  --via '/absolute/path/to/custom_config/bin/ssh-with-key --hc --key /absolute/path/to/work_key dev-server'
```

`--hc` disables SSH terminal allocation and interactive authentication, uses a
10-second connection timeout, and requires the remote command supplied by hc.
Key loading must succeed without a prompt; encrypted keys that cannot be unlocked
non-interactively fail instead of waiting for input. Output on stdout remains
reserved for hc's protocol.

On each connection it atomically updates the remote symlink
`~/.ssh/hc-forwarded-agent.sock` to that connection's forwarded agent socket.
Only the socket path is written remotely, never the private key. Add this at the
end of the remote user's `~/.zshrc` for hc's interactive Zsh terminals:

```sh
if [[ -n "$HC_TERMINAL_ID" && -L "$HOME/.ssh/hc-forwarded-agent.sock" ]]; then
    export SSH_AUTH_SOCK="$HOME/.ssh/hc-forwarded-agent.sock"
fi
```

New terminals inherit the fixed path. In an existing shell, run the export once;
already-running programs retain their environment. After reconnection, shells
using the fixed path can use the replacement agent without restarting.
Each `--hc` connection atomically publishes its forwarded socket: the last
publication wins, including automatic reconnects. Other clients can keep using
the same Herdr spaces and terminals. Disconnecting a client never changes the
link. If the selected connection ends, authentication is unavailable until a
client reconnects; there is no automatic fallback to another live connection.
The wrapper does not probe the previous agent, maintain a candidate pool, or
compare client identities. Use the same intended key on each client: publishing
a different key changes the identity available to all shared terminals.
This Zsh setup does not change the environment of non-interactive `hc exec`
commands. Other shells need the equivalent startup configuration.

Tmux panes retain the target host label while the SSH connection is active.
Status messages go to stderr, so stdout contains only remote command output
and can be redirected or piped safely.

Run the local checks with Python 3 (no remote connections or private keys used):

```sh
python3 -m unittest discover -s tests -v
```
