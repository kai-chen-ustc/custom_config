"""Exercise real Zsh completion; never execute the completed SSH command."""
import os
from pathlib import Path
import pty
import re
import select
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InteractiveCompletionTest(unittest.TestCase):
    def test_generated_shared_entry_completes_hosts_with_space_paths(self):
        for home_name in ('home', 'home with spaces'):
            for mode in ('link', 'copy'):
                with self.subTest(home=home_name, mode=mode), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    home = root / home_name
                    keys = home / '.ssh'
                    keys.mkdir(parents=True)
                    source = root / 'shared source.conf'
                    source.write_text('Host shared-alpha shared-beta\n'
                                      '    HostName example.invalid\n    User fixture-user\n')
                    (keys / 'config.local').write_text('Host shared-local\n')
                    override = root / 'override.conf'
                    override.write_text('Host override-alpha override-beta\n')
                    env = dict(os.environ, HOME=str(home), TERM='xterm',
                               ZSH_CUSTOM=str(ROOT / 'config/omz_custom'), TMUX='', TMUX_PANE='')
                    result = subprocess.run(['/bin/bash', str(ROOT / 'bin/setup-ssh'), 'install',
                                             '--source', str(source), '--mode', mode],
                                            env=env, capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    result = subprocess.run(['ssh', '-T', '-G', '-F', str(keys / 'config'),
                                             'shared-alpha'], capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('hostname example.invalid\n', result.stdout)
                    self.assertIn('user fixture-user\n', result.stdout)
                    master, slave = pty.openpty()
                    process = subprocess.Popen(['zsh', '-f'], stdin=slave, stdout=slave, stderr=slave,
                                               cwd=home, env=env)
                    os.close(slave)

                    def read_output():
                        output = b''
                        deadline = time.monotonic() + 0.6
                        while time.monotonic() < deadline:
                            if select.select([master], [], [], 0.05)[0]:
                                output += os.read(master, 65536)
                        return output

                    try:
                        read_output()
                        os.write(master, b'autoload -Uz compinit; compinit -D; '
                                 b'source "$ZSH_CUSTOM/custom.zsh"; '
                                 b'source "$ZSH_CUSTOM/custom.zsh"; PS1="READY> "\n')
                        read_output()
                        for command in ('ssh', 'scp', 'sshk'):
                            with self.subTest(command=command):
                                os.write(master, (command + ' shared-\t').encode())
                                output = read_output()
                                for host in (b'shared-alpha', b'shared-beta', b'shared-local'):
                                    self.assertIn(host, output)
                                os.write(master, b'\x03\x15')
                                read_output()
                                os.write(master, (command + ' -F ' + str(override) + ' override-\t').encode())
                                output = read_output()
                                self.assertIn(b'override-alpha', output)
                                self.assertIn(b'override-beta', output)
                                self.assertNotIn(b'shared-alpha', output)
                                os.write(master, b'\x03\x15')
                                read_output()
                    finally:
                        process.kill()
                        process.wait()
                        os.close(master)

    def test_hosts_and_private_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            keys = Path(directory, '.ssh')
            keys.mkdir()
            (keys / 'config').write_text(
                'Host alpha-server beta-server\n  HostName example.invalid\nInclude extra.conf\n')
            (keys / 'extra.conf').write_text('Host gamma-server\n  HostName example.invalid\n')
            for name in ('work_key', 'personal_key'):
                (keys / name).write_text('-----BEGIN OPENSSH PRIVATE KEY-----\n')
            (keys / 'public.pub').write_text('ssh-ed25519 placeholder\n')
            Path(directory, 'unrelated-file').touch()
            master, slave = pty.openpty()
            process = subprocess.Popen(['zsh', '-f'], stdin=slave, stdout=slave, stderr=slave,
                cwd=directory, env=dict(os.environ, HOME=directory, TERM='xterm',
                    ZSH_CUSTOM=str(ROOT / 'config/omz_custom'), TMUX='', TMUX_PANE=''))
            os.close(slave)

            def read_output():
                output = b''
                deadline = time.monotonic() + 1
                while time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        output += os.read(master, 65536)
                return re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', output)

            try:
                read_output()
                os.write(master, b'autoload -Uz compinit; compinit -D; '
                         b'zstyle ":completion:*:*:*:*:*" menu select; unsetopt menu_complete; setopt auto_menu; '
                         b'zstyle ":completion:*" matcher-list "m:{a-z}={A-Z}" "r:|=*" "l:|=* r:|=*"; '
                         b'source "$ZSH_CUSTOM/custom.zsh"; '
                         b'capture-buffer() { print -r -- "BUFFER=$BUFFER"; }; '
                         b'zle -N capture-buffer; bindkey "^X" capture-buffer; PS1="READY> "\n'  )
                read_output()
                os.write(master, b'sshk \t')
                output = read_output()
                for host in (b'alpha-server', b'beta-server', b'gamma-server'):
                    self.assertIn(host, output)
                self.assertNotIn(b'unrelated-file', output)
                os.write(master, b'\x03\x15')
                read_output()
                os.write(master, b'sshk alpha-server --key \t')
                output = read_output()
                for key in (b'work_key', b'personal_key', b'private keys in ~/.ssh'):
                    self.assertIn(key, output)
                self.assertNotIn(b'public.pub', output)
                self.assertNotIn(b'unrelated-file', output)
                os.write(master, b'\x03\x15')
                read_output()
                os.write(master, b'sshk alpha-server --key work\t')
                self.assertIn(str(keys / 'work_key').encode(), read_output())
                for command, expected in (
                    (b'sshk --\t', b'--key'),
                    (b'sshk --k\t', b'--key'),
                    (b'sshk alpha-server --\t', b'--key'),
                    (b'sshk --key \t', b'private keys in ~/.ssh'),
                    (b'sshk --key work\t', str(keys / 'work_key').encode()),
                    (b'sshk --key /tmp/example-key \t', b'alpha-server'),
                    (b'sshk -p 2222 \t', b'alpha-server'),
                    (b'sshk -vp2222 --key /tmp/example-key \t', b'alpha-server'),
                    (b'sshk -p 2222 --key \t', b'private keys in ~/.ssh'),
                    (b'sshk alpha-server -p 2222 --key work\t', str(keys / 'work_key').encode()),
                    (b'sshk alpha-server -p 2222 --\t', b'--key'),
                ):
                    with self.subTest(command=command):
                        os.write(master, b'\x03\x15')
                        read_output()
                        os.write(master, command)
                        output = read_output()
                        if expected not in output:
                            os.write(master, b'\x18')
                            output += read_output()
                        self.assertIn(expected, output)
                        self.assertNotIn(b'unrelated-file', output)
                        self.assertNotIn(b'public.pub', output)
                        self.assertNotIn(b'possibilities', output)
            finally:
                process.kill()
                process.wait()
                os.close(master)
