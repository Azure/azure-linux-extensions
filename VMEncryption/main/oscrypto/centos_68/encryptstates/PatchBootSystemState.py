#!/usr/bin/env python
#
# VM Backup extension
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
# Requires Python 2.7+
#

import inspect
import re
import os
import sys

from time import sleep
from OSEncryptionState import *

class PatchBootSystemState(OSEncryptionState):
    def __init__(self, context):
        super(PatchBootSystemState, self).__init__('PatchBootSystemState', context)

    def should_enter(self):
        self.context.logger.log("Verifying if machine should enter patch_boot_system state")

        if not super(PatchBootSystemState, self).should_enter():
            return False
        
        self.context.logger.log("Performing enter checks for patch_boot_system state")

        self.command_executor.Execute('mount /dev/mapper/osencrypt /oldroot', True)
        self.command_executor.Execute('umount /oldroot', True)
                
        return True

    def enter(self):
        if not self.should_enter():
            return

        self.context.logger.log("Entering patch_boot_system state")

        self.command_executor.Execute('mount /boot', False)
        self.command_executor.Execute('mount /dev/mapper/osencrypt /oldroot', True)
        self.command_executor.Execute('mount --make-rprivate /', True)
        self.command_executor.Execute('mkdir /oldroot/memroot', True)
        self.command_executor.Execute('pivot_root /oldroot /oldroot/memroot', True)

        self.command_executor.ExecuteInBash('for i in dev proc sys boot; do mount --move /memroot/$i /$i; done', True)

        try:
            self._modify_pivoted_oldroot()
        except Exception as e:
            self.command_executor.Execute('mount --make-rprivate /')
            self.command_executor.Execute('pivot_root /memroot /memroot/oldroot')
            self.command_executor.Execute('rmdir /oldroot/memroot')
            self.command_executor.ExecuteInBash('for i in dev proc sys boot; do mount --move /oldroot/$i /$i; done')

            raise
        else:
            self.command_executor.Execute('mount --make-rprivate /')
            self.command_executor.Execute('pivot_root /memroot /memroot/oldroot')
            self.command_executor.Execute('rmdir /oldroot/memroot')
            self.command_executor.ExecuteInBash('for i in dev proc sys boot; do mount --move /oldroot/$i /$i; done')

            extension_full_name = 'Microsoft.Azure.Security.' + CommonVariables.extension_name
            self.command_executor.Execute('cp -ax' +
                                          ' /var/log/azure/{0}'.format(extension_full_name) +
                                          ' /oldroot/var/log/azure/{0}.Stripdown'.format(extension_full_name),
                                          True)
            self.command_executor.Execute('umount /boot')
            self.command_executor.Execute('umount /oldroot')

            self.context.logger.log("Pivoted back into memroot successfully, restarting WALA")

            self.command_executor.Execute('service sshd restart')
            self.command_executor.Execute('service atd restart')

            with open("/restart-wala.sh", "w") as f:
                f.write("service waagent restart\n")

            with open("/delete-lock.sh", "w") as f:
                f.write("rm -f /var/lib/azure_disk_encryption_config/daemon_lock_file.lck\n")

            self.command_executor.Execute('at -f /delete-lock.sh now + 1 minutes', True)
            self.command_executor.Execute('at -f /restart-wala.sh now + 2 minutes', True)

            self.should_exit()

            self.command_executor.ExecuteInBash('pkill -f .*ForLinux.*handle.py.*daemon.*', True)

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit patch_boot_system state")

        return super(PatchBootSystemState, self).should_exit()

    def _append_contents_to_file(self, contents, path):
        with open(path, 'a') as f:
            f.write(contents)

    def _modify_pivoted_oldroot(self):
        self.context.logger.log("Pivoted into oldroot successfully")

        scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        patchesdir = os.path.join(scriptdir, '../encryptpatches')
        patchpath = os.path.join(patchesdir, 'centos_68_dracut.patch')

        if not os.path.exists(patchpath):
            message = "Patch not found at path: {0}".format(patchpath)
            self.context.logger.log(message)
            raise Exception(message)
        else:
            self.context.logger.log("Patch found at path: {0}".format(patchpath))

        self.disk_util.remove_mount_info('/')
        self.disk_util.append_mount_info('/dev/mapper/osencrypt', '/')

        self.command_executor.ExecuteInBash('patch -b -d /usr/share/dracut/modules.d/90crypt -p1 <{0}'.format(patchpath), True)

        self._append_contents_to_file('\nadd_drivers+=" fuse vfat nls_cp437 nls_iso8859-1"\n',
                                      '/etc/dracut.conf')
        self._append_contents_to_file('\nadd_dracutmodules+=" crypt"\n',
                                      '/etc/dracut.conf')

        self.command_executor.Execute('/sbin/dracut -f -v', True)
        self.command_executor.ExecuteInBash('mv -f /boot/initramfs* /boot/boot/', True)

        with open("/boot/boot/grub/grub.conf", "r") as f:
            contents = f.read()

        contents = re.sub(r"rd_NO_LUKS ", r"", contents)
        contents = re.sub(r"root=(.*?)\s", r"root=/dev/mapper/osencrypt rd_LUKS_UUID=osencrypt rdinitdebug ", contents)
        contents = re.sub(r"hd0,0", r"hd0,1", contents)

        with open("/boot/boot/grub/grub.conf", "w") as f:
            f.write(contents)

        grub_input = "root (hd0,1)\nsetup (hd0)\nquit\n"
        self.command_executor.Execute('grub', input=grub_input, raise_exception_on_failure=True)
