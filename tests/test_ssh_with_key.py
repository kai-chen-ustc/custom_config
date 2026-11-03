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
                       '    json.dump(sys.argv[1:], f)\n'
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
            ]
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
                    pid = int((tmp / 'pid').read_text())
                    # The shell has delivered SIGTERM; allow the agent time to exit.
                    for _ in range(100):
                        result = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)],
                                                capture_output=True, text=True)
                        if not result.stdout.strip() or result.stdout.lstrip().startswith('Z'):
                            break
                        time.sleep(0.01)
                    else:
                        os.kill(pid, 15)
                        self.fail('temporary agent survived script exit')
                    if expected is None:
                        self.assertFalse((tmp / 'args').exists())
                    else:
                        self.assertEqual(json.loads((tmp / 'args').read_text()), expected)

    def test_zsh_alias_with_spaces_in_repo_path(self):
        with tempfile.TemporaryDirectory() as directory:
            repo_link = Path(directory) / 'repo with spaces'
            repo_link.symlink_to(ROOT, target_is_directory=True)
            result = subprocess.run(
                ['zsh', '-f', '-c', 'source "$ZSH_CUSTOM/custom_kai.zsh"; eval "sshk --help"'],
                cwd=directory,
                env=dict(os.environ, HOME=directory, TMUX='', TMUX_PANE='',
                         ZSH_CUSTOM=str(repo_link / 'config/omz_custom')),
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Usage:', result.stdout)
            self.assertIn('--key', result.stdout)

    def test_usage_errors(self):
        for args in ([], ['host', '--key'], ['host', '--key', '/nonexistent/key'], ['-A']):
            with self.subTest(args=args):
                result = subprocess.run([str(SCRIPT), *args], capture_output=True)
                self.assertEqual(result.returncode, 1)
        result = subprocess.run([str(SCRIPT), '--help'], capture_output=True)
        self.assertEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
