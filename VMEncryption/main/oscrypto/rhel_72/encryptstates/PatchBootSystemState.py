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
import re
import sys
import io

from Common import CommonVariables, CryptItem
from OSEncryptionState import OSEncryptionState
from CommandExecutor import ProcessCommunicator


class PatchBootSystemState(OSEncryptionState):
    def __init__(self, context):
        super(PatchBootSystemState, self).__init__('PatchBootSystemState', context)
        self.root_partuuid = self._get_root_partuuid()
        self.context.logger.log("root_partuuid: " + str(self.root_partuuid))

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
        # Try mounting /boot/efi for UEFI image support
        self.command_executor.Execute('mount /boot/efi', False)
        self.command_executor.Execute('mount /dev/mapper/osencrypt /oldroot', True)
        self.command_executor.Execute('mount --make-rprivate /', True)
        self.command_executor.Execute('mkdir /oldroot/memroot', True)
        self.command_executor.Execute('pivot_root /oldroot /oldroot/memroot', True)

        self.command_executor.ExecuteInBash('for i in dev proc sys boot; do mount --move /memroot/$i /$i; done', True)
        self.command_executor.ExecuteInBash('[ -e "/boot/luks" ]', True)

        try:
            self._modify_pivoted_oldroot()
        except Exception:
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
            self.command_executor.Execute('systemctl restart waagent')

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
        if not self.root_partuuid:
            self._modify_pivoted_oldroot_no_partuuid()
        else:
            boot_uuid = self._get_boot_uuid()
            self._modify_pivoted_oldroot_with_partuuid(self.root_partuuid, boot_uuid)

    def _modify_pivoted_oldroot_with_partuuid(self, root_partuuid, boot_uuid):
        # Copy the 91adeOnline directory to dracut/modules.d
        scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        ademoduledir = os.path.join(scriptdir, '../../91adeOnline')
        self.command_executor.Execute('cp -r {0} /lib/dracut/modules.d/'.format(ademoduledir), True)

        # Change config so that dracut will force add the dm_crypt kernel module
        self._append_contents_to_file('\nadd_drivers+=" dm_crypt "\n',
                                      '/etc/dracut.conf.d/ade.conf')

        # Change config so that dracut will add the fstab line to the initrd
        self._append_contents_to_file('\nadd_fstab+=" /lib/dracut/modules.d/91adeOnline/ade_fstab_line "\n',
                                      '/etc/dracut.conf.d/ade.conf')

        # Add the new kernel param
        additional_params = ["rd.luks.ade.partuuid={0}".format(root_partuuid),
                             "rd.luks.ade.bootuuid={0}".format(boot_uuid),
                             "rd.debug"]
        self._add_kernelopts(additional_params)

        # For clarity after reboot, we should also add the correct info to crypttab
        crypt_item = CryptItem()
        crypt_item.dev_path = os.path.join("/dev/disk/by-partuuid/", root_partuuid)
        crypt_item.mapper_name = CommonVariables.osmapper_name
        crypt_item.luks_header_path = "/boot/luks/osluksheader"
        self.crypt_mount_config_util.add_crypt_item(crypt_item)

        self._append_contents_to_file('\nadd_dracutmodules+=" crypt"\n',
                                      '/etc/dracut.conf.d/ade.conf')

        self.command_executor.ExecuteInBash("/usr/sbin/dracut -f -v --kver `grubby --default-kernel | sed 's|/boot/vmlinuz-||g'`", True)

    def _modify_pivoted_oldroot_no_partuuid(self):
        scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        ademoduledir = os.path.join(scriptdir, '../../91ade')
        dracutmodulesdir = '/lib/dracut/modules.d'
        udevaderulepath = os.path.join(dracutmodulesdir, '91ade/50-udev-ade.rules')

        proc_comm = ProcessCommunicator()

        self.command_executor.Execute('cp -r {0} /lib/dracut/modules.d/'.format(ademoduledir), True)

        udevadm_cmd = "udevadm info --attribute-walk --name={0}".format(self.rootfs_block_device)
        self.command_executor.Execute(command_to_execute=udevadm_cmd, raise_exception_on_failure=True, communicator=proc_comm)

        matches = re.findall(r'ATTR{partition}=="(.*)"', proc_comm.stdout)
        if not matches:
            raise Exception("Could not parse ATTR{partition} from udevadm info")
        partition = matches[0]
        sed_cmd = 'sed -i.bak s/ENCRYPTED_DISK_PARTITION/{0}/ "{1}"'.format(partition, udevaderulepath)
        self.command_executor.Execute(command_to_execute=sed_cmd, raise_exception_on_failure=True)

        self._append_contents_to_file('osencrypt UUID=osencrypt-locked none discard,header=/osluksheader\n',
                                      '/etc/crypttab')

        self._append_contents_to_file('\nadd_drivers+=" fuse vfat nls_cp437 nls_iso8859-1"\n',
                                      '/etc/dracut.conf')
        self._append_contents_to_file('\nadd_dracutmodules+=" crypt"\n',
                                      '/etc/dracut.conf')

        self.command_executor.Execute('/usr/sbin/dracut -f -v', True)

        self._add_kernelopts(["rd.debug"])

    def _get_boot_uuid(self):
        return self._parse_uuid_from_fstab('/boot')

    def _add_kernelopts(self, args_to_add):
        """
        For EFI machines (Gen2) we want to use the EFI grub.cfg path
        For BIOS machines (Gen1) we want to use the old grub.cfg path
        But we can't tell at this stage easily which one to use if both are present. so we will just update both.
        Moreover, in case somebody runs grub2-mkconfig on the machine we don't want the changes to get nuked out, we will update grub defaults file too.
        """
        grub_cfg_paths = [
            "/boot/grub2/grub.cfg",
            "/boot/efi/EFI/redhat/grub.cfg"
        ]
        grub_cfg_paths = filter(os.path.exists, grub_cfg_paths)

        for grub_cfg_path in grub_cfg_paths:
            for arg in args_to_add:
                self.command_executor.ExecuteInBash("grubby --args {0} --update-kernel DEFAULT -c {1}".format(arg, grub_cfg_path))

        self._append_contents_to_file('\nGRUB_CMDLINE_LINUX+="{0}"\n'.format(" ".join(args_to_add)),
                                      '/etc/default/grub')
