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
