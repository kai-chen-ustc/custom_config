"""Shared SSH installation uses temporary homes and ssh -G, never a network login."""
import os
from pathlib import Path
import pty
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'bin/setup-ssh'


class SetupSSHTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home with spaces'
        self.home.mkdir()
        self.ssh = self.home / '.ssh'
        self.source = self.root / 'shared hosts.conf'
        self.source.write_text('Host dev-server\n    User example-user\n'
                               '    IdentityFile ~/.ssh/example_key\n    IdentitiesOnly yes\n')
        self.source.chmod(0o600)
        self.env = dict(os.environ, HOME=str(self.home))

    def run_script(self, action='install', source=True, options=(), answers=None, env=None):
        args = ['/bin/bash', str(SCRIPT), action]
        if source:
            args += ['--source', str(self.source)]
        args += list(options)
        if answers is None:
            return subprocess.run(args, env=env or self.env, input='', text=True,
                                  capture_output=True, timeout=10)
        master, slave = pty.openpty()
        process = subprocess.Popen(args, env=env or self.env, stdin=slave,
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
        return subprocess.CompletedProcess(args, process.returncode, stdout.decode(), stderr.decode())

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def effective(self, host='dev-server'):
        result = subprocess.run(['ssh', '-T', '-G', '-F', str(self.ssh / 'config'), host],
                                capture_output=True, text=True, timeout=10)
        self.assert_ok(result)
        return result.stdout

    def test_link_install_repeat_status_and_live_source_updates(self):
        self.assert_ok(self.run_script())
        link = self.ssh / 'config.shared'
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), self.source.resolve())
        self.assertIn('user example-user\n', self.effective())
        before = (self.ssh / 'config').stat().st_mtime_ns
        result = self.run_script()
        self.assert_ok(result)
        self.assertIn('already configured', result.stdout)
        self.assertEqual(before, (self.ssh / 'config').stat().st_mtime_ns)
        self.assert_ok(self.run_script('status', source=False))
        self.source.write_text('Host dev-server\n    User updated-user\n')
        self.assertIn('user updated-user\n', self.effective())
        self.assertEqual(list(self.home.glob('.ssh-config-backup-*')), [])
        self.assertEqual(self.ssh.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.ssh / 'config').stat().st_mode & 0o777, 0o600)

    def test_glob_home_is_rejected_without_creating_or_replacing_files(self):
        for name in ('home[1]', 'home]', 'home*', 'home?'):
            with self.subTest(home=name):
                home = self.root / name
                home.mkdir()
                env = dict(self.env, HOME=str(home))
                result = self.run_script(env=env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('glob characters', result.stderr)
                self.assertFalse((home / '.ssh').exists())
                ssh = home / '.ssh'
                ssh.mkdir()
                (ssh / 'config').write_text('Host original-server\n')
                for action in ('install', 'replace', 'status'):
                    result = self.run_script(action, env=env)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('glob characters', result.stderr)
                    self.assertEqual((ssh / 'config').read_text(), 'Host original-server\n')
                    self.assertEqual(sorted(p.name for p in ssh.iterdir()), ['config'])
                    self.assertEqual(list(home.glob('.ssh-config-backup-*')), [])

    def test_existing_files_links_and_directories_never_overwritten(self):
        self.ssh.mkdir()
        target = self.root / 'existing'
        target.write_text('original content')
        for name in ('config', 'config.shared'):
            path = self.ssh / name
            for kind in ('file', 'link', 'broken', 'directory'):
                with self.subTest(name=name, kind=kind):
                    if kind == 'file':
                        path.write_text('original content')
                    elif kind == 'directory':
                        path.mkdir()
                    else:
                        path.symlink_to(target if kind == 'link' else self.root / 'absent')
                    result = self.run_script()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertTrue(path.exists() or path.is_symlink())
                    self.assertEqual(target.read_text(), 'original content')
                    if kind == 'file':
                        self.assertEqual(path.read_text(), 'original content')
                    self.assertEqual(list(self.home.glob('.ssh-config-backup-*')), [])
                    path.rmdir() if kind == 'directory' else path.unlink()

    def test_replace_backs_up_symlink_and_resolved_file_and_keeps_local(self):
        self.ssh.mkdir()
        old = self.root / 'old configuration'
        old.write_text('Host old-server\n    User old-user\n')
        (self.ssh / 'config').symlink_to(old)
        local = self.ssh / 'config.local'
        local.write_text('Host dev-server\n    User local-user\n')
        self.assert_ok(self.run_script('replace'))
        backup, = self.home.glob('.ssh-config-backup-*')
        self.assertTrue((backup / 'config').is_symlink())
        self.assertEqual((backup / 'config.resolved').read_text(), old.read_text())
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        self.assertEqual(old.read_text(), 'Host old-server\n    User old-user\n')
        self.assertIn('user local-user\n', self.effective())
        self.assertTrue(local.exists())
        self.assert_ok(self.run_script('replace'))
        self.assertEqual(len(list(self.home.glob('.ssh-config-backup-*'))), 1)

    def test_copy_update_and_manual_edit_require_replace(self):
        options = ['--mode', 'copy']
        self.assert_ok(self.run_script(options=options))
        copy = self.ssh / 'config.shared'
        self.assertFalse(copy.is_symlink())
        self.assert_ok(self.run_script('status'))
        self.source.write_text('Host dev-server\n    User updated-user\n')
        self.assertIn('user example-user\n', self.effective())
        self.assertNotEqual(self.run_script(options=options).returncode, 0)
        self.assertNotEqual(self.run_script('status').returncode, 0)
        self.assert_ok(self.run_script('replace', options=options))
        backup, = self.home.glob('.ssh-config-backup-*')
        self.assertIn('example-user', (backup / 'config.shared').read_text())
        copy.write_text('Host dev-server\n    User hand-edited\n')
        self.assertNotEqual(self.run_script(options=options).returncode, 0)
        self.assertIn('hand-edited', copy.read_text())
        self.assert_ok(self.run_script('status', source=False))

    def test_invalid_or_missing_source_leaves_existing_configuration_intact(self):
        self.ssh.mkdir()
        config = self.ssh / 'config'
        config.write_text('Host old-server\n    User old-user\n')
        self.source.write_text('ThisOptionDoesNotExist yes\n')
        result = self.run_script('replace')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(config.read_text(), 'Host old-server\n    User old-user\n')
        self.assertEqual(list(self.home.glob('.ssh-config-backup-*')), [])
        self.assertEqual(sorted(p.name for p in self.ssh.iterdir()), ['config'])
        self.source.unlink()
        self.assertNotEqual(self.run_script('replace').returncode, 0)

    def test_broken_installed_link_and_modified_entry_are_reported(self):
        self.assert_ok(self.run_script())
        self.source.unlink()
        result = self.run_script('status', source=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('broken', result.stderr)
        (self.ssh / 'config').write_text('Host custom\n')
        self.assertNotEqual(self.run_script('status', source=False).returncode, 0)

    def test_discovery_no_source_multiple_candidates_and_explicit_path(self):
        self.assertNotEqual(self.run_script(source=False).returncode, 0)
        self.assert_ok(self.run_script(source=False, answers='\n'))
        candidates = []
        for directory in ('Seafile/server-sync', 'server-sync'):
            path = self.home / directory / 'config/ssh/hosts.conf'
            path.parent.mkdir(parents=True)
            shutil.copy2(self.source, path)
            candidates.append(path)
        self.assert_ok(self.run_script(source=False, answers='2\n'))
        self.assertEqual((self.ssh / 'config.shared').resolve(), candidates[1].resolve())
        # An invalid explicit source must not fall back to discoverable candidates.
        self.source.unlink()
        self.assertNotEqual(self.run_script().returncode, 0)

    def test_single_candidate_confirmation_and_manual_path(self):
        path = self.home / 'Seafile/server-sync/config/ssh/hosts.conf'
        path.parent.mkdir(parents=True)
        shutil.copy2(self.source, path)
        self.assert_ok(self.run_script(source=False, answers='n\n\n'))
        self.assertFalse(self.ssh.exists())
        self.assert_ok(self.run_script(source=False, answers='y\n'))
        self.assertEqual((self.ssh / 'config.shared').resolve(), path.resolve())

    def test_manual_source_path_and_source_inside_ssh_are_checked(self):
        self.assert_ok(self.run_script(source=False, answers=str(self.source) + '\n'))
        internal = self.ssh / 'internal.conf'
        internal.write_text('Host internal-server\n')
        result = self.run_script(options=['--source', str(internal)])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('outside ~/.ssh', result.stderr)

    def test_discovery_deduplicates_directory_aliases(self):
        path = self.home / 'Projects/server-sync/config/ssh/hosts.conf'
        path.parent.mkdir(parents=True)
        shutil.copy2(self.source, path)
        alias = self.home / 'projects'
        if not alias.exists():  # macOS may already treat Projects and projects as the same path.
            alias.symlink_to(self.home / 'Projects', target_is_directory=True)
        result = self.run_script(source=False, answers='y\n')
        self.assert_ok(result)
        self.assertNotIn('1) ', result.stdout)

    def test_failed_creation_does_not_remove_a_file_created_by_someone_else(self):
        mock = self.root / 'mock'
        mock.mkdir()
        real_ln = shutil.which('ln')
        wrapper = mock / 'ln'
        wrapper.write_text('#!/bin/bash\n'
                           'if [[ "$1" != -s && "$1" != -P ]]; then\n'
                           '  printf "external edit\\n" > "$HOME/.ssh/config"\n'
                           'fi\n'
                           f'exec "{real_ln}" "$@"\n')
        wrapper.chmod(0o755)
        result = self.run_script(env=dict(self.env, PATH=f'{mock}:{os.environ["PATH"]}'))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.ssh / 'config').read_text(), 'external edit\n')
        self.assertFalse((self.ssh / 'config.shared').exists())

    def test_rollback_after_final_validation_failure(self):
        self.ssh.mkdir()
        config = self.ssh / 'config'
        config.write_text('Host old-server\n    User old-user\n')
        mock = self.root / 'mock'
        mock.mkdir()
        real_ssh = shutil.which('ssh')
        wrapper = mock / 'ssh'
        # Allow staging validation, fail once after activation, then let inspection work.
        wrapper.write_text('#!/bin/bash\n'
                           'if [[ "$4" = "$(cd "$HOME" && pwd -P)/.ssh/config" ]]; then exit 17; fi\n'
                           f'exec "{real_ssh}" "$@"\n')
        wrapper.chmod(0o755)
        result = self.run_script('replace', env=dict(self.env, PATH=f'{mock}:{os.environ["PATH"]}'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('restoring previous', result.stderr)
        self.assertEqual(config.read_text(), 'Host old-server\n    User old-user\n')
        self.assertFalse((self.ssh / 'config.shared').exists())
        self.assertEqual(sorted(p.name for p in self.ssh.iterdir()), ['config'])

    def test_backup_failure_does_not_activate_new_files(self):
        self.ssh.mkdir()
        config = self.ssh / 'config'
        config.write_text('Host old-server\n')
        mock = self.root / 'mock'
        mock.mkdir()
        wrapper = mock / 'cp'
        wrapper.write_text('#!/bin/sh\nexit 19\n')
        wrapper.chmod(0o755)
        result = self.run_script('replace', env=dict(self.env, PATH=f'{mock}:{os.environ["PATH"]}'))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(config.read_text(), 'Host old-server\n')
        self.assertFalse((self.ssh / 'config.shared').exists())


if __name__ == '__main__':
    unittest.main()
