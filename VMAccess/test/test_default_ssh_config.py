#!/usr/bin/env python
#
# Copyright 2026 Microsoft Corporation
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
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from VMAccess import vmaccess


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AZURE_LINUX_NAMES = (
    'NAME="Azure Linux"',
    'Azure Linux',
    'AzureLinux',
    'azure linux',
    'NAME="Common Base Linux Mariner"',
    'CBL-Mariner',
    'mariner',
)


class TestDefaultSshConfigFilename(unittest.TestCase):
    def test_azure_linux_and_mariner(self):
        for os_name in AZURE_LINUX_NAMES:
            with self.subTest(os_name=os_name):
                with patch.object(vmaccess, 'OSName', os_name):
                    self.assertEqual(vmaccess._get_default_ssh_config_filename(),
                                     'azurelinux_default')

    def test_existing_distributions(self):
        cases = (
            ('CentOS Linux', 'centos_default'),
            ('Debian GNU/Linux', 'debian_default'),
            ('Fedora Linux', 'fedora_default'),
            ('Red Hat Enterprise Linux', 'redhat_default'),
            ('RedHat Enterprise Linux', 'redhat_default'),
            ('openSUSE', 'SuSE_default'),
            ('Ubuntu', 'ubuntu_default'),
            ('Unknown Linux', 'default'),
            (None, 'default'),
        )
        for os_name, expected in cases:
            with self.subTest(os_name=os_name):
                with patch.object(vmaccess, 'OSName', os_name):
                    self.assertEqual(vmaccess._get_default_ssh_config_filename(), expected)


class TestAzureLinuxSshConfigReset(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config_path = os.path.join(directory.name, 'sshd_config')
        self.backup_path = os.path.join(directory.name, 'backup')
        self.distro = MagicMock(spec=vmaccess.dist_utils.GenericDistro)
        self.hutil = MagicMock()
        patches = (
            patch.multiple(vmaccess, OSName='NAME="Azure Linux"',
                           SshdConfigPath=self.config_path,
                           SshdConfigBackupPath=self.backup_path,
                           MyDistro=self.distro),
            patch.object(vmaccess.os, 'getcwd', return_value=ROOT),
        )
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def read_config(self):
        with open(self.config_path) as config:
            return config.read()

    def test_reset_copies_azure_linux_template(self):
        with open(os.path.join(ROOT, 'resources', 'azurelinux_default')) as template:
            expected = template.read()
        for os_name in AZURE_LINUX_NAMES:
            with self.subTest(os_name=os_name):
                self.distro.reset_mock()
                with patch.object(vmaccess, 'OSName', os_name):
                    vmaccess._reset_sshd_config(self.hutil, False)
                self.assertEqual(self.read_config(), expected)
                self.distro.restart_ssh_service.assert_called_once_with()

    def test_template_preserves_drop_ins_and_sftp(self):
        vmaccess._reset_sshd_config(self.hutil, False)
        config = self.read_config()
        directives = [line.split() for line in config.splitlines()
                      if line.strip() and not line.lstrip().startswith('#')]
        self.assertIn(['Include', '/etc/ssh/sshd_config.d/*.conf'], directives)
        self.assertIn(['Subsystem', 'sftp', '/usr/libexec/openssh/sftp-server'],
                      directives)
        self.assertIn(['AuthorizedKeysFile', '.ssh/authorized_keys'], directives)
        self.assertNotIn('ssh_host_dsa_key', config)
        for directive in directives:
            self.assertNotIn(directive[0].lower(), (
                'passwordauthentication', 'permitrootlogin', 'rsaauthentication',
                'rhostsrsaauthentication', 'useprivilegeseparation',
                'keyregenerationinterval', 'serverkeybits',
            ))

    def test_restore_backup_takes_precedence(self):
        original = 'Port 2222\n'
        with open(self.backup_path, 'w') as backup:
            backup.write(original)
        vmaccess._reset_sshd_config(self.hutil, True)
        self.assertEqual(self.read_config(), original)
        self.assertFalse(os.path.exists(self.backup_path))
        self.distro.restart_ssh_service.assert_called_once_with()

    def test_restore_without_backup_uses_azure_linux_template(self):
        vmaccess._reset_sshd_config(self.hutil, True)
        with open(os.path.join(ROOT, 'resources', 'azurelinux_default')) as template:
            self.assertEqual(self.read_config(), template.read())
        self.distro.restart_ssh_service.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
