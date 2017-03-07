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
        self.command_executor.ExecuteInBash('[ -e "/boot/luks" ]', True)

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
            self.command_executor.Execute('systemctl restart walinuxagent')

            self.context.logger.log("Pivoted back into memroot successfully")

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit patch_boot_system state")

        return super(PatchBootSystemState, self).should_exit()

    def _append_contents_to_file(self, contents, path):
        with open(path, 'a') as f:
            f.write(contents)

    def _modify_pivoted_oldroot(self):
        self.context.logger.log("Pivoted into oldroot successfully")

        scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        encryptscriptsdir = os.path.join(scriptdir, '../encryptscripts')
        injectscriptpath = os.path.join(encryptscriptsdir, 'inject_luks_header.sh')

        if not os.path.exists(injectscriptpath):
            message = "Inject-script not found at path: {0}".format(injectscriptpath)
            self.context.logger.log(message)
            raise Exception(message)
        else:
            self.context.logger.log("Inject-script found at path: {0}".format(injectscriptpath))

        self.command_executor.Execute('cp {0} /usr/share/initramfs-tools/hooks/luksheader'.format(injectscriptpath), True)
        self.command_executor.Execute('chmod +x /usr/share/initramfs-tools/hooks/luksheader', True)

        scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        patchesdir = os.path.join(scriptdir, '../encryptpatches')
        patchpath = os.path.join(patchesdir, 'ubuntu_1604_initramfs.patch')

        if not os.path.exists(patchpath):
            message = "Patch not found at path: {0}".format(patchpath)
            self.context.logger.log(message)
            raise Exception(message)
        else:
            self.context.logger.log("Patch found at path: {0}".format(patchpath))
        
        self.command_executor.ExecuteInBash('patch -b -d /usr/share/initramfs-tools/hooks -p1 <{0}'.format(patchpath), True)
        
        entry = 'osencrypt /dev/sda1 none luks,discard,header=/boot/luks/osluksheader,keyscript=/usr/sbin/azure_crypt_key.sh'
        self._append_contents_to_file(entry, '/etc/crypttab')

        self.command_executor.Execute('update-initramfs -u -k all', True)
        self.command_executor.Execute('update-grub', True)
        self.command_executor.Execute('grub-install --recheck --force {0}'.format(self.rootfs_disk), True)

    def _get_uuid(self, partition_name):
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(command_to_execute="blkid -s UUID -o value {0}".format(partition_name),
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)
        return proc_comm.stdout.strip()
