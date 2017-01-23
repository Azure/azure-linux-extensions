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

from inspect import ismethod
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

        if not os.path.exists('/dev/mapper/osencrypt'):
            return False
                
        return True

    def enter(self):
        if not self.should_enter():
            return

        self.context.logger.log("Entering patch_boot_system state")

        self.command_executor.Execute('systemctl restart lvm2-lvmetad', True)
        self.command_executor.Execute('pvscan', True)
        self.command_executor.Execute('vgcfgrestore -f /volumes.lvm rootvg', True)
        self.command_executor.Execute('cryptsetup luksClose osencrypt', True)

        self._find_bek_and_execute_action('_luks_open')

        self.unmount_lvm_volumes()
        
        self.command_executor.Execute('mount /dev/rootvg/rootlv /oldroot', True)
        self.command_executor.Execute('mount /dev/rootvg/varlv /oldroot/var', True)
        self.command_executor.Execute('mount /dev/rootvg/usrlv /oldroot/usr', True)
        self.command_executor.Execute('mount /dev/rootvg/tmplv /oldroot/tmp', True)
        self.command_executor.Execute('mount /dev/rootvg/homelv /oldroot/home', True)
        self.command_executor.Execute('mount /dev/rootvg/optlv /oldroot/opt', True)

        self.command_executor.Execute('mount /boot', False)
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
            self.command_executor.Execute('systemctl restart waagent')

            self.context.logger.log("Pivoted back into memroot successfully")

            self.unmount_lvm_volumes()

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit patch_boot_system state")

        return super(PatchBootSystemState, self).should_exit()

    def unmount_lvm_volumes(self):
        self.command_executor.Execute('swapoff -a', True)
        self.command_executor.Execute('umount -a')

        for mountpoint in ['/var', '/opt', '/tmp', '/home', '/usr']:
            if self.command_executor.Execute('mountpoint /oldroot' + mountpoint) == 0:
                self.unmount('/oldroot' + mountpoint)
            if self.command_executor.Execute('mountpoint ' + mountpoint) == 0:
                self.unmount(mountpoint)

        self.unmount_var()

    def unmount_var(self):
        unmounted = False

        while not unmounted:
            self.command_executor.Execute('systemctl stop NetworkManager')
            self.command_executor.Execute('systemctl stop rsyslog')
            self.command_executor.Execute('systemctl stop systemd-udevd')
            self.command_executor.Execute('systemctl stop systemd-journald')
            self.command_executor.Execute('systemctl stop systemd-hostnamed')
            self.command_executor.Execute('umount /var')

            sleep(3)

            if self.command_executor.Execute('mountpoint /var'):
                unmounted = True

    def unmount(self, mountpoint):
        self.unmount_var()

        proc_comm = ProcessCommunicator()

        self.command_executor.Execute(command_to_execute="fuser -vm " + mountpoint,
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)

        self.context.logger.log("Processes using {0}:\n{1}".format(mountpoint, proc_comm.stdout))

        procs_to_kill = filter(lambda p: p.isdigit(), proc_comm.stdout.split())
        procs_to_kill = reversed(sorted(procs_to_kill))

        for victim in procs_to_kill:
            if int(victim) == os.getpid():
                self.context.logger.log("Restarting WALA in 30 seconds before committing suicide")
                
                # This is a workaround for the bug on CentOS/RHEL 7.2 where systemd-udevd
                # needs to be restarted and the drive mounted/unmounted.
                # Otherwise the dir becomes inaccessible, fuse says: Transport endpoint is not connected

                self.command_executor.Execute('systemctl restart systemd-udevd', True)
                self.bek_util.umount_azure_passhprase(self.encryption_config, force=True)
                self.command_executor.Execute('systemctl restart systemd-udevd', True)

                self.bek_util.get_bek_passphrase_file(self.encryption_config)
                self.bek_util.umount_azure_passhprase(self.encryption_config, force=True)
                self.command_executor.Execute('systemctl restart systemd-udevd', True)

                self.command_executor.ExecuteInBash('sleep 30 && systemctl start waagent &', True)

            if int(victim) == 1:
                self.context.logger.log("Skipping init")
                continue

            self.command_executor.Execute('kill -9 {0}'.format(victim))

        self.command_executor.Execute('telinit u', True)

        sleep(3)

        self.command_executor.Execute('umount ' + mountpoint, True)

    def _append_contents_to_file(self, contents, path):
        with open(path, 'a') as f:
            f.write(contents)

    def _modify_pivoted_oldroot(self):
        self.context.logger.log("Pivoted into oldroot successfully")

        scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        patchesdir = os.path.join(scriptdir, '../encryptpatches')
        patchpath = os.path.join(patchesdir, 'rhel_72_lvm_dracut.patch')

        if not os.path.exists(patchpath):
            message = "Patch not found at path: {0}".format(patchpath)
            self.context.logger.log(message)
            raise Exception(message)
        else:
            self.context.logger.log("Patch found at path: {0}".format(patchpath))

        self.command_executor.Execute('mv /usr/lib/dracut/modules.d/90lvm /usr/lib/dracut/modules.d/91lvm', True)

        self._append_contents_to_file('\nGRUB_CMDLINE_LINUX+=" rd.debug rd.luks.uuid=osencrypt"\n',
                                      '/etc/default/grub')

        self.command_executor.ExecuteInBash('patch -b -d /usr/lib/dracut/modules.d/90crypt -p1 <{0}'.format(patchpath), True)

        self._append_contents_to_file('\nadd_drivers+=" fuse vfat nls_cp437 nls_iso8859-1"\n',
                                      '/etc/dracut.conf')
        self._append_contents_to_file('\nadd_dracutmodules+=" crypt"\n',
                                      '/etc/dracut.conf')

        self.command_executor.Execute('/usr/sbin/dracut -I ntfs-3g -f -v', True)
        self.command_executor.Execute('grub2-install --recheck --force {0}'.format(self.rootfs_disk), True)
        self.command_executor.Execute('grub2-mkconfig -o /boot/grub2/grub.cfg', True)

    def _luks_open(self, bek_path):
        self.command_executor.Execute('mount /boot')
        self.command_executor.Execute('cryptsetup luksOpen --header /boot/luks/osluksheader {0} osencrypt -d {1}'.format(self.rootfs_block_device,
                                                                                                                         bek_path),
                                      raise_exception_on_failure=True)

    def _find_bek_and_execute_action(self, callback_method_name):
        callback_method = getattr(self, callback_method_name)
        if not ismethod(callback_method):
            raise Exception("{0} is not a method".format(callback_method_name))

        bek_path = self.bek_util.get_bek_passphrase_file(self.encryption_config)
        callback_method(bek_path)    
