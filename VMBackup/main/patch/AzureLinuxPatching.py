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


import subprocess
from patch.AbstractPatching import AbstractPatching
from common import *


class AzureLinuxPatching(AbstractPatching):
    def __init__(self,logger,distro_info):
        super(AzureLinuxPatching,self).__init__(distro_info)
        self.logger = logger
        self.base64_path = '/usr/bin/base64'
        self.bash_path = '/usr/bin/bash'
        self.blkid_path = '/usr/bin/blkid'
        self.cat_path = '/usr/bin/cat'
        self.cryptsetup_path = '/usr/bin/cryptsetup'
        self.dd_path = '/usr/bin/dd'
        self.e2fsck_path = '/usr/bin/e2fsck'
        self.echo_path = '/usr/bin/echo'
        self.getenforce_path = '/usr/bin/getenforce'
        self.setenforce_path = '/usr/bin/setenforce'
        self.lsblk_path = '/usr/bin/lsblk'
        self.usr_flag = 1
        self.lsscsi_path = '/usr/bin/lsscsi'
        self.mkdir_path = '/usr/bin/mkdir'
        self.mount_path = '/usr/bin/mount'
        self.openssl_path = '/usr/bin/openssl'
        self.resize2fs_path = '/usr/bin/resize2fs'
        self.umount_path = '/usr/bin/umount'

    def install_extras(self):
        common_extras = ['cryptsetup','lsscsi']
        for extra in common_extras:
            self.logger.log("installation for " + extra + ' result is ' + str(subprocess.call(['dnf', 'install','-y', extra])))
