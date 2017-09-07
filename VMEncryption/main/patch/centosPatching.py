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

    def install_extras(self):
        epel_packages_installed = False
        attempt = 0

        while not epel_packages_installed:
            attempt += 1
            self.logger.log("Attempt #{0} to locate EPEL packages".format(attempt))
            if self.distro_info[1].startswith("6."):
                if self.command_executor.Execute("rpm -q ntfs-3g python-pip"):
                    epel_cmd = "yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-6.noarch.rpm"

                    if self.command_executor.Execute("rpm -q epel-release"):
                        self.command_executor.Execute(epel_cmd)

                    self.command_executor.Execute("yum install -y ntfs-3g python-pip")

                    if not self.command_executor.Execute("rpm -q ntfs-3g python-pip"):
                        epel_packages_installed = True
                else:
                    epel_packages_installed = True
            else:
                if self.command_executor.Execute("rpm -q ntfs-3g python2-pip"):
                    epel_cmd = "yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm"

                    if self.command_executor.Execute("rpm -q epel-release"):
                        self.command_executor.Execute(epel_cmd)

                    self.command_executor.Execute("yum install -y ntfs-3g python2-pip")

                    if not self.command_executor.Execute("rpm -q ntfs-3g python2-pip"):
                        epel_packages_installed = True
                else:
                    epel_packages_installed = True

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
                    'gcc',
                    'python-six',
                    'pyparted',
                    'libffi-devel',
                    'openssl-devel',
                    'python-devel']

        if self.distro_info[1].startswith("6."):
            packages.remove('cryptsetup')
            packages.remove('procps-ng')
            packages.remove('util-linux')

        if self.command_executor.Execute("rpm -q " + " ".join(packages)):
            self.command_executor.Execute("yum install -y " + " ".join(packages))

        if self.command_executor.Execute("pip show adal"):
            self.command_executor.Execute("pip install --upgrade six")
            self.command_executor.Execute("pip install adal")
