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

        if not os.path.exists('/boot/luks'):
            self.command_executor.Execute('mount /boot', True)

        self.command_executor.Execute('mount /dev/mapper/osencrypt /oldroot', True)
        self.command_executor.ExecuteInBash('for i in dev proc sys boot; do mount --bind /$i /oldroot/$i; done', True)
        self.command_executor.Execute('mount --make-rprivate /', True)
        self.command_executor.Execute('mkdir /oldroot/memroot', True)
        self.command_executor.Execute('pivot_root /oldroot /oldroot/memroot', True)

        try:
            self._modify_pivoted_oldroot()
        except Exception as e:
            raise
        finally:
            self.command_executor.Execute('pivot_root /memroot /memroot/oldroot', True)
            self.command_executor.Execute('rmdir /oldroot/memroot', True)
            self.command_executor.ExecuteInBash('for i in dev proc sys boot; do umount /oldroot/$i; done', True)
            self.command_executor.Execute('umount /boot', True)
            self.command_executor.Execute('umount /oldroot', True)

            self.context.logger.log("Pivoted back into memroot successfully")

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit patch_boot_system state")

        return super(PatchBootSystemState, self).should_exit()

    def _modify_pivoted_oldroot(self):
        self.context.logger.log("Pivoted into oldroot successfully")

        scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        patchesdir = os.path.join(scriptdir, '../encryptpatches')
        patchpath = os.path.join(patchesdir, 'rhel-72-dracut.patch')

        if not os.path.exists(patchpath):
            self.context.logger.log("Patch not found at path: {0}".format(patchpath))
        else:
            self.context.logger.log("Patch found at path: {0}".format(patchpath))

        self.command_executor.ExecuteInBash('echo "GRUB_CMDLINE_LINUX+=\" rd.debug rd.luks.uuid=osencrypt\"" >>/etc/default/grub', True)
        self.command_executor.ExecuteInBash('patch -b -d /usr/lib/dracut/modules.d/90crypt -p1 <{0}'.format(patchpath), True)
        self.command_executor.ExecuteInBash('echo add_drivers+=\" vfat nls_cp437 nls_iso8859-1\" >>/etc/dracut.conf', True)
        self.command_executor.ExecuteInBash('echo add_dracutmodules+=\" crypt\" >>/etc/dracut.conf', True)
        self.command_executor.ExecuteInBash('/usr/sbin/dracut -f -v', True)
        self.command_executor.ExecuteInBash('grub2-install /dev/sda', True)
        self.command_executor.ExecuteInBash('grub2-mkconfig -o /boot/grub2/grub.cfg', True)
