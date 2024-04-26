#!/usr/bin/python
#
# AbstractPatching is the base patching class of all the linux distros
#
# Copyright (C) Microsoft Corporation
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
import io
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
from distutils.version import LooseVersion
class AbstractPatching(object):
    """
    AbstractPatching defines a skeleton neccesary for a concrete Patching class.
    """
    def __init__(self, distro_info):
        self.distro_info = distro_info
        self.base64_path = '/usr/bin/base64'
        self.bash_path = '/bin/bash'
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
        self.kernel_version = platform.release()
        self.min_version_online_encryption = ''
        self.support_online_encryption = False

    def install_cryptsetup(self):
        pass

    def install_extras(self):
        pass

    def install_azguestattestation(self):
        pass

    def update_prereq(self):
        pass

    def validate_online_encryption_support(self):
        distro_version = self.distro_info[1]
        if len(self.min_version_online_encryption) > 0 and LooseVersion(distro_version) >= LooseVersion(self.min_version_online_encryption):
            self.logger.log("Distro {0} {1} is a candidate for online encryption.".format(self.distro_info[0], distro_version))
            return True
        return False
    
    def pack_initial_root_fs(self):
        pass

    def add_kernelopts(self, args_to_add):
        pass

    def add_args_to_default_grub(self, args_to_add):
        self.append_contents_to_file('\nGRUB_CMDLINE_LINUX+=" {0} "\n'.format(" ".join(args_to_add)),
                                      '/etc/default/grub')

    def install_and_enable_ade_online_enc(self, root_partuuid, boot_uuid, rootfs_disk, is_os_disk_lvm):
        pass

    def append_contents_to_file(self, contents, path):
        # Python 3.x strings are Unicode by default and do not use decode
        if sys.version_info[0] < 3:
            if isinstance(contents, str):
                contents = contents.decode('utf-8')

        with io.open(path, 'a') as f:
            f.write(contents)