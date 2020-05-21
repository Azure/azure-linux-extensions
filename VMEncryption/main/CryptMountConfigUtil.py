#!/usr/bin/env python
#
# VMEncryption extension
#
# Copyright 2019 Microsoft Corporation
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

import json
import os
import os.path
import re
import shutil
import uuid
from datetime import datetime

from CommandExecutor import CommandExecutor, ProcessCommunicator
from Common import CryptItem, CommonVariables


class CryptMountConfigUtil(object):
    """
    A utility to modify the config files that mount or unlock encrypted disks

    There are effectively two "config file systems" that we use:
    1) The "old" azure_crypt_mount system
        A file that does the job of fstab (mounting) and crypttab (unlocking) both.
        The extension does the job of parsing this file and mounting-unlocking the drives.
        As the extension is run a while after the boot process completes, the disks get ready a little bit late
    2) The "new" crypttab system
        We use the standard system files (fstab and crypttab).
        The system is supposed to mount the drives for us before the extension even starts.
        In case the system fails to do so, the extension still parses and unlock-mounts the drives when it is run.
        In this system the disks should be ready at boot.

    As of now, if any non-OS disks are present in the old system, we stick to the old system.
    Otherwise the old system is considered unused and we use the new system.
    """

    def __init__(self, logger, encryption_environment, disk_util):
        self.encryption_environment = encryption_environment
        self.logger = logger
        self.disk_util = disk_util
        self.command_executor = CommandExecutor(self.logger)

    def parse_crypttab_line(self, line):
        crypttab_parts = line.strip().split()

        if len(crypttab_parts) < 3:  # Line should have enough content
            return None

        if crypttab_parts[0].startswith("#"):  # Line should not be a comment
            return None

        crypt_item = CryptItem()
        crypt_item.mapper_name = crypttab_parts[0]
        crypt_item.dev_path = crypttab_parts[1]
        keyfile_path = crypttab_parts[2]
        if CommonVariables.encryption_key_file_name not in keyfile_path and self.encryption_environment.cleartext_key_base_path not in keyfile_path:
            return None  # if the key_file path doesn't have the encryption key file name, its probably not for us to mess with
        if self.encryption_environment.cleartext_key_base_path in keyfile_path:
            crypt_item.uses_cleartext_key = True
        crypttab_option_string = crypttab_parts[3]
        crypttab_options = crypttab_option_string.split(',')
        for option in crypttab_options:
            option_pair = option.split("=")
            if len(option_pair) == 2:
                key = option_pair[0].strip()
                value = option_pair[1].strip()
                if key == "header":
                    crypt_item.luks_header_path = value
        return crypt_item

    def parse_azure_crypt_mount_line(self, line):

        crypt_item = CryptItem()

        crypt_mount_item_properties = line.strip().split()

        crypt_item.mapper_name = crypt_mount_item_properties[0]
        crypt_item.dev_path = crypt_mount_item_properties[1]
        crypt_item.luks_header_path = crypt_mount_item_properties[2] if crypt_mount_item_properties[2] and crypt_mount_item_properties[2] != "None" else None
        crypt_item.mount_point = crypt_mount_item_properties[3]
        crypt_item.file_system = crypt_mount_item_properties[4]
        crypt_item.uses_cleartext_key = True if crypt_mount_item_properties[5] == "True" else False
        crypt_item.current_luks_slot = int(crypt_mount_item_properties[6]) if len(crypt_mount_item_properties) > 6 else -1

        return crypt_item

    def consolidate_azure_crypt_mount(self, passphrase_file):
        """
        Reads the backup files from block devices that have a LUKS header and adds it to the cenral azure_crypt_mount file
        """
        self.logger.log("Consolidating azure_crypt_mount")

        device_items = self.disk_util.get_device_items(None)
        crypt_items = self.get_crypt_items()
        azure_name_table = self.disk_util.get_block_device_to_azure_udev_table()

        for device_item in device_items:
            if device_item.file_system == "crypto_LUKS":
                # Found an encrypted device, let's check if it is in the azure_crypt_mount file
                # Check this by comparing the dev paths
                self.logger.log("Found an encrypted device at {0}".format(device_item.name))
                found_in_crypt_mount = False
                device_item_path = self.disk_util.get_device_path(device_item.name)
                device_item_real_path = os.path.realpath(device_item_path)
                for crypt_item in crypt_items:
                    if os.path.realpath(crypt_item.dev_path) == device_item_real_path:
                        found_in_crypt_mount = True
                        break
                if found_in_crypt_mount:
                    # Its already in crypt_mount so nothing to do yet
                    self.logger.log("{0} is already in the azure_crypt_mount/crypttab file".format(device_item.name))
                    continue
                # Otherwise, unlock and mount it at a test spot and extract mount info

                crypt_item = CryptItem()
                crypt_item.dev_path = azure_name_table[device_item_path] if device_item_path in azure_name_table else device_item_path
                if crypt_item.dev_path == "/dev/disk/azure/resource-part1":
                    # Ignore the resource disk. We have other code for that.
                    continue
                # dev_path will always start with "/" so we strip that out and generate a temporary mapper name from the rest
                # e.g. /dev/disk/azure/scsi1/lun1 --> dev-disk-azure-scsi1-lun1-unlocked  | /dev/mapper/lv0 --> dev-mapper-lv0-unlocked
                crypt_item.mapper_name = crypt_item.dev_path[5:].replace("/", "-") + "-unlocked"
                crypt_item.uses_cleartext_key = False  # might need to be changed later
                crypt_item.current_luks_slot = -1

                temp_mount_point = os.path.join("/mnt/", crypt_item.mapper_name)
                azure_crypt_mount_backup_location = os.path.join(temp_mount_point, ".azure_ade_backup_mount_info/azure_crypt_mount_line")
                crypttab_backup_location = os.path.join(temp_mount_point, ".azure_ade_backup_mount_info/crypttab_line")

                # try to open to the temp mapper name generated above
                return_code = self.disk_util.luks_open(passphrase_file=passphrase_file,
                                                       dev_path=device_item_real_path,
                                                       mapper_name=crypt_item.mapper_name,
                                                       header_file=None,
                                                       uses_cleartext_key=False)
                if return_code != CommonVariables.process_success:
                    self.logger.log(msg=('cryptsetup luksOpen failed, return_code is:{0}'.format(return_code)), level=CommonVariables.ErrorLevel)
                    continue

                return_code = self.disk_util.mount_filesystem(os.path.join(CommonVariables.dev_mapper_root, crypt_item.mapper_name), temp_mount_point)
                if return_code != CommonVariables.process_success:
                    self.logger.log(msg=('Mount failed, return_code is:{0}'.format(return_code)), level=CommonVariables.ErrorLevel)
                    # this can happen with disks without file systems (lvm, raid or simply empty disks)
                    # in this case just add an entry to the azure_crypt_mount without a mount point (for lvm/raid scenarios)
                    self.add_crypt_item(crypt_item)
                    self.disk_util.luks_close(crypt_item.mapper_name)
                    continue

                if not os.path.exists(azure_crypt_mount_backup_location) and not os.path.exists(crypttab_backup_location):
                    self.logger.log(msg=("MountPoint info not found for" + device_item_real_path), level=CommonVariables.ErrorLevel)
                    # Not sure when this happens..
                    # in this case also, just add an entry to the azure_crypt_mount without a mount point.
                    self.add_crypt_item(crypt_item)
                elif os.path.exists(azure_crypt_mount_backup_location):
                    with open(azure_crypt_mount_backup_location, 'r') as f:
                        for line in f:
                            if not line.strip():
                                continue
                            # copy the crypt_item from the backup to the central os location
                            parsed_crypt_item = self.parse_azure_crypt_mount_line(line)
                            self.add_crypt_item(parsed_crypt_item)
                elif os.path.exists(crypttab_backup_location):
                    with open(crypttab_backup_location, 'r') as f:
                        for line in f:
                            if not line.strip():
                                continue
                            # copy the crypt_item from the backup to the central os location
                            parsed_crypt_item = self.parse_crypttab_line(line)
                            if parsed_crypt_item is None:
                                continue
                            self.add_crypt_item(parsed_crypt_item)
                    fstab_backup_location = os.path.join(temp_mount_point, ".azure_ade_backup_mount_info/fstab_line")
                    if os.path.exists(fstab_backup_location):
                        fstab_backup_line = None
                        with open(fstab_backup_location, 'r') as f:
                            for line in f:
                                if not line.strip():
                                    continue
                                # copy the crypt_item from the backup to the central os location
                                fstab_backup_line = line
                        if fstab_backup_line is not None:
                            with open("/etc/fstab", 'a') as f:
                                f.writelines([fstab_backup_line])

                # close the file and then unmount and close
                self.disk_util.umount(temp_mount_point)
                self.disk_util.luks_close(crypt_item.mapper_name)

    def get_crypt_items(self):
        """
        Reads the central azure_crypt_mount file and parses it into an array of CryptItem()s
        If the root partition is encrypted but not present in the file it generates a CryptItem() for the root partition and appends it to the list.

        At boot time, it might be required to run the consolidate_azure_crypt_mount method to capture any encrypted volumes not in
        the central file and add it to the central file
        """

        crypt_items = []
        rootfs_crypt_item_found = False

        if self.should_use_azure_crypt_mount():
            with open(self.encryption_environment.azure_crypt_mount_config_path, 'r') as f:
                for line in f.readlines():
                    if not line.strip():
                        continue

                    crypt_item = self.parse_azure_crypt_mount_line(line)

                    if crypt_item.mount_point == "/" or crypt_item.mapper_name == CommonVariables.osmapper_name:
                        rootfs_crypt_item_found = True

                    crypt_items.append(crypt_item)
        else:
            self.logger.log("Using crypttab instead of azure_crypt_mount file.")
            crypttab_path = "/etc/crypttab"

            fstab_items = []

            with open("/etc/fstab", "r") as f:
                for line in f.readlines():
                    fstab_device, fstab_mount_point, fstab_fs, fstab_opts = self.parse_fstab_line(line)
                    if fstab_device is not None:
                        fstab_items.append((fstab_device, fstab_mount_point, fstab_fs))

            if not os.path.exists(crypttab_path):
                self.logger.log("{0} does not exist".format(crypttab_path))
            else:
                with open(crypttab_path, 'r') as f:
                    for line in f.readlines():
                        if not line.strip():
                            continue

                        crypt_item = self.parse_crypttab_line(line)
                        if crypt_item is None:
                            continue

                        if crypt_item.mapper_name == CommonVariables.osmapper_name:
                            rootfs_crypt_item_found = True

                        for device_path, mount_path, fs in fstab_items:
                            if crypt_item.mapper_name in device_path:
                                crypt_item.mount_point = mount_path
                                crypt_item.file_system = fs
                        crypt_items.append(crypt_item)

        encryption_status = json.loads(self.disk_util.get_encryption_status())

        if encryption_status["os"] == "Encrypted" and not rootfs_crypt_item_found:
            # If the OS partition looks encrypted but we didn't find an OS partition in the crypt_mount_file
            # So we will create a CryptItem on the fly and add it to the output
            crypt_item = CryptItem()
            crypt_item.mapper_name = CommonVariables.osmapper_name

            proc_comm = ProcessCommunicator()
            grep_result = self.command_executor.ExecuteInBash("cryptsetup status {0} | grep device:".format(CommonVariables.osmapper_name), communicator=proc_comm)
            if grep_result == 0:
                crypt_item.dev_path = proc_comm.stdout.strip().split()[1]
            else:
                proc_comm = ProcessCommunicator()
                self.command_executor.Execute("dmsetup table --target crypt", communicator=proc_comm)

                for line in proc_comm.stdout.splitlines():
                    if CommonVariables.osmapper_name in line:
                        majmin = filter(lambda p: re.match(r'\d+:\d+', p), line.split())[0]
                        src_device = filter(lambda d: d.majmin == majmin, self.disk_util.get_device_items(None))[0]
                        crypt_item.dev_path = '/dev/' + src_device.name
                        break

            rootfs_dev = next((m for m in self.disk_util.get_mount_items() if m["dest"] == "/"))
            crypt_item.file_system = rootfs_dev["fs"]

            if not crypt_item.dev_path:
                raise Exception("Could not locate block device for rootfs")

            crypt_item.luks_header_path = "/boot/luks/osluksheader"

            if not os.path.exists(crypt_item.luks_header_path):
                crypt_item.luks_header_path = crypt_item.dev_path

            crypt_item.mount_point = "/"
            crypt_item.uses_cleartext_key = False
            crypt_item.current_luks_slot = -1

            crypt_items.append(crypt_item)

        return crypt_items

    def should_use_azure_crypt_mount(self):
        if not os.path.exists(self.encryption_environment.azure_crypt_mount_config_path):
            return False

        non_os_entry_found = False
        with open(self.encryption_environment.azure_crypt_mount_config_path, 'r') as f:
            for line in f.readlines():
                if not line.strip():
                    continue

                parsed_crypt_item = self.parse_azure_crypt_mount_line(line)
                if parsed_crypt_item.mapper_name != CommonVariables.osmapper_name:
                    non_os_entry_found = True

        # if there is a non_os_entry found we should use azure_crypt_mount. Otherwise we shouldn't
        return non_os_entry_found

    def add_crypt_item(self, crypt_item, backup_folder=None):
        if self.should_use_azure_crypt_mount():
            return self.add_crypt_item_to_azure_crypt_mount(crypt_item, backup_folder)
        else:
            return self.add_crypt_item_to_crypttab(crypt_item, backup_folder)

    def add_crypt_item_to_crypttab(self, crypt_item, backup_folder=None):
        # figure out the keyfile. if cleartext use that, if not use keyfile from scsi and lun
        if crypt_item.uses_cleartext_key:
            key_file = self.encryption_environment.cleartext_key_base_path + crypt_item.mapper_name
        else:
            # get the scsi and lun number for the dev_path of this crypt_item
            scsi_lun_numbers = self.disk_util.get_azure_data_disk_controller_and_lun_numbers([os.path.realpath(crypt_item.dev_path)])
            if len(scsi_lun_numbers) == 0:
                # The default in case we didn't get any scsi/lun numbers
                key_file = os.path.join(CommonVariables.encryption_key_mount_point, self.encryption_environment.default_bek_filename)
            else:
                scsi_controller, lun_number = scsi_lun_numbers[0]
                key_file = os.path.join(CommonVariables.encryption_key_mount_point, CommonVariables.encryption_key_file_name + "_" + str(scsi_controller) + "_" + str(lun_number))

        crypttab_line = "\n{0} {1} {2} luks,nofail".format(crypt_item.mapper_name, crypt_item.dev_path, key_file)
        if crypt_item.luks_header_path and str(crypt_item.luks_header_path) != "None":
            crypttab_line += ",header=" + crypt_item.luks_header_path

        with open("/etc/crypttab", "a") as wf:
            wf.write(crypttab_line + "\n")

        if backup_folder is not None:
            crypttab_backup_file = os.path.join(backup_folder, "crypttab_line")
            self.disk_util.make_sure_path_exists(backup_folder)
            with open(crypttab_backup_file, "w") as wf:
                wf.write(crypttab_line)
            self.logger.log("Added crypttab item {0} to {1}".format(crypt_item.mapper_name, crypttab_backup_file))

            if crypt_item.mount_point:
                # We need to backup the fstab line too
                fstab_backup_line = None
                with open("/etc/fstab", "r") as f:
                    for line in f.readlines():
                        device, mountpoint, fs, opts = self.parse_fstab_line(line)
                        if mountpoint == crypt_item.mount_point and crypt_item.mapper_name in device:
                            fstab_backup_line = line
                if fstab_backup_line is not None:
                    fstab_backup_file = os.path.join(backup_folder, "fstab_line")
                    with open(fstab_backup_file, "w") as wf:
                        wf.write(fstab_backup_line)
                    self.logger.log("Added fstab item {0} to {1}".format(fstab_backup_line, fstab_backup_file))

        return True

    def add_crypt_item_to_azure_crypt_mount(self, crypt_item, backup_folder=None):
        """
        format is like this:
        <target name> <source device> <key file> <options>
        """
        try:
            mount_content_item = (crypt_item.mapper_name + " " +
                                  crypt_item.dev_path + " " +
                                  str(crypt_item.luks_header_path) + " " +
                                  crypt_item.mount_point + " " +
                                  crypt_item.file_system + " " +
                                  str(crypt_item.uses_cleartext_key) + " " +
                                  str(crypt_item.current_luks_slot)) + "\n"

            with open(self.encryption_environment.azure_crypt_mount_config_path, 'a') as wf:
                wf.write(mount_content_item)

            self.logger.log("Added crypt item {0} to azure_crypt_mount".format(crypt_item.mapper_name))

            if backup_folder is not None:
                backup_file = os.path.join(backup_folder, "azure_crypt_mount_line")
                self.disk_util.make_sure_path_exists(backup_folder)
                with open(backup_file, "w") as wf:
                    wf.write(mount_content_item)
                self.logger.log("Added crypt item {0} to {1}".format(crypt_item.mapper_name, backup_file))

            return True
        except Exception:
            return False

    def remove_crypt_item(self, crypt_item, backup_folder=None):
        try:
            if self.should_use_azure_crypt_mount():
                crypt_file_path = self.encryption_environment.azure_crypt_mount_config_path
                crypt_line_parser = self.parse_azure_crypt_mount_line
                line_file_name = "azure_crypt_mount_line"
            elif os.path.exists("/etc/crypttab"):
                crypt_file_path = "/etc/crypttab"
                crypt_line_parser = self.parse_crypttab_line
                line_file_name = "crypttab_line"
            else:
                return True

            filtered_mount_lines = []
            with open(crypt_file_path, 'r') as f:
                self.logger.log("removing an entry from {0}".format(crypt_file_path))
                for line in f:
                    if not line.strip():
                        continue

                    parsed_crypt_item = crypt_line_parser(line)
                    if parsed_crypt_item is not None and parsed_crypt_item.mapper_name == crypt_item.mapper_name:
                        self.logger.log("Removing crypt mount entry: {0}".format(line))
                        continue

                    filtered_mount_lines.append(line)

            with open(crypt_file_path, 'w') as wf:
                wf.write(''.join(filtered_mount_lines))

            if backup_folder is not None:
                backup_file = os.path.join(backup_folder, line_file_name)
                if os.path.exists(backup_file):
                    os.remove(backup_file)

            return True

        except Exception:
            return False

    def update_crypt_item(self, crypt_item, backup_folder=None):
        self.logger.log("Updating entry for crypt item {0}".format(crypt_item))
        self.remove_crypt_item(crypt_item, backup_folder)
        self.add_crypt_item(crypt_item, backup_folder)

    def append_mount_info(self, dev_path, mount_point):
        shutil.copy2('/etc/fstab', '/etc/fstab.backup.' + str(uuid.uuid4()))
        mount_content_item = dev_path + " " + mount_point + "  auto defaults 0 0"
        new_mount_content = ""
        with open("/etc/fstab", 'r') as f:
            existing_content = f.read()
            new_mount_content = existing_content + "\n" + mount_content_item
        with open("/etc/fstab", 'w') as wf:
            wf.write(new_mount_content)

    def append_mount_info_data_disk(self, mapper_path, mount_point):
        shutil.copy2('/etc/fstab', '/etc/fstab.backup.' + str(uuid.uuid4()))
        mount_content_item = "\n#This line was added by Azure Disk Encryption\n" + mapper_path + " " + mount_point + " auto defaults,nofail,discard 0 0"
        with open("/etc/fstab", 'a') as wf:
            wf.write(mount_content_item)

    def is_bek_in_fstab_file(self, lines):
        for line in lines:
            fstab_device, fstab_mount_point, fstab_fs, fstab_opts = self.parse_fstab_line(line)
            if fstab_mount_point and os.path.normpath(fstab_mount_point) == os.path.normpath(CommonVariables.encryption_key_mount_point):
                return True
        return False

    def parse_fstab_line(self, line):
        fstab_parts = line.strip().split()

        if len(fstab_parts) < 4:  # Line should have enough content
            return None, None, None, None

        if fstab_parts[0].startswith("#"):  # Line should not be a comment
            return None, None, None, None

        fstab_device = fstab_parts[0]
        fstab_mount_point = fstab_parts[1]
        fstab_file_system = fstab_parts[2]
        fstab_options = fstab_parts[3]
        fstab_options = fstab_options.strip().split(",")
        return fstab_device, fstab_mount_point, fstab_file_system, fstab_options

    def add_nofail_if_absent_to_fstab_line(self, line):
        fstab_device, fstab_mount_point, fstab_fs, fstab_opts = self.parse_fstab_line(line)
        if fstab_opts is None or "nofail" in fstab_opts:
            return line

        old_opts_string = ",".join(fstab_opts)
        new_opts_string = ",".join(["nofail"] + fstab_opts)

        return line.replace(old_opts_string, new_opts_string)


    def modify_fstab_entry_encrypt(self, mount_point, mapper_path):
        self.logger.log("modify_fstab_entry_encrypt called with mount_point={0}, mapper_path={1}".format(mount_point, mapper_path))

        if not mount_point:
            self.logger.log("modify_fstab_entry_encrypt: mount_point is empty")
            return

        shutil.copy2('/etc/fstab', '/etc/fstab.backup.' + str(uuid.uuid4()))

        with open('/etc/fstab', 'r') as f:
            lines = f.readlines()

        relevant_line = None
        for i in range(len(lines)):
            line = lines[i]
            fstab_device, fstab_mount_point, fstab_fs, fstab_opts = self.parse_fstab_line(line)

            if fstab_mount_point != mount_point:  # Not the line we are looking for
                continue

            self.logger.log("Found the relevant fstab line: " + line)
            relevant_line = line

            if self.should_use_azure_crypt_mount():
                # in this case we just remove the line
                lines.pop(i)
                break
            else:
                new_line = relevant_line.replace(fstab_device, mapper_path)
                new_line = self.add_nofail_if_absent_to_fstab_line(new_line)
                self.logger.log("Replacing that line with: " + new_line)
                lines[i] = new_line
                break

        if not self.is_bek_in_fstab_file(lines):
            lines.append(self.get_fstab_bek_line())
            self.add_bek_to_default_cryptdisks()

        with open('/etc/fstab', 'w') as f:
            f.writelines(lines)

        if relevant_line is not None:
            with open('/etc/fstab.azure.backup', 'a+') as f:
                # The backup file contains the fstab entries from before encryption.
                # the file is used during disable to restore the original fstab entry
                f.write(relevant_line)

    def get_fstab_bek_line(self):
        if self.disk_util.distro_patcher.distro_info[0].lower() == 'ubuntu' and self.disk_util.distro_patcher.distro_info[1].startswith('14'):
            return CommonVariables.bek_fstab_line_template_ubuntu_14.format(CommonVariables.encryption_key_mount_point)
        else:
            return CommonVariables.bek_fstab_line_template.format(CommonVariables.encryption_key_mount_point)

    def add_bek_to_default_cryptdisks(self):
        if os.path.exists("/etc/default/cryptdisks"):
            with open("/etc/default/cryptdisks", 'r') as f:
                lines = f.readlines()
            if not any(["azure_bek_disk" in line for line in lines]):
                with open("/etc/default/cryptdisks", 'a') as f:
                    f.write(CommonVariables.etc_defaults_cryptdisks_line.format(CommonVariables.encryption_key_mount_point))

    def remove_mount_info(self, mount_point):
        if not mount_point:
            self.logger.log("remove_mount_info: mount_point is empty")
            return

        shutil.copy2('/etc/fstab', '/etc/fstab.backup.' + str(str(uuid.uuid4())))

        filtered_contents = []
        removed_lines = []

        with open('/etc/fstab', 'r') as f:
            for line in f.readlines():
                line = line.strip()
                pattern = '\\s' + re.escape(mount_point) + '\\s'

                if re.search(pattern, line):
                    self.logger.log("removing fstab line: {0}".format(line))
                    removed_lines.append(line)
                    continue

                filtered_contents.append(line)

        with open('/etc/fstab', 'w') as f:
            f.write('\n')
            f.write('\n'.join(filtered_contents))
            f.write('\n')

        self.logger.log("fstab updated successfully")

        with open('/etc/fstab.azure.backup', 'a+') as f:
            f.write('\n')
            f.write('\n'.join(removed_lines))
            f.write('\n')

        self.logger.log("fstab.azure.backup updated successfully")

    def restore_mount_info(self, mount_point_or_mapper_name):
        if not mount_point_or_mapper_name:
            self.logger.log("restore_mount_info: mount_point_or_mapper_name is empty")
            return

        shutil.copy2('/etc/fstab', '/etc/fstab.backup.' + str(str(uuid.uuid4())))

        lines_to_keep_in_backup_fstab = []
        lines_to_put_back_to_fstab = []

        with open('/etc/fstab.azure.backup', 'r') as f:
            for line in f.readlines():
                line = line.strip()
                pattern = '\\s' + re.escape(mount_point_or_mapper_name) + '\\s'

                if re.search(pattern, line):
                    self.logger.log("removing fstab.azure.backup line: {0}".format(line))
                    lines_to_put_back_to_fstab.append(line)
                    continue

                lines_to_keep_in_backup_fstab.append(line)

        with open('/etc/fstab.azure.backup', 'w') as f:
            f.write('\n'.join(lines_to_keep_in_backup_fstab))
            f.write('\n')

        self.logger.log("fstab.azure.backup updated successfully")

        lines_that_remain_in_fstab = []
        with open('/etc/fstab', 'r') as f:
            for line in f.readlines():
                line = line.strip()
                pattern = '\\s' + re.escape(mount_point_or_mapper_name) + '\\s'
                if re.search(pattern, line):
                    # This line should not remain in the fstab.
                    self.logger.log("removing fstab line: {0}".format(line))
                    continue
                lines_that_remain_in_fstab.append(line)

        with open('/etc/fstab', 'w') as f:
            f.write('\n'.join(lines_that_remain_in_fstab + lines_to_put_back_to_fstab))
            f.write('\n')

        self.logger.log("fstab updated successfully")

    # All encrypted devices are unlocked before this function is called
    def migrate_crypt_items(self):
        with open('/etc/fstab', 'r') as f:
            lines = f.readlines()
        
        if not self.is_bek_in_fstab_file(lines):
            self.logger.log("BEK volume not detected in fstab. Adding it now.")
            lines.append(self.get_fstab_bek_line())
            self.add_bek_to_default_cryptdisks()
            with open('/etc/fstab', 'w') as f:
                f.writelines(lines)

        crypt_items = self.get_crypt_items()

        for crypt_item in crypt_items:
            self.logger.log("Migrating crypt item: {0}".format(crypt_item))
            if crypt_item.mount_point == "/" or CommonVariables.osmapper_name == crypt_item.mapper_name:
                self.logger.log("Skipping OS disk")
                continue

            if crypt_item.mapper_name and crypt_item.mount_point and crypt_item.mount_point != "None":
                self.logger.log(msg="Checking if device for mapper name: {0} has valid filesystem".format(crypt_item.mapper_name), level=CommonVariables.InfoLevel)
                try:
                    fstype = self.disk_util.get_device_items_property(crypt_item.mapper_name, 'FSTYPE')
                    if fstype not in CommonVariables.format_supported_file_systems:
                        self.logger.log("mapper name: {0} does not have a supported filesystem. Skipping device".format(crypt_item.mapper_name))
                        continue
                except Exception:
                    self.logger.log("Exception occured while querying filesystem for mapper name {0}. Skipping device.".format(crypt_item.mapper_name))
                    continue
                self.logger.log(msg="Adding entry for {0} drive in fstab with mount point {1}".format(crypt_item.mapper_name, crypt_item.mount_point), level=CommonVariables.InfoLevel)
                self.append_mount_info_data_disk(os.path.join(CommonVariables.dev_mapper_root, crypt_item.mapper_name), crypt_item.mount_point)
                backup_folder = os.path.join(crypt_item.mount_point, ".azure_ade_backup_mount_info/")
                self.add_crypt_item_to_crypttab(crypt_item, backup_folder=backup_folder)
            else:
                self.logger.log("Mapper name or mount point not available. Cannot migrate it to crypttab")
        
        if os.path.exists(self.encryption_environment.azure_crypt_mount_config_path):
            self.logger.log(msg="archiving azure crypt mount file: {0}".format(self.encryption_environment.azure_crypt_mount_config_path))
            time_stamp = datetime.now()
            new_name = "{0}_{1}".format(self.encryption_environment.azure_crypt_mount_config_path, time_stamp)
            os.rename(self.encryption_environment.azure_crypt_mount_config_path, new_name)
        else:
            self.logger.log(msg=("the azure crypt mount file not exist: {0}".format(self.encryption_environment.azure_crypt_mount_config_path)), level=CommonVariables.InfoLevel)


