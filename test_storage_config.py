import os
import tempfile
import unittest
from unittest.mock import patch
from storage_config import configure_storage


class StorageConfigTests(unittest.TestCase):
    def test_only_music_root_is_sufficient(self):
        with tempfile.TemporaryDirectory() as root:
            env = {'MUSIC_ROOT': root}
            self.assertEqual(configure_storage(env), 'host')
            self.assertEqual(env['MUSIC_ROOT'], root)
            self.assertEqual(env['STORAGE_MODE'], 'local')

    def test_no_parent_or_default_fallback(self):
        for root in ('', 'Audio', '/nonexistent-mp3z-audio-test'):
            with self.assertRaises(ValueError):
                configure_storage({'STORAGE_MODE': 'host', 'MUSIC_ROOT': root})

    def test_smb_does_not_inspect_host_root(self):
        env = dict(STORAGE_MODE='smb', MUSIC_ROOT='/nonexistent', SMB_HOST='nas',
                   SMB_SHARE='music', SMB_USER='user', SMB_PASS='test-only', SMB_PATH='Audio')
        with patch('storage_config.Path.is_dir', side_effect=AssertionError('Host touched')):
            self.assertEqual(configure_storage(env), 'smb')
        self.assertEqual(env['MUSIC_ROOT'], '')

    def test_smb_never_falls_back_to_host(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                configure_storage({'STORAGE_MODE': 'smb', 'MUSIC_ROOT': root})

    def test_inactive_smb_port_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            env = {'STORAGE_MODE': 'host', 'MUSIC_ROOT': root, 'SMB_PORT': 'not-a-port'}
            configure_storage(env)
            self.assertEqual(env['SMB_PORT'], '445')

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            configure_storage({'STORAGE_MODE': 'both'})

    def test_smb_path_cannot_escape_share(self):
        for base in ('../Video', '/Audio', 'C:/Audio', 'bad\x00name'):
            env = dict(STORAGE_MODE='smb', SMB_HOST='nas', SMB_SHARE='music',
                       SMB_USER='user', SMB_PASS='test-only', SMB_PATH=base)
            with self.assertRaises(ValueError):
                configure_storage(env)


if __name__ == '__main__':
    unittest.main()
