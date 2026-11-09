"""Run setup in a temporary home with fake downloads and Homebrew."""
import json
import os
from pathlib import Path
import pty
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SetupRestoreTest(unittest.TestCase):
    def run_setup(self, platform='Darwin', answers='y\nINSTALL\n', interactive=True,
                  brew_status=0, brew_present=True, arch='arm64',
                  download_status=0, installer_status=0):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            repo = tmp / 'repo with spaces'
            repo.mkdir()
            # Redirect absolute Homebrew paths in the fixture, never touch host Homebrew.
            script = (ROOT / 'setup.sh').read_text()
            script = script.replace('/opt/homebrew', str(tmp / 'opt/homebrew'))
            script = script.replace('/usr/local', str(tmp / 'usr/local'))
            (repo / 'setup.sh').write_text(script)
            shutil.copy2(ROOT / 'Brewfile', repo)
            for plugin in ('zsh-autosuggestions', 'zsh-syntax-highlighting'):
                path = repo / 'config/omz_custom/plugins' / plugin
                path.mkdir(parents=True)
                (path / (plugin + '.plugin.zsh')).touch()
            for name in ('vimrc', 'tmux.conf', 'bash_aliases'):
                (repo / 'config' / name).touch()
            user_dir = tmp / 'user'
            (user_dir / '.oh-my-zsh').mkdir(parents=True)
            (user_dir / '.oh-my-zsh/oh-my-zsh.sh').touch()
            (user_dir / '.zshrc').write_text('export PERSONAL_SETTING=preserved\n')
            mock_bin = tmp / 'bin'
            mock_bin.mkdir()
            scripts = {
                'uname': 'if [ "$1" = -m ]; then echo "$TEST_ARCH"; else echo "$TEST_PLATFORM"; fi',
                'zsh': 'exit 0',
                'git': 'echo unexpected-git >> "$TEST_LOG"; exit 99',
                'curl': 'echo download >> "$TEST_LOG"\n'
                        '[ "$2" = https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh ] || exit 99\n'
                        '[ "$3" = -o ] || exit 99\n'
                        '[ "$TEST_DOWNLOAD_STATUS" = 0 ] || exit "$TEST_DOWNLOAD_STATUS"\n'
                        'cp "$TEST_INSTALLER" "$4"',
                'brew': 'printf "%s\\n" "$*" >> "$TEST_LOG"\n'
                        'if [ "$1" = bundle ]; then exit "$TEST_BREW_STATUS"; fi',
            }
            brew_template = tmp / 'brew-template'
            brew_template.write_text('#!/bin/sh\n' + scripts['brew'] + '\n')
            brew_template.chmod(0o755)
            if not brew_present:
                del scripts['brew']
            install_target = tmp / ('opt/homebrew/bin/brew' if arch == 'arm64' else 'usr/local/bin/brew')
            installer = tmp / 'installer'
            installer.write_text(
                'echo installer >> "$TEST_LOG"\n'
                '[ "$TEST_INSTALLER_STATUS" = 0 ] || exit "$TEST_INSTALLER_STATUS"\n'
                'mkdir -p "$(dirname "$TEST_INSTALL_TARGET")"\n'
                'cp "$TEST_BREW_TEMPLATE" "$TEST_INSTALL_TARGET"\n')
            for name, body in scripts.items():
                path = mock_bin / name
                path.write_text('#!/bin/sh\n' + body + '\n')
                path.chmod(0o755)
            env = dict(os.environ, HOME=str(user_dir), PATH=f'{mock_bin}:/usr/bin:/bin',
                       TEST_PLATFORM=platform, TEST_LOG=str(tmp / 'calls'),
                       TEST_BREW_STATUS=str(brew_status), TEST_ARCH=arch,
                       TEST_DOWNLOAD_STATUS=str(download_status),
                       TEST_INSTALLER_STATUS=str(installer_status),
                       TEST_INSTALLER=str(installer), TEST_INSTALL_TARGET=str(install_target),
                       TEST_BREW_TEMPLATE=str(brew_template))
            if interactive:
                master, slave = pty.openpty()
                process = subprocess.Popen(['/bin/bash', str(repo / 'setup.sh')],
                                           env=env, stdin=slave,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                os.close(slave)
                try:
                    os.write(master, answers.encode())
                    stdout, stderr = process.communicate(timeout=10)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    os.close(master)
                code = process.returncode
            else:
                result = subprocess.run(['/bin/bash', str(repo / 'setup.sh')],
                                        env=env, input=answers.encode(), capture_output=True,
                                        timeout=10)
                code, stdout, stderr = result.returncode, result.stdout, result.stderr
            content = (user_dir / '.zshrc').read_text()
            self.assertIn('export PERSONAL_SETTING=preserved', content)
            self.assertIn('source "$ZSH/oh-my-zsh.sh"', content)
            calls = (tmp / 'calls').read_text().splitlines() if (tmp / 'calls').exists() else []
            self.assertFalse(any('unexpected' in call for call in calls), calls)
            return code, (stdout + stderr).decode(), calls, str(repo)

    def test_linux_and_unattended_skip_even_with_yes_input(self):
        for platform, interactive in [('Linux', True), ('Darwin', False)]:
            with self.subTest(platform=platform, interactive=interactive):
                code, output, calls, _ = self.run_setup(platform=platform, interactive=interactive)
                self.assertEqual(code, 0, output)
                self.assertNotIn('Also restore', output)
                self.assertEqual(calls, [])

    def test_declining_either_confirmation_does_not_call_brew(self):
        for answers in ('\n', 'n\n', 'y\n\n', 'y\nno\n', 'y\ninstall\n', '\x04', 'y\n\x04'):
            with self.subTest(answers=answers):
                code, output, calls, _ = self.run_setup(answers=answers)
                self.assertEqual(code, 0, output)
                self.assertIn('Application restore skipped.', output)
                self.assertEqual(calls, [])

    def test_two_confirmations_install_the_displayed_brewfile(self):
        code, output, calls, repo = self.run_setup()
        self.assertEqual(code, 0, output)
        self.assertIn('cask "chatgpt"', output)
        self.assertIn('administrator password', output)
        self.assertEqual(calls, ['shellenv', f'bundle install --no-upgrade --file={repo}/Brewfile'])
        self.assertIn('Application restore completed.', output)

    def test_brew_failure_reports_terminal_setup_is_preserved(self):
        code, output, calls, _ = self.run_setup(brew_status=23)
        self.assertEqual(code, 23, output)
        self.assertIn('Application restore failed; terminal setup is already complete.', output)
        self.assertNotIn('Application restore completed.', output)
        self.assertEqual(len(calls), 2)

    def test_bootstrap_homebrew_on_both_architectures(self):
        for arch in ('arm64', 'x86_64'):
            with self.subTest(arch=arch):
                code, output, calls, repo = self.run_setup(brew_present=False, arch=arch)
                self.assertEqual(code, 0, output)
                self.assertEqual(calls, ['download', 'installer', 'shellenv',
                                        f'bundle install --no-upgrade --file={repo}/Brewfile'])
                self.assertIn('Application restore completed.', output)

    def test_bootstrap_failures_stop_before_bundle(self):
        for options, expected_code, expected_calls in (
            ({'download_status': 22}, 22, ['download']),
            ({'installer_status': 31}, 31, ['download', 'installer']),
        ):
            with self.subTest(options=options):
                code, output, calls, _ = self.run_setup(brew_present=False, **options)
                self.assertEqual(code, expected_code, output)
                self.assertEqual(calls, expected_calls)
                self.assertIn('Application restore failed; terminal setup is already complete.', output)
                self.assertNotIn('Application restore completed.', output)

    @unittest.skipUnless(shutil.which('ruby'), 'Ruby is needed to evaluate Brewfile conditions')
    def test_existing_package_apps_are_excluded_from_brewfile(self):
        # Evaluate the actual Ruby DSL with simulated app presence, without Homebrew.
        ruby = r'''
require "json"
$selected = []
def brew(*) end
def cask(name); $selected << name; end
class File
  def self.exist?(path)
    JSON.parse(ENV.fetch("TEST_APPS")).include?(path)
  end
end
load ARGV.fetch(0)
puts JSON.generate($selected)
'''
        apps = {'uuremote': '/Applications/UURemote.app',
                'microsoft-teams': '/Applications/Microsoft Teams.app'}
        for existing in ([], ['uuremote'], ['microsoft-teams'], list(apps)):
            with self.subTest(existing=existing):
                result = subprocess.run(['ruby', '-e', ruby, str(ROOT / 'Brewfile')],
                                        env=dict(os.environ, TEST_APPS=json.dumps([apps[n] for n in existing])),
                                        capture_output=True, text=True, check=True)
                selected = json.loads(result.stdout)
                for name in apps:
                    self.assertEqual(name in selected, name not in existing)
                self.assertIn('chatgpt', selected)
                self.assertEqual(len(selected), 12 - len(existing))
