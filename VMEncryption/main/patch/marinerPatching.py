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
import inspect

from AbstractPatching import AbstractPatching
from Common import *
from CommandExecutor import *

class marinerPatching(AbstractPatching):
    def __init__(self, logger, distro_info):
        super(marinerPatching, self).__init__(distro_info)
        self.logger = logger
        self.command_executor = CommandExecutor(logger)
        self.distro_info = distro_info
        self.base64_path = '/usr/bin/base64'
        self.bash_path = '/usr/bin/bash'
        self.blkid_path = '/usr/bin/blkid'
        self.cat_path = '/bin/cat'
        self.cryptsetup_path = '/usr/sbin/cryptsetup'
        self.dd_path = '/usr/bin/dd'
        self.e2fsck_path = '/sbin/e2fsck'
        self.echo_path = '/usr/bin/echo'
        self.getenforce_path = '/usr/sbin/getenforce'
        self.setenforce_path = '/usr/sbin/setenforce'
        self.lsblk_path = '/usr/bin/lsblk'
        self.lsscsi_path = '/usr/bin/lsscsi'
        self.mkdir_path = '/usr/bin/mkdir'
        self.mount_path = '/usr/bin/mount'
        self.openssl_path = '/usr/bin/openssl'
        self.resize2fs_path = '/sbin/resize2fs'
        self.touch_path = '/usr/bin/touch'
        self.umount_path = '/usr/bin/umount'

    def install_cryptsetup(self):
        packages = ['cryptsetup']

        if self.command_executor.Execute("rpm -q " + " ".join(packages)):
            return_code = self.command_executor.Execute("tdnf install -y " + " ".join(packages), timeout=100)
            if return_code == -9:
                msg = "Command: tdnf install timed out. Make sure tdnf is configured correctly and there are no network problems."
                raise Exception(msg)
            return return_code

    def install_adal(self):
        self.command_executor.Execute('tdnf install -y python2')
        self.command_executor.Execute('tdnf install -y python-pip')
        self.command_executor.Execute('python -m pip install --upgrade pip')
        self.command_executor.Execute('python -m pip install adal')

    def install_extras(self):
        packages = ['at',
                    'cryptsetup',
                    'lsscsi',
                    'lvm2',
                    'patch',
                    'procps-ng',
                    'psmisc',
                    'python-six',
                    'util-linux',
                    'uuid']

        if self.command_executor.Execute("rpm -q " + " ".join(packages)):
            self.command_executor.Execute("tdnf install -y " + " ".join(packages))

    def update_prereq(self):
        pass