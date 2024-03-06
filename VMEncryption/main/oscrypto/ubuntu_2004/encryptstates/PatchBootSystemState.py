#!/usr/bin/env python
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

import inspect
import os
import sys
import io

from OSEncryptionState import OSEncryptionState
from CommandExecutor import ProcessCommunicator
from Common import CommonVariables


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
        self.command_executor.Execute('mount /boot/efi', False)
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
            extension_versioned_name = 'Microsoft.Azure.Security.' + CommonVariables.extension_name + '-' + CommonVariables.extension_version
            test_extension_full_name = CommonVariables.test_extension_publisher + CommonVariables.test_extension_name
            test_extension_versioned_name = CommonVariables.test_extension_publisher + CommonVariables.test_extension_name + '-' + CommonVariables.extension_version
            self.command_executor.Execute('cp -ax' +
                                          ' /var/log/azure/{0}'.format(extension_full_name) +
                                          ' /oldroot/var/log/azure/{0}.Stripdown'.format(extension_full_name))
            self.command_executor.ExecuteInBash('cp -ax' +
                                          ' /var/lib/waagent/{0}/config/*.settings.rejected'.format(extension_versioned_name) +
                                          ' /oldroot/var/lib/waagent/{0}/config'.format(extension_versioned_name))
            self.command_executor.ExecuteInBash('cp -ax' +
                                          ' /var/lib/waagent/{0}/status/*.status.rejected'.format(extension_versioned_name) +
                                          ' /oldroot/var/lib/waagent/{0}/status'.format(extension_versioned_name))
            self.command_executor.Execute('cp -ax' +
                                          ' /var/log/azure/{0}'.format(test_extension_full_name) +
                                          ' /oldroot/var/log/azure/{0}.Stripdown'.format(test_extension_full_name), suppress_logging=True)
            self.command_executor.ExecuteInBash('cp -ax' +
                                          ' /var/lib/waagent/{0}/config/*.settings.rejected'.format(test_extension_versioned_name) +
                                          ' /oldroot/var/lib/waagent/{0}/config'.format(test_extension_versioned_name), suppress_logging=True)
            self.command_executor.ExecuteInBash('cp -ax' +
                                          ' /var/lib/waagent/{0}/status/*.status.rejected'.format(test_extension_versioned_name) +
                                          ' /oldroot/var/lib/waagent/{0}/status'.format(test_extension_versioned_name), suppress_logging=True)
            # Preserve waagent log from pivot root env
            self.command_executor.Execute('cp -ax /var/log/waagent.log /oldroot/var/log/waagent.log.pivotroot')
            self.command_executor.Execute('umount /boot')
            self.command_executor.Execute('umount /oldroot')
            self.command_executor.Execute('systemctl restart walinuxagent')

            self.context.logger.log("Pivoted back into memroot successfully")

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit patch_boot_system state")

        return super(PatchBootSystemState, self).should_exit()

    def _append_contents_to_file(self, contents, path):
        # Python 3.x strings are Unicode by default and do not use decode
        if sys.version_info[0] < 3:
            if isinstance(contents, str):
                contents = contents.decode('utf-8')

        with io.open(path, 'a') as f:
            f.write(contents)

    def _modify_pivoted_oldroot(self):
        self.context.logger.log("Pivoted into oldroot successfully")

        # copy hook and boot scripts to initramfs 
        self._copy_ade_scripts()

        root_partition_uuid = self._get_root_partuuid()
        if root_partition_uuid:
            # add root partition UUID to boot script cryptsetup command
            self.command_executor.Execute("sed -i 's/ROOTPARTUUID/{0}/g' /usr/share/initramfs-tools/scripts/init-premount/crypt-ade-boot".format(root_partition_uuid), True)
            # add root partition UUID to /etc/crypttab
            entry = 'osencrypt /dev/disk/by-partuuid/{0} /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,discard,header=/boot/luks/osluksheader'.format(root_partition_uuid)
            self._append_contents_to_file(entry, '/etc/crypttab')
        else:
            message = "Failed to get root partition UUID"
            self.context.logger.log(message)
            raise Exception(message)

        # once hook and boot scripts are ready, update initramfs
        self.command_executor.Execute('update-initramfs -u -k all', True)

        # prior to updating grub, do the following: 
        # - remove the 40-force-partuuid.cfg file added by cloudinit, since it references the old boot partition
        # - set grub cmdline to use root=/dev/mapper/osencrypt
        self.command_executor.Execute("rm -f /etc/default/grub.d/40-force-partuuid.cfg", True)
        self.command_executor.Execute("sed -i 's/GRUB_CMDLINE_LINUX=\"/GRUB_CMDLINE_LINUX=\"root=\/dev\/mapper\/osencrypt /g' /etc/default/grub", True)

        # now update grub and re-install
        self.command_executor.Execute('update-grub', True)
        self.command_executor.Execute('grub-install --recheck --force {0}'.format(self.rootfs_disk), True)

    def _get_root_partuuid(self):
        if not os.path.exists(CommonVariables.disk_by_partuuid_root):
            self.context.logger.log(CommonVariables.disk_by_partuuid_root + " does not exist.")
            return None
        partuuids = os.listdir(CommonVariables.disk_by_partuuid_root)
        for partuuid in partuuids:
            if os.path.realpath(os.path.join(CommonVariables.disk_by_partuuid_root, partuuid)) == os.path.realpath(self.rootfs_block_device):
                self.context.logger.log("Root PARTUUID found " + partuuid)
                return partuuid
        self.context.logger.log("Cannot determine root PARTUUID.")
        return None

    def _copy_ade_scripts(self):
        # Copy Ubuntu 20.04 specific hook and boot scripts for ADE into position
        # Subsequent update-initramfs calls will use these to build the new initramfs
        # http://manpages.ubuntu.com/manpages/focal/en/man7/initramfs-tools.7.html

        script_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        encrypt_scripts_dir = os.path.join(script_dir,'../encryptscripts/')

        # hook script
        hook_script_name = 'crypt-ade-hook'
        hook_script_source = os.path.join(script_dir, encrypt_scripts_dir, hook_script_name)
        hook_script_dest = os.path.join('/usr/share/initramfs-tools/hooks/', hook_script_name)
        if not os.path.exists(hook_script_source):
            message = "Hook script not found at path: {0}".format(hook_script_source)
            self.context.logger.log(message)
            raise Exception(message)
        else:
            self.context.logger.log("Hook script found at path: {0}".format(hook_script_source))
        self.command_executor.Execute('cp {0} {1}'.format(hook_script_source,hook_script_dest), True)
        self.command_executor.Execute('chmod +x {0}'.format(hook_script_dest), True)

        # copy boot script and update with root partition uuid
        boot_script_name = 'crypt-ade-boot'
        boot_script_source = os.path.join(script_dir, encrypt_scripts_dir, boot_script_name)
        boot_script_dest = os.path.join('/usr/share/initramfs-tools/scripts/init-premount/', boot_script_name)
        if not os.path.exists(boot_script_source):
            message = "Boot script not found at path: {0}".format(boot_script_source)
            self.context.logger.log(message)
            raise Exception(message)
        else:
            self.context.logger.log("Boot script found at path: {0}".format(boot_script_source))
        self.command_executor.Execute('cp {0} {1}'.format(boot_script_source,boot_script_dest), True)
        self.command_executor.Execute('chmod +x {0}'.format(boot_script_dest), True)
