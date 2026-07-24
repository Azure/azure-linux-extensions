#!/usr/bin/env python
#
# Copyright 2014 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)
sys.path.insert(0, os.path.dirname(root))

from VMAccess import vmaccess


class TestValidatePathSafe(unittest.TestCase):
    @patch('os.path.exists', return_value=False)
    @patch('os.path.islink', return_value=True)
    def test_rejects_symlink(self, mock_islink, mock_exists):
        with self.assertRaises(Exception) as ctx:
            vmaccess._validate_path_safe('/home/user/.ssh', 1000, 'user')
        self.assertIn('symlink', str(ctx.exception))

    @patch('os.lstat')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.islink', return_value=False)
    def test_rejects_wrong_owner(self, mock_islink, mock_exists, mock_lstat):
        mock_lstat.return_value = MagicMock(st_uid=9999)
        with self.assertRaises(Exception) as ctx:
            vmaccess._validate_path_safe('/home/user/.ssh', 1000, 'user')
        self.assertIn('not owned by', str(ctx.exception))

    @patch('os.lstat')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.islink', return_value=False)
    def test_allows_root_owned(self, mock_islink, mock_exists, mock_lstat):
        mock_lstat.return_value = MagicMock(st_uid=0)
        vmaccess._validate_path_safe('/home/user/.ssh', 1000, 'user')

    @patch('os.lstat')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.islink', return_value=False)
    def test_allows_correct_owner(self, mock_islink, mock_exists, mock_lstat):
        mock_lstat.return_value = MagicMock(st_uid=1000)
        vmaccess._validate_path_safe('/home/user/.ssh', 1000, 'user')


class TestIsSshdConfigModified(unittest.TestCase):
    def test_returns_false_when_none(self):
        self.assertFalse(vmaccess._is_sshd_config_modified(None))

    def test_returns_false_when_empty_dict(self):
        self.assertFalse(vmaccess._is_sshd_config_modified({}))

    def test_returns_true_when_password_set(self):
        self.assertTrue(vmaccess._is_sshd_config_modified({'password': 'x'}))

    def test_returns_true_when_reset_ssh(self):
        self.assertTrue(vmaccess._is_sshd_config_modified({'reset_ssh': True}))

    def test_returns_true_when_restore_backup_ssh(self):
        self.assertTrue(vmaccess._is_sshd_config_modified({'restore_backup_ssh': True}))


class TestValidateSshPathKeyError(unittest.TestCase):
    @patch('pwd.getpwnam', side_effect=KeyError('nouser'))
    def test_raises_on_nonexistent_user(self, mock_pwd):
        with self.assertRaises(KeyError):
            vmaccess.validate_ssh_path('/home/nouser/.ssh/authorized_keys', 'nouser')


class TestSafeWriteAuthorizedKeys(unittest.TestCase):
    @patch('os.close')
    @patch('os.write')
    @patch('os.open', return_value=5)
    @patch('os.path.exists', return_value=False)
    @patch('VMAccess.vmaccess.ext_utils.encode_for_writing_to_file', return_value=b'ssh-rsa AAA\n')
    def test_creates_with_excl_flag_when_new(self, mock_enc, mock_exists, mock_open, mock_write, mock_close):
        vmaccess.safe_write_authorized_keys('/home/u/.ssh/authorized_keys', 'ssh-rsa AAA\n', append=False)
        flags = mock_open.call_args[0][1]
        self.assertTrue(flags & os.O_CREAT)
        self.assertTrue(flags & os.O_EXCL)
        self.assertTrue(flags & os.O_NOFOLLOW)

    @patch('os.close')
    @patch('os.write')
    @patch('os.open', return_value=5)
    @patch('os.path.exists', return_value=True)
    @patch('VMAccess.vmaccess.ext_utils.encode_for_writing_to_file', return_value=b'ssh-rsa AAA\n')
    def test_append_uses_nofollow(self, mock_enc, mock_exists, mock_open, mock_write, mock_close):
        vmaccess.safe_write_authorized_keys('/home/u/.ssh/authorized_keys', 'ssh-rsa AAA\n', append=True)
        flags = mock_open.call_args[0][1]
        self.assertTrue(flags & os.O_APPEND)
        self.assertTrue(flags & os.O_NOFOLLOW)


if __name__ == '__main__':
    unittest.main()
