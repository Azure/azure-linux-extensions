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

import os
import os.path
import sys
import base64
import re
import json
import platform
import shutil
import time
import traceback
import datetime
import subprocess

from .redhatPatching import redhatPatching
from Common import *
from CommandExecutor import *

class centosPatching(redhatPatching):
    def __init__(self, logger, distro_info):
        super(centosPatching, self).__init__(logger, distro_info)
        self.logger = logger
        self.command_executor = CommandExecutor(logger)
        if distro_info[1] in ["6.9", "6.8", "6.7", "6.6", "6.5"]:
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
        else:
            self.base64_path = '/usr/bin/base64'
            self.bash_path = '/usr/bin/bash'
            self.blkid_path = '/usr/bin/blkid'
            self.cat_path = '/bin/cat'
            self.cryptsetup_path = '/usr/sbin/cryptsetup'
            self.dd_path = '/usr/bin/dd'
            self.e2fsck_path = '/sbin/e2fsck'
            self.echo_path = '/usr/bin/echo'
            self.lsblk_path = '/usr/bin/lsblk'
            self.lsscsi_path = '/usr/bin/lsscsi'
            self.mkdir_path = '/usr/bin/mkdir'
            self.mount_path = '/usr/bin/mount'
            self.openssl_path = '/usr/bin/openssl'
            self.resize2fs_path = '/sbin/resize2fs'
            self.umount_path = '/usr/bin/umount'
        
        self.min_version_online_encryption = '8.1'
        self.support_online_encryption = self.validate_online_encryption_support()
        self.grub_cfg_paths = [
            ("/boot/grub2/grub.cfg", "/boot/grub2/grubenv"),
            ("/boot/efi/EFI/redhat/grub.cfg", "/boot/efi/EFI/redhat/grubenv"), # Keep for now for older images
            ("/boot/efi/EFI/centos/grub.cfg", "/boot/efi/EFI/centos/grubenv")
        ]

    def install_cryptsetup(self):
        if self.distro_info[1].startswith("6."):
            packages = ['cryptsetup-reencrypt']
        else:
            packages = ['cryptsetup']

        if self.command_executor.Execute("rpm -q " + " ".join(packages)):
            return_code = self.command_executor.Execute("yum install -y " + " ".join(packages), timeout=100)
            if return_code == -9:
                msg = "Command: yum install timed out. Make sure yum is configured correctly and there are no network problems."
                raise Exception(msg)
            return return_code        

    def install_extras(self):
        packages = ['cryptsetup',
                    'lsscsi',
                    'psmisc',
                    'lvm2',
                    'uuid',
                    'at',
                    'patch',
                    'procps-ng',
                    'util-linux',
                    'pyparted']

        if self.distro_info[1].startswith("6."):
            packages.append('cryptsetup-reencrypt')
            packages.append('python-six')
            packages.remove('cryptsetup')
            packages.remove('procps-ng')
            packages.remove('util-linux')

        if self.command_executor.Execute("rpm -q " + " ".join(packages)):
            self.command_executor.Execute("yum install -y " + " ".join(packages))

