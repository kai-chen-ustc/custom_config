import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import time
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'bin/ssh-with-key'


class SSHWithKeyTest(unittest.TestCase):
    def test_hc_transport_and_reconnect(self):
        # Execute the remote bootstrap locally through a mock SSH transport.
        # Real temporary agents provide sockets; no keys or network are used.
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            key = tmp / 'key'
            key.touch()
            remote = tmp / "remote home with 'quotes'"
            remote.mkdir()
            (tmp / 'ssh-add').write_text(
                '#!/bin/sh\n[ "$SSH_ASKPASS_REQUIRE" = force ] || exit 1\n'
                '[ "$SSH_ASKPASS" = /usr/bin/false ] || exit 1\n'
                'test -z "$(cat)"\n')
            (tmp / 'ssh').write_text(
                f'#!{sys.executable}\nimport os, subprocess, sys\n'
                'assert "-T" in sys.argv and "BatchMode=yes" in sys.argv\n'
                'os.environ["HOME"] = os.environ["TEST_REMOTE"]\n'
                'if os.environ.get("NO_FORWARD"): os.environ.pop("SSH_AUTH_SOCK", None)\n'
                'result = subprocess.run(["sh", "-c", sys.argv[-1]])\n'
                'sock = os.environ.get("SSH_AUTH_SOCK")\n'
                'if sock and os.path.exists(sock): os.unlink(sock)\n'
                'sys.exit(result.returncode)\n')
            for name in ('ssh', 'ssh-add'):
                (tmp / name).chmod(0o755)
            env = dict(os.environ, PATH=f'{tmp}:{os.environ["PATH"]}',
                       TEST_REMOTE=str(remote), TMUX_PANE='')
            command = 'printf "%s\\n" "it\'s intact"; cat; exit 17'
            args = [str(SCRIPT), '--hc', '--key', str(key), 'host', command]
            link = remote / '.ssh/hc-forwarded-agent.sock'
            targets = []
            for _ in range(2):
                result = subprocess.run(args, env=env, input='protocol bytes\n',
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 17, result.stderr)
                self.assertEqual(result.stdout, "it's intact\nprotocol bytes\n")
                self.assertTrue(link.is_symlink())
                targets.append(os.readlink(link))
            self.assertNotEqual(*targets)
            result = subprocess.run(args, env=dict(env, NO_FORWARD='1'),
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('no forwarded SSH agent', result.stderr)
            self.assertEqual(os.readlink(link), targets[-1])
            link.unlink()
            link.write_text('keep this file')
            result = subprocess.run(args, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(link.read_text(), 'keep this file')

    def test_hc_last_connection_wins_without_probes_or_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            remote = tmp / 'remote'
            (remote / '.ssh').mkdir(parents=True)
            key = tmp / 'key'
            key.touch()
            (tmp / 'ssh-add').write_text(
                '#!/bin/sh\nif [ "$1" = -l ]; then\n'
                ' echo probed > "$TEST_PROBE"; exit 99\nfi\nexit 0\n')
            (tmp / 'ssh').write_text(
                f'#!{sys.executable}\nimport os, pathlib, subprocess, sys\n'
                'os.environ["HOME"] = os.environ["TEST_REMOTE"]\n'
                'pathlib.Path(os.environ["TEST_SOCKET"]).write_text(os.environ["SSH_AUTH_SOCK"])\n'
                'r = subprocess.run(["sh", "-c", sys.argv[-1]])\n'
                'pathlib.Path(os.environ["SSH_AUTH_SOCK"]).unlink(missing_ok=True)\n'
                'sys.exit(r.returncode)\n')
            for name in ('ssh', 'ssh-add'):
                (tmp / name).chmod(0o755)
            env = dict(os.environ, PATH=f'{tmp}:{os.environ["PATH"]}',
                       TEST_REMOTE=str(remote), TEST_PROBE=str(tmp / 'probe'),
                       TMUX_PANE='')
            args = [str(SCRIPT), '--hc', '--key', str(key), 'host',
                    'printf "ready\\n"; cat']
            link = remote / '.ssh/hc-forwarded-agent.sock'
            # An existing socket that never replies must not block a new login.
            stalled = socket.socket(socket.AF_UNIX)
            stalled.bind(str(tmp / 'stalled'))
            stalled.listen()
            link.symlink_to(tmp / 'stalled')
            processes = []

            def start(name):
                p = subprocess.Popen(args, env=dict(env, TEST_SOCKET=str(tmp / name)),
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
                processes.append(p)
                return p

            def ready(p):
                self.assertTrue(select.select([p.stdout], [], [], 5)[0],
                                'bootstrap blocked before starting the command')
                self.assertEqual(p.stdout.readline(), 'ready\n')

            def finish(p):
                stdout, stderr = p.communicate('protocol bytes\n', timeout=5)
                self.assertEqual(p.returncode, 0, stderr)
                self.assertEqual(stdout, 'protocol bytes\n')

            try:
                first = start('first')
                ready(first)
                first_socket = os.readlink(link)
                second = start('second')
                ready(second)
                second_socket = os.readlink(link)
                self.assertNotEqual(first_socket, second_socket)
                finish(first)
                self.assertEqual(os.readlink(link), second_socket)
                self.assertTrue(link.is_socket())

                # Both simultaneous logins may start; the last publication wins.
                third = start('third')
                fourth = start('fourth')
                ready(third)
                ready(fourth)
                sockets = [(tmp / name).read_text() for name in ('third', 'fourth')]
                selected = os.readlink(link)
                self.assertIn(selected, sockets)
                winner, loser = (third, fourth) if selected == sockets[0] else (fourth, third)
                finish(loser)
                self.assertEqual(os.readlink(link), selected)
                finish(winner)
                self.assertEqual(os.readlink(link), selected)
                self.assertFalse(
                    link.exists(), 'no automatic fallback to the still-live second connection')
                self.assertIsNone(second.poll())

                reconnected = start('reconnected')
                ready(reconnected)
                replacement = os.readlink(link)
                self.assertTrue(link.is_socket())
                finish(second)
                self.assertEqual(os.readlink(link), replacement)
                finish(reconnected)
                self.assertFalse((tmp / 'probe').exists(), 'previous agents must not be probed')
                self.assertFalse(list((remote / '.ssh').glob('.hc-agent.*')))
                self.assertFalse((remote / '.ssh/hc-forwarded-agents').exists())
            finally:
                stalled.close()
                for p in processes:
                    if p.poll() is None:
                        p.communicate('', timeout=5)
                    for stream in (p.stdin, p.stdout, p.stderr):
                        if stream and not stream.closed:
                            stream.close()

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
                       '    assert args[1:9] == ["-o", "IdentityAgent=" + os.environ["SSH_AUTH_SOCK"], "-o", "ForwardAgent=" + os.environ["SSH_AUTH_SOCK"], "-o", "AddKeysToAgent=no", "-S", "none"]\n'
                       '    json.dump([args[0], *args[9:]], f)\n'
                       'print(json.dumps({"ok": True}, separators=(",", ":")))\n'
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
            for options in (
                ['-p', '2222', '--key', str(key), 'host'],
                ['--key', str(key), '-p2222', 'host'],
                ['host', '-p', '2222', '--key', str(key)],
                ['-vp2222', 'host', '--key', str(key)],
                ['-vp', '2222', 'host', '--key', str(key)],
                ['-o', 'ProxyCommand=ssh jump -W %h:%p', 'host', '--key', str(key)],
            ):
                forwarded = options.copy()
                index = forwarded.index('--key')
                del forwarded[index:index + 2]
                cases.append((options + ['printf', '--key', 'remote value'], 0, 0,
                              ['-A', *forwarded, 'printf', '--key', 'remote value']))
            cases.append((['--key', str(key), '--', 'host', 'printf', '--key'],
                          0, 0, ['-A', '--', 'host', 'printf', '--key']))
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
                    self.assertIn('Starting temporary SSH agent', result.stderr)
                    self.assertEqual(result.stdout, '' if expected is None else '{"ok":true}\n')
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

    def test_forward_agent_config_cannot_override_selected_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            key = tmp / 'key'
            key.touch()
            add = tmp / 'ssh-add'
            add.write_text('#!/bin/sh\nexit 0\n')
            add.chmod(0o755)
            config = tmp / 'config'
            config.write_text('Host *\n ForwardAgent /tmp/other-agent\n'
                              ' IdentityAgent /tmp/other-agent\n AddKeysToAgent yes\n')
            result = subprocess.run(
                [str(SCRIPT), '-F', str(config), '--key', str(key), 'example.invalid', '-G'],
                env=dict(os.environ, PATH=f'{tmp}:{os.environ["PATH"]}', TMUX_PANE=''),
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            settings = dict(line.split(' ', 1) for line in result.stdout.splitlines())
            self.assertEqual(settings['forwardagent'], settings['identityagent'])
            self.assertNotEqual(settings['forwardagent'], '/tmp/other-agent')
            self.assertEqual(settings['addkeystoagent'], 'false')

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
            self.assertIn('Usage: sshk [--key path] [ssh options] <host|user@ip>', result.stdout)
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
                PREFIX=''
                words=(sshk -o --key host --key ''); CURRENT=6; _sshk
                words=(sshk host printf --key ''); CURRENT=5; _sshk
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
            self.assertIn('--hc', lines[6])
            self.assertEqual(lines[7:], ['keys', 'ssh:5:ssh,host,printf,--key,'])

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
        for args in ([], ['host', '--key'], ['host', '--key', '/nonexistent/key'], ['-A'], ['-p'], ['--'], ['host', '-p']):
            with self.subTest(args=args):
                result = subprocess.run([str(SCRIPT), *args], capture_output=True)
                self.assertEqual(result.returncode, 1)
        result = subprocess.run([str(SCRIPT), '--help'], capture_output=True)
        self.assertEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
