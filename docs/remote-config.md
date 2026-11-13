# Remote configuration guide

This public guide uses example host names and paths. Actual hosts, accounts,
key paths, backups, and validation results belong in the private Seafile record
`server-sync/deploy/herdr/README.md`. Neither document should contain credentials.

The remote Zsh block's source is
[`config/remote/hc-agent.zsh`](../config/remote/hc-agent.zsh). Deploy changes
explicitly and update the snapshot and deployment record in `server-sync/deploy/herdr/`.

## Windows Herdr with a WSL backend

Run the native Windows Herdr app and connect it to the core inside WSL. Coding
agents, projects, Git, and SSH then run in WSL workspaces. Windows needs Herdr
and hc, but does not need coding agents or a second copy of the WSL SSH keys.
The Windows-to-WSL connection uses `wsl.exe`, not SSH, and needs no WSL SSH server.

Windows hc must be version 0.1.20 or newer; earlier versions reject `--via`.
The connection was verified with hc 0.1.21 and Windows Herdr app 0.1.15.
In PowerShell, find the distribution name with `wsl.exe --list --quiet`, then
replace `Ubuntu` below with that name:

```powershell
$hc = Join-Path $env:LOCALAPPDATA 'Programs\herdr-core\hc.exe'
& $hc --version
& $hc machine ls
& $hc machine add --via 'wsl.exe -d Ubuntu -e sh -c' --name wsl
& $hc exec --on wsl -- /usr/bin/uname -s
& $hc exec --on wsl -- /usr/bin/which ssh
```

Use the installed executable's actual path if it differs. Before registration,
back up any existing `%LOCALAPPDATA%\herdr-core\default\machines.json` and
the app's `%USERPROFILE%\.config\herdr-app\view.json` into a private directory.
Inspect an existing `wsl` registration rather than adding a duplicate or replacing it.

In Windows Herdr, select a space under the `wsl` machine, or create one there.
Existing WSL core spaces can appear automatically. New tabs and splits in that
space stay in WSL; the Windows local machine remains available separately.
This does not change the application's global default local environment or
make Windows-native `ssh.exe` use the WSL SSH configuration.

Inside a WSL space, `ssh`, `sshk`, and Git use the existing Linux configuration
and keys. No key synchronization or additional agent forwarding is needed for
the Windows-to-WSL connection. Remote server registrations are separate; do not
assume WSL's machine registry is recursively imported into the Windows sidebar.

Verify the selected machine, Linux command execution, and agent availability.
Test Chinese IME composition and committed text manually in the Windows window;
successful command execution alone does not verify input-method behavior.
WSL shutdown or a host reboot interrupts the backend's running programs.

To roll back, run `& $hc machine rm wsl` in Windows PowerShell. Removing the
connection does not stop WSL programs. Re-select the previous Windows space;
do not close shared WSL tabs as a rollback step, since closing a tab ends its
terminals. See the upstream
[machine transport documentation](https://github.com/herdrdev/herdr-core/blob/master/docs/machines.md).

## Example: hc SSH agent forwarding

The workflow was verified with hc 0.1.21. Replace all example values below
with your own settings before running commands.

| Item | Location / value |
| --- | --- |
| SSH host and local hc machine name | `dev-server` |
| Remote account and shell | your remote account, `/usr/bin/zsh` |
| Remote configuration | `~/.zshrc`, at the end of the file |
| Block markers | `# >>> sshk hc agent forwarding >>>` through `# <<< sshk hc agent forwarding <<<` |
| Original configuration backup | `~/.zshrc.before-hc-agent-YYYYMMDD-HHMMSS` |
| Runtime symlink | `~/.ssh/hc-forwarded-agent.sock` |
| Local forwarding key | `~/.ssh/work_key` on the Mac only |
| Local machine registry | `~/.local/state/herdr-core/default/machines.json` |

For this example, the machine's `via` is `true`, and its `target` is:

```sh
/absolute/path/to/custom_config/bin/ssh-with-key --hc --key /absolute/path/to/work_key dev-server
```

The local script starts an agent with only the selected key. SSH forwards that
agent, and the remote bootstrap updates the fixed symlink. The Zsh block points
hc terminals at that link. The temporary `/tmp/ssh-…/agent.…` target changes on
reconnection and must not be hard-coded or backed up. No private key is copied
to the server.

### Windows connections through WSL

Register each server in the Windows core to show it in the Windows Herdr sidebar.
Use WSL's wrapper and key paths; replace these example values before running:

```powershell
$hc = Join-Path $env:LOCALAPPDATA 'Programs\herdr-core\hc.exe'
& $hc machine add --name dev-server --via 'wsl.exe -d Ubuntu -e /home/example/custom_config/bin/ssh-with-key --hc --key /home/example/.ssh/work_key dev-server'
```

The server still needs the Zsh block described below. This registers a connection
to its existing default core, so Mac and Windows viewers share the same spaces
and terminals. It does not create a separate core session. Windows keeps the
connection command, while SSH configuration and private keys stay in WSL.

If a private hostname resolves on Windows but not in WSL, verify the resolved
address and put a host-specific `HostName` override in WSL's `config.local`, with
`HostKeyAlias` retaining the original name used in known_hosts. Back up that file
first. Do not disable host-key checking or publish the address in this repository.

### Multiple viewers and agent availability

Each connection atomically replaces the stable link with its own forwarded socket.
The last publication wins, including background reconnects; window focus does not
select an agent. Concurrent clients can still share the same core and terminals.
No previous agent is probed, and there is no candidate pool, monitor, or identity
comparison. Choose the same intended key on each client: a different key replaces
the identity available to every terminal using the stable path.

Disconnecting any client leaves the link unchanged. If the selected connection
ends, Git/SSH authentication through that link fails until a client reconnects,
even if another client remains connected. Closing an older connection does not
undo a newer connection's selection. Remote programs continue running; a failed
authentication operation may need retrying after reconnection.

After changing the wrapper, reconnect the affected transports: updating the local
script alone does not change a running remote bootstrap. Keep the remote core and
user terminals running while reconnecting.

### Configure a machine

1. Ensure ordinary SSH login and agent forwarding work for the host, and hc is
   installed on the remote machine.
2. Back up the remote `~/.zshrc`. Copy the complete versioned
   [`hc-agent.zsh`](../config/remote/hc-agent.zsh) block to its end. If the markers
   already exist, replace that block instead of appending a duplicate. Run
   `zsh -n ~/.zshrc` on the server to check syntax.
3. Register the machine locally with the correct absolute script and key paths:

   ```sh
   hc machine add --name dev-server \
     --via '/absolute/path/to/custom_config/bin/ssh-with-key --hc --key /absolute/path/to/work_key dev-server'
   ```

   hc 0.1.21 has no command to edit `via`. For an existing registration, back up
   the local machine registry, then use `hc machine rm dev-server` before
   adding it with the same name. Removing the registration disconnects it locally;
   remote terminals keep running. A rebuilt server can have a different core ID.
4. Open a new remote Zsh terminal in Herdr. Existing shells need this once:

   ```sh
   export SSH_AUTH_SOCK="$HOME/.ssh/hc-forwarded-agent.sock"
   ```

### Verify and troubleshoot

Run inside a **Herdr remote Zsh terminal**:

```sh
echo "$SSH_AUTH_SOCK"
readlink "$SSH_AUTH_SOCK"
ssh-add -l
ssh -T git@github.com
```

The first command should print the absolute path to
`$HOME/.ssh/hc-forwarded-agent.sock`.
`ssh-add -l` should show only the selected work key. GitHub should greet
the account associated with the selected key; its successful authentication greeting normally still exits with
status 1 because GitHub provides no interactive shell.

Verify both a new terminal and the **same terminal after SSH reconnects**.
The symlink target should change, and authentication should work without
resetting the shell environment.

- A GPG agent socket such as `/run/user/<uid>/gnupg/S.gpg-agent.ssh` means the shell has not applied the block.
- A broken fixed symlink means the forwarding connection is down or has not yet
  reconnected. Re-adding the desktop workspace does not repair the connection.
- The block applies to interactive Zsh terminals and their child processes;
  plain `hc exec` does not read `.zshrc`, and existing programs retain their old
  environment.
- Verify that a later `--hc` connection takes over, an older disconnect does not
  change the link, and reconnecting restores authentication after the selected
  connection ends. A short-lived `--hc` probe also takes over and leaves the link
  unavailable when it exits; use ordinary SSH without forwarding for inspection.
- The local key must load without a password prompt for hc background reconnects.

### Remove this setup

1. Change the local machine back to ordinary SSH by removing its registration
   and running `hc machine add dev-server --name dev-server`.
2. Remove only the marked block from the remote `~/.zshrc`. Compare against the
   original backup if needed; do not overwrite later unrelated shell changes by
   blindly restoring the whole backup.
3. After the `--hc` connection has ended, remove the symlink with
   `test ! -L ~/.ssh/hc-forwarded-agent.sock || rm ~/.ssh/hc-forwarded-agent.sock`.
   Open a new shell to discard the old exported value.

Ordinary SSH registration alone does not provide agent access to hc terminals;
this rollback removes the integration rather than replacing it.
