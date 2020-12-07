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
import os.path
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

from redhatPatching import redhatPatching
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
    
    def install_adal(self):
        # epel-release and python-pip >= version 8.1 are adal prerequisites
        # https://github.com/AzureAD/azure-activedirectory-library-for-python/
        self.command_executor.Execute("yum install -y epel-release")
        self.command_executor.Execute("yum install -y python-pip")
        self.command_executor.Execute("python -m pip install --upgrade pip")
        self.command_executor.Execute("python -m pip install adal")

    def install_extras(self):
        packages = ['cryptsetup',
                    'lsscsi',
                    'psmisc',
                    'cryptsetup-reencrypt',
                    'lvm2',
                    'uuid',
                    'at',
                    'patch',
                    'procps-ng',
                    'util-linux',
                    'pyparted']

        if self.distro_info[1].startswith("6."):
            packages.add('python-six')
            packages.remove('cryptsetup')
            packages.remove('procps-ng')
            packages.remove('util-linux')

        if self.command_executor.Execute("rpm -q " + " ".join(packages)):
            self.command_executor.Execute("yum install -y " + " ".join(packages))

    def update_prereq(self):
        if (self.distro_info[1].startswith('7.')):
            dracut_repack_needed = False

            if os.path.exists("/lib/dracut/modules.d/91lvm/"):
                # If 90lvm already exists 91lvm will cause problems, so remove it.
                if os.path.exists("/lib/dracut/modules.d/90lvm/"):
                    shutil.rmtree("/lib/dracut/modules.d/91lvm/")
                else:
                    os.rename("/lib/dracut/modules.d/91lvm/","/lib/dracut/modules.d/90lvm/")
                dracut_repack_needed = True

            if redhatPatching.is_old_patching_system():
                redhatPatching.remove_old_patching_system(self.logger, self.command_executor)
                dracut_repack_needed = True

            if os.path.exists("/lib/dracut/modules.d/91ade/"):
                shutil.rmtree("/lib/dracut/modules.d/91ade/")
                dracut_repack_needed = True

            if os.path.exists("/dev/mapper/osencrypt"):
                #TODO: only do this if needed (if code and existing module are different)
                redhatPatching.add_91_ade_dracut_module(self.command_executor)
                dracut_repack_needed = True

            if dracut_repack_needed:
                self.command_executor.ExecuteInBash("/usr/sbin/dracut -f -v --kver `grubby --default-kernel | sed 's|/boot/vmlinuz-||g'`", True)
