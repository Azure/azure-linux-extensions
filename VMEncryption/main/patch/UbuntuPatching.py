#!/usr/bin/python
#
# Copyright 2015 Microsoft Corporation
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
#
# Requires Python 2.4+


import os
import sys
import imp
import base64
import re
import json
import platform
import shutil
import time
import traceback
import datetime
import subprocess

from AbstractPatching import AbstractPatching
try:
    from Common import *
except Exception:
    from ..Common import * # Added for unit test
try:
    from CommandExecutor import *
except Exception:
    from ..CommandExecutor import * # Added for unit test


class UbuntuPatching(AbstractPatching):
    def __init__(self, logger, distro_info):
        super(UbuntuPatching, self).__init__(distro_info)
        self.logger = logger
        self.command_executor = CommandExecutor(logger)
        self.base64_path = '/usr/bin/base64'
        self.bash_path = '/bin/bash'
        self.blkid_path = '/sbin/blkid'
        self.cat_path = '/bin/cat'
        self.cryptsetup_path = '/sbin/cryptsetup'
        self.dd_path = '/bin/dd'
        self.e2fsck_path = '/sbin/e2fsck'
        self.echo_path = '/bin/echo'
        self.lsblk_path = '/bin/lsblk'
        self.lsscsi_path = '/usr/bin/lsscsi'
        self.mkdir_path = '/bin/mkdir'
        self.mount_path = '/bin/mount'
        self.openssl_path = '/usr/bin/openssl'
        self.resize2fs_path = '/sbin/resize2fs'
        self.umount_path = '/bin/umount'
        self.touch_path = '/usr/bin/touch'

    def install_adal(self):
        return_code = self.command_executor.Execute('apt-get install -y python-pip')
        # If install fails, try running apt-get update and then try install again
        if return_code != 0:
            self.logger.log('python-pip installation failed. Retrying installation after running update')
            return_code = self.command_executor.Execute('apt-get -o Acquire::ForceIPv4=true -y update', timeout=30)
            # Fail early if apt-get update times out.
            if return_code == -9:
                msg = "Command: apt-get -o Acquire::ForceIPv4=true -y update timed out. Make sure apt-get is configured correctly."
                raise Exception(msg)
            self.command_executor.Execute('apt-get install -y python-pip')
        self.command_executor.Execute('python -m pip install --upgrade pip')
        self.command_executor.Execute('python -m pip install --upgrade setuptools')
        self.command_executor.Execute('python -m pip install adal')

    def install_extras(self):
        """
        install the sg_dd because the default dd do not support the sparse write
        """
        packages = ['at',
                    'cryptsetup-bin',
                    'lsscsi',
                    'python-parted',
                    'python-six',
                    'procps',
                    'psmisc']

        cmd = " ".join(['apt-get', 'install', '-y'] + packages)
        return_code = self.command_executor.Execute(cmd)

        # If install fails, try running apt-get update and then try install again
        if return_code != 0:
            self.logger.log('prereq packages installation failed. Retrying installation after running update')
            return_code = self.command_executor.Execute('apt-get -o Acquire::ForceIPv4=true -y update')
            # Fail early if apt-get update times out.
            if return_code == -9:
                msg = "Command: apt-get -o Acquire::ForceIPv4=true -y update timed out. Make sure apt-get is configured correctly."
                raise Exception(msg)
            cmd = " ".join(['apt-get', 'install', '-y'] + packages)
            self.command_executor.Execute(cmd)
        
    def update_prereq(self):
        self.logger.log("Trying to update Ubuntu osencrypt entry.")
        filtered_crypttab_lines = []
        initramfs_repack_needed = False
        if not os.path.exists('/etc/crypttab'):
            return
        with open('/etc/crypttab', 'r') as f:
            for line in f.readlines():
                crypttab_parts = line.strip().split()

                if len(crypttab_parts) < 3:
                    filtered_crypttab_lines.append(line)
                    continue

                if crypttab_parts[0].startswith("#"):
                    filtered_crypttab_lines.append(line)
                    continue

                if crypttab_parts[0] == 'osencrypt' and crypttab_parts[1] == '/dev/sda1' and 'keyscript=/usr/sbin/azure_crypt_key.sh' in line:
                    self.logger.log("Found osencrypt entry to update.")
                    if os.path.exists('/dev/disk/azure/root-part1'):
                        filtered_crypttab_lines.append(CommonVariables.osencrypt_crypttab_line_ubuntu)
                        initramfs_repack_needed = True
                        continue
                    else:
                        self.logger.log("Cannot find expected link to root partition.")

                filtered_crypttab_lines.append(line)

        if initramfs_repack_needed:
            with open('/etc/crypttab', 'w') as f:
                f.writelines(filtered_crypttab_lines)
            self.command_executor.Execute('update-initramfs -u -k all', True)
            self.logger.log("Successfully updated osencrypt entry.")
        else:
            self.logger.log('osencrypt entry not present or already updated or expected root partition link does not exists.')