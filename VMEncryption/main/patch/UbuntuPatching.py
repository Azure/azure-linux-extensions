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
from Common import *
from CommandExecutor import *


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
        pass