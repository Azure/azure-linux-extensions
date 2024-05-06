#!/usr/bin/env python
#
# VM Backup extension
#
# Copyright 2020 Microsoft Corporation
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
from time import sleep

from OSEncryptionState import OSEncryptionState
from CommandExecutor import ProcessCommunicator
from Common import CommonVariables, CryptItem


class PatchBootSystemState(OSEncryptionState):
    def __init__(self, context):
        super(PatchBootSystemState, self).__init__('PatchBootSystemState', context)

    def should_enter(self):
        self.context.logger.log("Verifying if machine should enter patch_boot_system state")

        if not super(PatchBootSystemState, self).should_enter():
            return False

        self.context.logger.log("Performing enter checks for patch_boot_system state")

        return True

    def enter(self):
        if not self.should_enter():
            return

        # Get BEK path
        bek_path = self.bek_util.get_bek_passphrase_file(self.encryption_config)

        # Set up luksheader
        self.command_executor.ExecuteInBash('mount /boot', False)
        self.command_executor.ExecuteInBash('mount /boot/efi', False)
        self.command_executor.ExecuteInBash('mkdir -p /boot/luks', True)
        self.command_executor.ExecuteInBash('dd if=/dev/zero of=/boot/luks/osluksheader bs=33554432 count=1', True)
        self.command_executor.ExecuteInBash('cryptsetup reencrypt --encrypt --init-only {1} --header /boot/luks/osluksheader -d {0} -q'.format(bek_path,
                                                                                                                                               self.rootfs_block_device),
                                            raise_exception_on_failure=True)

        # Find out the PARTUUID for the root disk
        root_partuuid = self._get_root_partuuid()
        if not root_partuuid:
            raise Exception("Failed to find the partuuid for the root device: {0}", self.rootfs_block_device)

        boot_uuid = self._get_boot_uuid()
        if not boot_uuid:
            raise Exception("Failed to find the uuid for boot device: {0}", self.bootfs_block_device)

        luks_uuid = self._get_luks_uuid()

        if self._is_detached_header_fix():
            # Add the new kernel param if the detached header fix is present
            self._install_and_enable_detached_header_kernel_params(root_partuuid, luks_uuid, boot_uuid)
        else:
            # if detached header fix is absent we will use the 91ade workaround
            self.context.distro_patcher.install_and_enable_ade_online_enc(root_partuuid, boot_uuid, self.rootfs_disk, self.disk_util.is_os_disk_lvm())

        # Everything is ready, repack using dracut/mkinitrd. None of the changes above will take affect until this line is executed.
        self.context.distro_patcher.pack_initial_root_fs()

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit patch_boot_system state")

        if not os.path.exists(self.state_marker):
            self.context.logger.log("First call to patch_boot_system state (pid={0}), restarting the machine".format(os.getpid()))

            # create the marker, but do not advance the state machine
            super(PatchBootSystemState, self).should_exit()

            self.context.hutil.do_status_report(operation='EnableEncryptionOSVolume',
                                                status=CommonVariables.extension_transitioning_status,
                                                status_code=CommonVariables.success,
                                                message="Restarting vm after patching")

            sleep(5)
            # the restarted vm shall see the marker and advance the state machine
            self.command_executor.Execute('reboot')
            # reboot race condition sleep
            sleep(5)
        else:
            self.context.logger.log("Second call to stripdown state (pid={0}), continuing process".format(os.getpid()))
            return True

    def _append_contents_to_file(self, contents, path):
        with open(path, 'a') as f:
            f.write(contents)

    def _install_and_enable_detached_header_kernel_params(self, root_partuuid, luks_uuid, boot_uuid):
        additional_params = ["rd.luks.name={0}=osencrypt".format(luks_uuid),
                             "rd.luks.options={0}=header=/luks/osluksheader".format(luks_uuid),
                             "rd.luks.key={0}=/LinuxPassPhraseFileName:LABEL=\"BEK VOLUME\"".format(luks_uuid),
                             "rd.luks.data={0}=PARTUUID={1}".format(luks_uuid, root_partuuid),
                             "rd.luks.hdr={0}=UUID={1}".format(luks_uuid, boot_uuid),
                             "rd.debug"]
        self._add_kernelopts(additional_params)

    def _get_root_partuuid(self):
        root_partuuid = None
        root_device_items = self.disk_util.get_device_items(self.rootfs_block_device)
        for root_item in root_device_items:
            if self.rootfs_sdx_path.endswith(root_item.name) or os.path.realpath(self.rootfs_block_device).endswith(root_item.name):
                root_partuuid = self.disk_util.get_device_items_property(root_item.name, "PARTUUID")
                if root_partuuid:
                    return root_partuuid
        return root_partuuid

    def _get_luks_uuid(self):
        luks_header_path = "/boot/luks/osluksheader"
        return self.disk_util.luks_get_uuid(luks_header_path)

    def _is_detached_header_fix(self):
        # TODO: We need to ask the redhat folks the best way to do this. We can scan man pages like below.
        # But as we haven't fully tested detached header fix's production code, I am going to hard code this method to return False

        # ret_code = self.command_executor.ExecuteInBash("man systemd-cryptsetup-generator | grep luks.hdr")
        # return ret_code == 0
        return False
