# Remote configuration guide

This public guide uses example host names and paths. Keep actual host names,
account names, key paths, and backup locations in `docs/remote-config.local.md`,
which is excluded from Git. Never store private keys or credentials in either file.
The versioned source of the remote Zsh block is
[`config/remote/hc-agent.zsh`](../config/remote/hc-agent.zsh).
Editing that file does **not** automatically update a server. Keep the deployed
block and your local deployment record in sync when making changes.

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

### Restore on a rebuilt machine

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

Validation covered a new hc terminal and the **same terminal after
an actual SSH transport disconnect and automatic reconnect**. The symlink target
changed, and GitHub authentication succeeded again without resetting the shell.

- A GPG agent socket such as `/run/user/<uid>/gnupg/S.gpg-agent.ssh` means the shell has not applied the block.
- A broken fixed symlink means the forwarding connection is down or has not yet
  reconnected. Re-adding the desktop workspace does not repair the connection.
- The block applies to interactive Zsh terminals and their child processes;
  plain `hc exec` does not read `.zshrc`, and existing programs retain their old
  environment.
- Use one `--hc` forwarding connection per remote Unix account. Another such
  connection, including a short-lived probe, replaces the shared link.
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
