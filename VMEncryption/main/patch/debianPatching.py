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


class debianPatching(AbstractPatching):
    def __init__(self, logger, distro_info):
        super(debianPatching, self).__init__(distro_info)
        self.logger = logger
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

    def install_adal(self):
        pass

    def install_extras(self):
        pass

    def update_prereq(self):
        pass