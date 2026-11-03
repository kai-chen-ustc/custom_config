import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'bin/ssh-with-key'


class SSHWithKeyTest(unittest.TestCase):
    def test_agent_lifecycle_and_arguments(self):
        # Use a real agent, but never load private keys or connect to a server.
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            key = tmp / 'key with spaces'
            key.touch()
            for name, body in {
                'ssh-add': 'echo "$SSH_AGENT_PID" > "$TEST_PID"\n'
                           'printf "%s\\n" "$1" > "$TEST_KEY"\nexit "$ADD_STATUS"',
                'tmux': 'printf "%s\\n" "$*" >> "$TEST_TMUX"',
                'ssh': f'#!{sys.executable}\nimport json, os, sys\n'
                       'with open(os.environ["TEST_ARGS"], "w") as f:\n'
                       '    args = sys.argv[1:]\n'
                       '    assert args[1:7] == ["-o", "IdentityAgent=" + os.environ["SSH_AUTH_SOCK"], "-o", "AddKeysToAgent=no", "-S", "none"]\n'
                       '    json.dump([args[0], *args[7:]], f)\n'
                       'sys.exit(int(os.environ["SSH_STATUS"]))',
            }.items():
                executable = tmp / name
                executable.write_text(body if body.startswith('#!') else '#!/bin/sh\n' + body)
                executable.chmod(0o755)
            env = dict(os.environ, PATH=f'{tmp}:{os.environ["PATH"]}',
                       GIT_KEY_PATH=str(key), TMUX_PANE='%1', TEST_PID=str(tmp / 'pid'),
                       TEST_KEY=str(tmp / 'key-log'), TEST_TMUX=str(tmp / 'tmux-log'),
                       TEST_ARGS=str(tmp / 'args'))
            cases = [
                (['host'], 0, 0, ['-A', 'host']),
                (['host', '--key', str(key), 'printf', 'a b'],
                 0, 17, ['-A', 'host', 'printf', 'a b']),
                (['host'], 1, 0, None),
                (['--key', str(key), 'host', 'printf', 'a b'],
                 0, 0, ['-A', 'host', 'printf', 'a b']),
            ]
            agent_pids = []
            for args, add_status, ssh_status, expected in cases:
                with self.subTest(args=args, add_status=add_status):
                    (tmp / 'args').unlink(missing_ok=True)
                    (tmp / 'tmux-log').unlink(missing_ok=True)
                    result = subprocess.run([str(SCRIPT), *args],
                                            env=dict(env, GIT_KEY_PATH="/nonexistent/default" if "--key" in args else str(key),
                                                     ADD_STATUS=str(add_status),
                                                     SSH_STATUS=str(ssh_status)),
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, add_status or ssh_status, result.stderr)
                    self.assertEqual((tmp / 'key-log').read_text().strip(), str(key))
                    tmux_calls = (tmp / 'tmux-log').read_text().splitlines()
                    expected_tmux = ['set-option -pu -t %1 @ssh_alias']
                    if expected is not None:
                        expected_tmux.insert(0, 'set-option -p -t %1 @ssh_alias host')
                    self.assertEqual(tmux_calls, expected_tmux)
                    agent_pids.append(int((tmp / 'pid').read_text()))
                    if expected is None:
                        self.assertFalse((tmp / 'args').exists())
                    else:
                        self.assertEqual(json.loads((tmp / 'args').read_text()), expected)

            # OpenSSH checks whether its command exited on a roughly 10-second timer.
            deadline = time.monotonic() + 15
            while agent_pids and time.monotonic() < deadline:
                for pid in agent_pids[:]:
                    state = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)],
                                           capture_output=True, text=True).stdout.strip()
                    if not state or state.startswith('Z'):
                        agent_pids.remove(pid)
                if agent_pids:
                    time.sleep(0.1)
            for pid in agent_pids:
                os.kill(pid, 15)
            self.assertFalse(agent_pids, 'OpenSSH did not automatically stop its agents')

    def test_default_key_selection(self):
        cases = [
            (['id_rsa', 'id_ed25519'], '', None, 'id_ed25519'),
            (['id_rsa', 'id_ed25519.pub'], '', None, 'id_rsa'),
            (['custom_key'], '', None, None),
            (['id_ed25519', 'custom_key'], 'custom_key', None, 'custom_key'),
            (['id_ed25519', 'custom_key'], 'missing', 'custom_key', 'custom_key'),
            (['id_ed25519'], 'missing', None, None),
            (['id_ed25519'], '', 'missing', None),
        ]
        for files, configured, explicit, expected in cases:
            with self.subTest(files=files, configured=configured, explicit=explicit):
                with tempfile.TemporaryDirectory() as directory:
                    home = Path(directory)
                    keys = home / '.ssh'
                    keys.mkdir()
                    for name in files:
                        (keys / name).touch()
                    # Fail key loading deliberately, recording selection without using a key.
                    add = home / 'ssh-add'
                    add.write_text('#!/bin/sh\nprintf "%s\\n" "$1" > "$HOME/selected"\nexit 1\n')
                    add.chmod(0o755)
                    args = [str(SCRIPT), 'dev-server']
                    if explicit:
                        args += ['--key', str(keys / explicit)]
                    result = subprocess.run(args, capture_output=True, text=True,
                        env=dict(os.environ, HOME=directory, TMUX_PANE='',
                                 PATH=f'{directory}:{os.environ["PATH"]}',
                                 GIT_KEY_PATH=str(keys / configured) if configured else ''))
                    self.assertEqual(result.returncode, 1)
                    if expected:
                        self.assertEqual((home / 'selected').read_text().strip(), str(keys / expected))
                    else:
                        self.assertFalse((home / 'selected').exists())
                        self.assertNotIn('Starting temporary SSH agent', result.stdout)
                        self.assertIn('Error:', result.stderr)

    def test_zsh_command_with_spaces_in_repo_path(self):
        with tempfile.TemporaryDirectory() as directory:
            repo_link = Path(directory) / 'repo with spaces'
            repo_link.symlink_to(ROOT, target_is_directory=True)
            result = subprocess.run(
                ['zsh', '-f', '-c', 'source "$ZSH_CUSTOM/custom.zsh"; eval "sshk --help"'],
                cwd=directory,
                env=dict(os.environ, HOME=directory, TMUX='', TMUX_PANE='',
                         ZSH_CUSTOM=str(repo_link / 'config/omz_custom')),
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Usage: sshk [--key path] <host|user@ip>', result.stdout)
            self.assertIn('--key', result.stdout)

    def test_completion_routing_and_alias_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(['zsh', '-f', '-c', r'''
                alias sshk='old-command'
                compdef() { print -r -- "registered:$*"; }
                source "$ZSH_CUSTOM/custom.zsh"
                (( $+functions[sshk] && ! $+aliases[sshk] )) || exit 1
                _ssh() { print -r -- "$service:$CURRENT:${(j:,:)words}"; }
                _ssh_hosts() { print hosts; }
                compset() { :; }
                _sshk_keys() { print keys; }
                _describe() { print -rl -- "${options[@]}"; }
                words=(sshk dev); CURRENT=2; _sshk
                words=(sshk host --key ''); CURRENT=4; _sshk
                words=(sshk host --key '/key with spaces' -p ''); CURRENT=6; _sshk
                words=(sshk host --); CURRENT=3; PREFIX=--; _sshk
            '''], cwd=directory,
                env=dict(os.environ, HOME=directory, TMUX='', TMUX_PANE='',
                         ZSH_CUSTOM=str(ROOT / 'config/omz_custom')),
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.splitlines()
            self.assertEqual(lines[:4], ['registered:_sshk sshk', 'hosts',
                                         'keys', 'ssh:4:ssh,host,-p,'])
            self.assertIn('--key', lines[4])
            self.assertIn('--help', lines[5])

    def test_private_key_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            keys = home / '.ssh'
            keys.mkdir()
            (keys / 'work key').write_text('-----BEGIN OPENSSH PRIVATE KEY-----\n')
            (keys / 'rsa_key').write_text('-----BEGIN RSA PRIVATE KEY-----\n')
            (keys / 'public.pub').write_text('ssh-ed25519 public-key-placeholder\n')
            (keys / 'config').write_text('Host dev-server\n')
            (keys / 'known_hosts').touch()
            (keys / 'subdirectory').mkdir()
            result = subprocess.run(['zsh', '-f', '-c', r'''
                source "$ZSH_CUSTOM/custom.zsh"
                _wanted() { print -rl -- "$@"; }
                _files() { print browse-path; }
                PREFIX=''; _sshk_keys
                PREFIX='./'; _sshk_keys
            '''], cwd=directory,
                env=dict(os.environ, HOME=directory, TMUX='', TMUX_PANE='',
                         ZSH_CUSTOM=str(ROOT / 'config/omz_custom')),
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.splitlines()
            self.assertIn('work key', lines)
            self.assertIn('rsa_key', lines)
            for excluded in ('public.pub', 'config', 'known_hosts', 'subdirectory'):
                self.assertNotIn(excluded, lines)
            self.assertEqual(lines[-1], 'browse-path')

    def test_usage_errors(self):
        for args in ([], ['host', '--key'], ['host', '--key', '/nonexistent/key'], ['-A']):
            with self.subTest(args=args):
                result = subprocess.run([str(SCRIPT), *args], capture_output=True)
                self.assertEqual(result.returncode, 1)
        result = subprocess.run([str(SCRIPT), '--help'], capture_output=True)
        self.assertEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
