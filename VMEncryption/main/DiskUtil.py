#!/usr/bin/env python
#
# VMEncryption extension
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
import json
import os
import os.path
import re
from subprocess import Popen
import traceback
import glob

from EncryptionConfig import EncryptionConfig
from DecryptionMarkConfig import DecryptionMarkConfig
from EncryptionMarkConfig import EncryptionMarkConfig
from TransactionalCopyTask import TransactionalCopyTask
from CommandExecutor import CommandExecutor, ProcessCommunicator
from Common import CommonVariables, LvmItem, DeviceItem


class DiskUtil(object):
    os_disk_lvm = None
    sles_cache = {}

    def __init__(self, hutil, patching, logger, encryption_environment):
        self.encryption_environment = encryption_environment
        self.hutil = hutil
        self.distro_patcher = patching
        self.logger = logger
        self.ide_class_id = "{32412632-86cb-44a2-9b5c-50d1417354f5}"
        self.vmbus_sys_path = '/sys/bus/vmbus/devices'

        self.command_executor = CommandExecutor(self.logger)

        self._LUN_PREFIX = "lun"
        self._SCSI_PREFIX = "scsi"

    def get_osmapper_path(self):
        return os.path.join(CommonVariables.dev_mapper_root, CommonVariables.osmapper_name)

    def copy(self, ongoing_item_config, status_prefix=''):
        copy_task = TransactionalCopyTask(logger=self.logger,
                                          disk_util=self,
                                          hutil=self.hutil,
                                          ongoing_item_config=ongoing_item_config,
                                          patching=self.distro_patcher,
                                          encryption_environment=self.encryption_environment,
                                          status_prefix=status_prefix)
        try:
            mem_fs_result = copy_task.prepare_mem_fs()
            if mem_fs_result != CommonVariables.process_success:
                return CommonVariables.tmpfs_error
            else:
                return copy_task.begin_copy()
        except Exception as e:
            message = "Failed to perform dd copy: {0}, stack trace: {1}".format(e, traceback.format_exc())
            self.logger.log(msg=message, level=CommonVariables.ErrorLevel)
        finally:
            copy_task.clear_mem_fs()

    def format_disk(self, dev_path, file_system):
        mkfs_command = ""
        if file_system in CommonVariables.format_supported_file_systems:
            mkfs_command = "mkfs." + file_system
        mkfs_cmd = "{0} {1}".format(mkfs_command, dev_path)
        return self.command_executor.Execute(mkfs_cmd)

    def make_sure_path_exists(self, path):
        mkdir_cmd = self.distro_patcher.mkdir_path + ' -p ' + path
        self.logger.log("make sure path exists, executing: {0}".format(mkdir_cmd))
        return self.command_executor.Execute(mkdir_cmd)

    def touch_file(self, path):
        mkdir_cmd = self.distro_patcher.touch_path + ' ' + path
        self.logger.log("touching file, executing: {0}".format(mkdir_cmd))
        return self.command_executor.Execute(mkdir_cmd)

    def create_luks_header(self, mapper_name):
        luks_header_file_path = self.encryption_environment.luks_header_base_path + mapper_name
        if not os.path.exists(luks_header_file_path):
            dd_command = self.distro_patcher.dd_path + ' if=/dev/zero bs=33554432 count=1 > ' + luks_header_file_path
            self.command_executor.ExecuteInBash(dd_command, raise_exception_on_failure=True)
        return luks_header_file_path

    def create_cleartext_key(self, mapper_name):
        cleartext_key_file_path = self.encryption_environment.cleartext_key_base_path + mapper_name
        if not os.path.exists(cleartext_key_file_path):
            dd_command = self.distro_patcher.dd_path + ' if=/dev/urandom bs=128 count=1 > ' + cleartext_key_file_path
            self.command_executor.ExecuteInBash(dd_command, raise_exception_on_failure=True)
        return cleartext_key_file_path

    def encrypt_disk(self, dev_path, passphrase_file, mapper_name, header_file):
        return_code = self.luks_format(passphrase_file=passphrase_file, dev_path=dev_path, header_file=header_file)
        if return_code != CommonVariables.process_success:
            self.logger.log(msg=('cryptsetup luksFormat failed, return_code is:{0}'.format(return_code)), level=CommonVariables.ErrorLevel)
            return return_code
        else:
            return_code = self.luks_open(passphrase_file=passphrase_file,
                                         dev_path=dev_path,
                                         mapper_name=mapper_name,
                                         header_file=header_file,
                                         uses_cleartext_key=False)
            if return_code != CommonVariables.process_success:
                self.logger.log(msg=('cryptsetup luksOpen failed, return_code is:{0}'.format(return_code)), level=CommonVariables.ErrorLevel)
            return return_code

    def check_fs(self, dev_path):
        self.logger.log("checking fs:" + str(dev_path))
        check_fs_cmd = self.distro_patcher.e2fsck_path + " -f -y " + dev_path
        return self.command_executor.Execute(check_fs_cmd)

    def expand_fs(self, dev_path):
        expandfs_cmd = self.distro_patcher.resize2fs_path + " " + str(dev_path)
        return self.command_executor.Execute(expandfs_cmd)

    def shrink_fs(self, dev_path, size_shrink_to):
        """
        size_shrink_to is in sector (512 byte)
        """
        shrinkfs_cmd = self.distro_patcher.resize2fs_path + ' ' + str(dev_path) + ' ' + str(size_shrink_to) + 's'
        return self.command_executor.Execute(shrinkfs_cmd)

    def check_shrink_fs(self, dev_path, size_shrink_to):
        return_code = self.check_fs(dev_path)
        if return_code == CommonVariables.process_success:
            return_code = self.shrink_fs(dev_path=dev_path, size_shrink_to=size_shrink_to)
            return return_code
        else:
            return return_code

    def luks_format(self, passphrase_file, dev_path, header_file):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("dev path to cryptsetup luksFormat {0}".format(dev_path))
        # walkaround for sles sp3
        if self.distro_patcher.distro_info[0].lower() == 'suse' and self.distro_patcher.distro_info[1] == '11':
            proc_comm = ProcessCommunicator()
            passphrase_cmd = self.distro_patcher.cat_path + ' ' + passphrase_file
            self.command_executor.Execute(passphrase_cmd, communicator=proc_comm)
            passphrase = proc_comm.stdout.decode("utf-8")

            cryptsetup_cmd = "{0} luksFormat {1} -q".format(self.distro_patcher.cryptsetup_path, dev_path)
            return self.command_executor.Execute(cryptsetup_cmd, input=passphrase)
        else:
            if header_file is not None:
                cryptsetup_cmd = "{0} luksFormat {1} --header {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path, dev_path, header_file, passphrase_file)
            else:
                cryptsetup_cmd = "{0} luksFormat {1} -d {2} -q".format(self.distro_patcher.cryptsetup_path, dev_path, passphrase_file)

            return self.command_executor.Execute(cryptsetup_cmd)

    def luks_add_key(self, passphrase_file, dev_path, mapper_name, header_file, new_key_path):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("new key path: " + (new_key_path))

        if not os.path.exists(new_key_path):
            self.hutil.error("new key does not exist")
            return None

        if header_file:
            cryptsetup_cmd = "{0} luksAddKey {1} {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path, header_file, new_key_path, passphrase_file)
        else:
            cryptsetup_cmd = "{0} luksAddKey {1} {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path, dev_path, new_key_path, passphrase_file)

        return self.command_executor.Execute(cryptsetup_cmd)

    def luks_remove_key(self, passphrase_file, dev_path, header_file):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("removing keyslot: {0}".format(passphrase_file))

        if header_file:
            cryptsetup_cmd = "{0} luksRemoveKey {1} -d {2} -q".format(self.distro_patcher.cryptsetup_path, header_file, passphrase_file)
        else:
            cryptsetup_cmd = "{0} luksRemoveKey {1} -d {2} -q".format(self.distro_patcher.cryptsetup_path, dev_path, passphrase_file)

        return self.command_executor.Execute(cryptsetup_cmd)

    def luks_kill_slot(self, passphrase_file, dev_path, header_file, keyslot):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("killing keyslot: {0}".format(keyslot))

        if header_file:
            cryptsetup_cmd = "{0} luksKillSlot {1} {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path, header_file, keyslot, passphrase_file)
        else:
            cryptsetup_cmd = "{0} luksKillSlot {1} {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path, dev_path, keyslot, passphrase_file)

        return self.command_executor.Execute(cryptsetup_cmd)

    def luks_add_cleartext_key(self, passphrase_file, dev_path, mapper_name, header_file):
        """
        return the return code of the process for error handling.
        """
        cleartext_key_file_path = self.encryption_environment.cleartext_key_base_path + mapper_name

        self.hutil.log("cleartext key path: " + (cleartext_key_file_path))

        return self.luks_add_key(passphrase_file, dev_path, mapper_name, header_file, cleartext_key_file_path)

    def luks_dump_keyslots(self, dev_path, header_file):
        cryptsetup_cmd = ""
        if header_file:
            cryptsetup_cmd = "{0} luksDump {1}".format(self.distro_patcher.cryptsetup_path, header_file)
        else:
            cryptsetup_cmd = "{0} luksDump {1}".format(self.distro_patcher.cryptsetup_path, dev_path)

        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(cryptsetup_cmd, communicator=proc_comm)

        lines = [l for l in proc_comm.stdout.decode("utf-8").split("\n") if "key slot" in l.lower()]
        keyslots = ["enabled" in l.lower() for l in lines]

        return keyslots

    def luks_open(self, passphrase_file, dev_path, mapper_name, header_file, uses_cleartext_key):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("dev mapper name to cryptsetup luksOpen " + (mapper_name))

        if uses_cleartext_key:
            passphrase_file = self.encryption_environment.cleartext_key_base_path + mapper_name

        self.hutil.log("keyfile: " + (passphrase_file))

        if header_file:
            cryptsetup_cmd = "{0} luksOpen {1} {2} --header {3} -d {4} -q".format(self.distro_patcher.cryptsetup_path, dev_path, mapper_name, header_file, passphrase_file)
        else:
            cryptsetup_cmd = "{0} luksOpen {1} {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path, dev_path, mapper_name, passphrase_file)

        return self.command_executor.Execute(cryptsetup_cmd)

    def luks_close(self, mapper_name):
        """
        returns the exit code for cryptsetup process.
        """
        self.hutil.log("dev mapper name to cryptsetup luksClose " + (mapper_name))
        cryptsetup_cmd = "{0} luksClose {1} -q".format(self.distro_patcher.cryptsetup_path, mapper_name)

        return self.command_executor.Execute(cryptsetup_cmd)

    def mount_by_label(self, label, mount_point, option_string=None):
        """
        mount the BEK volume
        """
        self.make_sure_path_exists(mount_point)
        if option_string is not None and option_string != "":
            mount_cmd = self.distro_patcher.mount_path + ' -L "' + label + '" ' + mount_point + ' -o ' + option_string
        else:
            mount_cmd = self.distro_patcher.mount_path + ' -L "' + label + '" ' + mount_point

        return self.command_executor.Execute(mount_cmd)

    def mount_auto(self, dev_path_or_mount_point):
        """
        mount the file system via fstab entry
        """
        mount_cmd = self.distro_patcher.mount_path + ' ' + dev_path_or_mount_point
        return self.command_executor.Execute(mount_cmd)

    def mount_filesystem(self, dev_path, mount_point, file_system=None):
        """
        mount the file system.
        """
        self.make_sure_path_exists(mount_point)
        if file_system is None:
            mount_cmd = self.distro_patcher.mount_path + ' ' + dev_path + ' ' + mount_point
        else:
            mount_cmd = self.distro_patcher.mount_path + ' ' + dev_path + ' ' + mount_point + ' -t ' + file_system

        return self.command_executor.Execute(mount_cmd)

    def mount_crypt_item(self, crypt_item, passphrase):
        self.logger.log("trying to mount the crypt item:" + str(crypt_item))
        self.logger.log(msg=('First trying to auto mount for the item'))
        mount_filesystem_result = self.mount_auto(os.path.join(CommonVariables.dev_mapper_root, crypt_item.mapper_name))
        if str(crypt_item.mount_point) != 'None' and mount_filesystem_result != CommonVariables.process_success:
            self.logger.log(msg=('mount_point is not None and auto mount failed. Trying manual mount.'), level=CommonVariables.WarningLevel)
            mount_filesystem_result = self.mount_filesystem(os.path.join(CommonVariables.dev_mapper_root, crypt_item.mapper_name),
                                                            crypt_item.mount_point,
                                                            crypt_item.file_system)
            self.logger.log("mount file system result:{0}".format(mount_filesystem_result))

    def swapoff(self):
        return self.command_executor.Execute('swapoff -a')

    def umount(self, path):
        umount_cmd = self.distro_patcher.umount_path + ' ' + path
        return self.command_executor.Execute(umount_cmd)

    def mount_all(self):
        mount_all_cmd = self.distro_patcher.mount_path + ' -a'
        return self.command_executor.Execute(mount_all_cmd)

    def get_mount_items(self):
        items = []

        for line in open('/proc/mounts'):
            #P3TODO - used to be s.decode('string_escape') need to update this to be both python2 and 3 compatible
            #P3STR - string sensitive change 
            line = [s for s in line.split()]
            item = {
                "src": line[0],
                "dest": line[1],
                "fs": line[2]
            }
            items.append(item)

        return items

    def is_in_memfs_root(self):
        # TODO: make this more robust. This could fail due to mount paths with spaces and tmpfs (e.g. '/mnt/ tmpfs')
        mounts = open('/proc/mounts', 'r').read()
        return bool(re.search(r'/\s+tmpfs', mounts))

    def get_encryption_status(self):
        encryption_status = {
            "data": "NotEncrypted",
            "os": "NotEncrypted"
        }

        mount_items = self.get_mount_items()
        device_items = self.get_device_items(None)
        device_items_dict = dict([(device_item.mount_point, device_item) for device_item in device_items])

        os_drive_encrypted = False
        data_drives_found = False
        all_data_drives_encrypted = True

        if self.is_os_disk_lvm():
            grep_result = self.command_executor.ExecuteInBash('pvdisplay | grep {0}'.format(self.get_osmapper_path()),
                                                              suppress_logging=True)
            if grep_result == 0 and not os.path.exists('/volumes.lvm'):
                self.logger.log("OS PV is encrypted")
                os_drive_encrypted = True

        special_azure_devices_to_skip = self.get_azure_devices()
        for mount_item in mount_items:
            device_item = device_items_dict.get(mount_item["dest"])

            if device_item is not None and \
               mount_item["fs"] in CommonVariables.format_supported_file_systems and \
               self.is_data_disk(device_item, special_azure_devices_to_skip):
                data_drives_found = True

                if not device_item.type == "crypt":
                    self.logger.log("Data volume {0} is mounted from {1}".format(mount_item["dest"], mount_item["src"]))
                    all_data_drives_encrypted = False

            if mount_item["dest"] == "/" and \
               not self.is_os_disk_lvm() and \
               CommonVariables.dev_mapper_root in mount_item["src"] or \
               "/dev/dm" in mount_item["src"]:
                self.logger.log("OS volume {0} is mounted from {1}".format(mount_item["dest"], mount_item["src"]))
                os_drive_encrypted = True

        if not data_drives_found:
            encryption_status["data"] = "NotMounted"
        elif all_data_drives_encrypted:
            encryption_status["data"] = "Encrypted"
        if os_drive_encrypted:
            encryption_status["os"] = "Encrypted"

        encryption_marker = EncryptionMarkConfig(self.logger, self.encryption_environment)
        decryption_marker = DecryptionMarkConfig(self.logger, self.encryption_environment)
        if decryption_marker.config_file_exists():
            print(decryption_marker.config_file_exists)
            encryption_status["data"] = "DecryptionInProgress"
        elif encryption_marker.config_file_exists():
            encryption_config = EncryptionConfig(self.encryption_environment, self.logger)
            volume_type = encryption_config.get_volume_type().lower()

            if volume_type == CommonVariables.VolumeTypeData.lower() or \
               volume_type == CommonVariables.VolumeTypeAll.lower():
                encryption_status["data"] = "EncryptionInProgress"

            if volume_type == CommonVariables.VolumeTypeOS.lower() or \
               volume_type == CommonVariables.VolumeTypeAll.lower():
                if not os_drive_encrypted:
                    encryption_status["os"] = "EncryptionInProgress"
        elif os.path.exists(self.get_osmapper_path()) and not os_drive_encrypted:
            encryption_status["os"] = "VMRestartPending"

        return json.dumps(encryption_status)

    def query_dev_sdx_path_by_scsi_id(self, scsi_number):
        p = Popen([self.distro_patcher.lsscsi_path, scsi_number], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        identity, err = p.communicate()
        # identity sample: [5:0:0:0] disk Msft Virtual Disk 1.0 /dev/sdc
        self.logger.log("lsscsi output is: {0}\n".format(identity))
        vals = identity.split()
        if vals is None or len(vals) == 0:
            return None
        sdx_path = vals[len(vals) - 1]
        return sdx_path

    def query_dev_sdx_path_by_uuid(self, uuid):
        """
        return /dev/disk/by-id that maps to the sdx_path, otherwise return the original path
        """
        desired_uuid_path = os.path.join(CommonVariables.disk_by_uuid_root, uuid)
        for disk_by_uuid in os.listdir(CommonVariables.disk_by_uuid_root):
            disk_by_uuid_path = os.path.join(CommonVariables.disk_by_uuid_root, disk_by_uuid)

            if disk_by_uuid_path == desired_uuid_path:
                return os.path.realpath(disk_by_uuid_path)

        return desired_uuid_path

    def query_dev_id_path_by_sdx_path(self, sdx_path):
        """
        return /dev/disk/by-id that maps to the sdx_path, otherwise return the original path
        Update: now we have realised that by-id is not a good way to refer to devices (they can change on reallocations or resizes).
        Try not to use this- use get_stable_path_from_sdx instead
        """
        for disk_by_id in os.listdir(CommonVariables.disk_by_id_root):
            disk_by_id_path = os.path.join(CommonVariables.disk_by_id_root, disk_by_id)
            if os.path.realpath(disk_by_id_path) == sdx_path:
                return disk_by_id_path

        return sdx_path

    def get_persistent_path_by_sdx_path(self, sdx_path):
        """
        return a stable path for this /dev/sdx device
        """
        sdx_realpath = os.path.realpath(sdx_path)

        # First try finding an Azure symlink
        azure_name_table = self.get_block_device_to_azure_udev_table()
        if sdx_realpath in azure_name_table:
            return azure_name_table[sdx_realpath]

        # A mapper path is also pretty good (especially for raid or lvm)
        for mapper_name in os.listdir(CommonVariables.dev_mapper_root):
            mapper_path = os.path.join(CommonVariables.dev_mapper_root, mapper_name)
            if os.path.realpath(mapper_path) == sdx_realpath:
                return mapper_path

        # Then try matching a uuid symlink. Those are probably the best
        for disk_by_uuid in os.listdir(CommonVariables.disk_by_uuid_root):
            disk_by_uuid_path = os.path.join(CommonVariables.disk_by_uuid_root, disk_by_uuid)

            if os.path.realpath(disk_by_uuid_path) == sdx_realpath:
                return disk_by_uuid_path

        # Found nothing very persistent. Just return the original sdx path.
        # And Log it.
        self.logger.log(msg="Failed to find a persistent path for [{0}].".format(sdx_path), level=CommonVariables.WarningLevel)

        return sdx_path

    def get_device_path(self, dev_name):
        device_path = None
        dev_name = str(dev_name)

        if os.path.exists("/dev/" + dev_name):
            device_path = "/dev/" + dev_name
        elif os.path.exists(os.path.join(CommonVariables.dev_mapper_root, dev_name)):
            device_path = os.path.join(CommonVariables.dev_mapper_root, dev_name)

        return device_path

    def get_device_id(self, dev_path):
        udev_cmd = "udevadm info -a -p $(udevadm info -q path -n {0}) | grep device_id".format(dev_path)
        proc_comm = ProcessCommunicator()
        self.command_executor.ExecuteInBash(udev_cmd, communicator=proc_comm, suppress_logging=True)
        match = re.findall(r'"{(.*)}"', proc_comm.stdout.decode("utf-8").strip())
        return match[0] if match else ""

    def get_device_items_property(self, dev_name, property_name):
        if (dev_name, property_name) in DiskUtil.sles_cache:
            return DiskUtil.sles_cache[(dev_name, property_name)]

        self.logger.log("getting property of device {0}".format(dev_name))

        device_path = self.get_device_path(dev_name)
        property_value = ""

        if property_name == "SIZE":
            get_property_cmd = self.distro_patcher.blockdev_path + " --getsize64 " + device_path
            proc_comm = ProcessCommunicator()
            self.command_executor.Execute(get_property_cmd, communicator=proc_comm, suppress_logging=True)
            property_value = proc_comm.stdout.decode("utf-8").strip()
        elif property_name == "DEVICE_ID":
            property_value = self.get_device_id(device_path)
        else:
            get_property_cmd = self.distro_patcher.lsblk_path + " " + device_path + " -b -nl -o NAME," + property_name
            proc_comm = ProcessCommunicator()
            self.command_executor.Execute(get_property_cmd, communicator=proc_comm, raise_exception_on_failure=True, suppress_logging=True)
            for line in proc_comm.stdout.decode("utf-8").splitlines():
                if line.strip():
                    disk_info_item_array = line.strip().split()
                    if dev_name == disk_info_item_array[0]:
                        if len(disk_info_item_array) > 1:
                            property_value = disk_info_item_array[1]

        DiskUtil.sles_cache[(dev_name, property_name)] = property_value
        return property_value

    def get_block_device_to_azure_udev_table(self):
        table = {}
        azure_links_dir = CommonVariables.azure_symlinks_dir

        if not os.path.exists(azure_links_dir):
            return table

        for top_level_item in os.listdir(azure_links_dir):
            top_level_item_full_path = os.path.join(azure_links_dir, top_level_item)
            if os.path.isdir(top_level_item_full_path):
                scsi_path = os.path.join(azure_links_dir, top_level_item)
                for symlink in os.listdir(scsi_path):
                    symlink_full_path = os.path.join(scsi_path, symlink)
                    table[os.path.realpath(symlink_full_path)] = symlink_full_path
            else:
                table[os.path.realpath(top_level_item_full_path)] = top_level_item_full_path
        return table

    def is_parent_of_any(self, parent_dev_path, children_dev_path_set):
        """
        check if the device whose path is parent_dev_path is actually a parent of any of the children in children_dev_path_set
        All the paths need to be "realpaths" (not symlinks)
        """
        actual_children_dev_items = self.get_device_items(parent_dev_path)
        actual_children_dev_path_set = set([os.path.realpath(self.get_device_path(di.name)) for di in actual_children_dev_items])
        # the sets being disjoint would mean the candidate parent is not parent of any of the candidate children. So we return the opposite of that
        return not actual_children_dev_path_set.isdisjoint(children_dev_path_set)

    def get_all_azure_data_disk_controller_and_lun_numbers(self):
        """
        Return the controller ids and lun numbers for data disks that show up in the dev_items
        """
        list_devices = []
        azure_links_dir = CommonVariables.azure_symlinks_dir

        if not os.path.exists(azure_links_dir):
            return list_devices

        for top_level_item in os.listdir(azure_links_dir):
            top_level_item_full_path = os.path.join(azure_links_dir, top_level_item)
            if os.path.isdir(top_level_item_full_path) and top_level_item.startswith(self._SCSI_PREFIX):
                # this works because apparently all data disks go int a scsi[x] where x is one of [1,2,3,4]
                try:
                    controller_id = int(top_level_item[4:])  # strip the first 4 letters of the folder
                except ValueError:
                    # if its not an integer, probably just best to skip it
                    continue

                for symlink in os.listdir(top_level_item_full_path):
                    if symlink.startswith(self._LUN_PREFIX):
                        try:
                            lun_number = int(symlink[3:])
                        except ValueError:
                            # parsing will fail if "symlink" was a partition (e.g. "lun0-part1")
                            continue  # so just ignore it
                        list_devices.append((controller_id, lun_number))
        return list_devices

    def get_azure_data_disk_controller_and_lun_numbers(self, dev_items_real_paths):
        """
        Return the controller ids and lun numbers for data disks that show up in the dev_items
        """

        all_controller_and_lun_numbers = self.get_all_azure_data_disk_controller_and_lun_numbers()

        list_devices = []
        azure_links_dir = CommonVariables.azure_symlinks_dir

        for controller_id, lun_number in all_controller_and_lun_numbers:
            scsi_dir = os.path.join(azure_links_dir, self._SCSI_PREFIX + str(controller_id))
            symlink = os.path.join(scsi_dir, self._LUN_PREFIX + str(lun_number))
            if self.is_parent_of_any(os.path.realpath(symlink), dev_items_real_paths):
                list_devices.append((controller_id, lun_number))

        return list_devices

    def log_lsblk_output(self):
        lsblk_command = 'lsblk -o NAME,TYPE,FSTYPE,LABEL,SIZE,RO,MOUNTPOINT'
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(lsblk_command, communicator=proc_comm)
        output = proc_comm.stdout.decode("utf-8")
        self.logger.log('\n' + output + '\n')
    def get_device_items_sles(self, dev_path):
        if dev_path:
            self.logger.log(msg=("getting blk info for: {0}".format(dev_path)))
        device_items_to_return = []
        device_items = []

        # first get all the device names
        if dev_path is None:
            lsblk_command = 'lsblk -b -nl -o NAME'
        else:
            lsblk_command = 'lsblk -b -nl -o NAME ' + dev_path

        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(lsblk_command, communicator=proc_comm, raise_exception_on_failure=True)

        for line in proc_comm.stdout.decode("utf-8").splitlines():
            item_value_str = line.strip()
            if item_value_str:
                device_item = DeviceItem()
                device_item.name = item_value_str.split()[0]
                device_items.append(device_item)

        for device_item in device_items:
            device_item.file_system = self.get_device_items_property(dev_name=device_item.name, property_name='FSTYPE')
            device_item.mount_point = self.get_device_items_property(dev_name=device_item.name, property_name='MOUNTPOINT')
            device_item.label = self.get_device_items_property(dev_name=device_item.name, property_name='LABEL')
            device_item.uuid = self.get_device_items_property(dev_name=device_item.name, property_name='UUID')
            device_item.majmin = self.get_device_items_property(dev_name=device_item.name, property_name='MAJ:MIN')
            device_item.device_id = self.get_device_items_property(dev_name=device_item.name, property_name='DEVICE_ID')

            # get the type of device
            model_file_path = '/sys/block/' + device_item.name + '/device/model'

            if os.path.exists(model_file_path):
                with open(model_file_path, 'r') as f:
                    device_item.model = f.read().strip()
            else:
                self.logger.log(msg=("no model file found for device {0}".format(device_item.name)))

            if device_item.model == 'Virtual Disk':
                self.logger.log(msg="model is virtual disk")
                device_item.type = 'disk'
            else:
                partition_files = glob.glob('/sys/block/*/' + device_item.name + '/partition')
                self.logger.log(msg="partition files exists")
                if partition_files is not None and len(partition_files) > 0:
                    device_item.type = 'part'

            size_string = self.get_device_items_property(dev_name=device_item.name, property_name='SIZE')

            if size_string is not None and size_string != "":
                device_item.size = int(size_string)

            if device_item.type is None:
                device_item.type = ''

            if device_item.size is not None:
                device_items_to_return.append(device_item)
            else:
                self.logger.log(msg=("skip the device {0} because we could not get size of it.".format(device_item.name)))

        return device_items_to_return

    def get_device_items(self, dev_path):
        if self.distro_patcher.distro_info[0].lower() == 'suse' and self.distro_patcher.distro_info[1] == '11':
            return self.get_device_items_sles(dev_path)
        else:
            if dev_path:
                self.logger.log(msg=("getting blk info for: " + str(dev_path)))

            if dev_path is None:
                lsblk_command = 'lsblk -b -n -P -o NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE,MAJ:MIN'
            else:
                lsblk_command = 'lsblk -b -n -P -o NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE,MAJ:MIN ' + dev_path

            proc_comm = ProcessCommunicator()
            self.command_executor.Execute(lsblk_command, communicator=proc_comm, raise_exception_on_failure=True, suppress_logging=True)

            device_items = []
            lvm_items = self.get_lvm_items()
            for line in proc_comm.stdout.decode("utf-8").splitlines():
                if line:
                    device_item = DeviceItem()

                    for disk_info_property in str(line).split():
                        property_item_pair = disk_info_property.split('=')
                        if property_item_pair[0] == 'SIZE':
                            device_item.size = int(property_item_pair[1].strip('"'))

                        if property_item_pair[0] == 'NAME':
                            device_item.name = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'TYPE':
                            device_item.type = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'FSTYPE':
                            device_item.file_system = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'MOUNTPOINT':
                            device_item.mount_point = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'LABEL':
                            device_item.label = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'UUID':
                            device_item.uuid = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'MODEL':
                            device_item.model = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'MAJ:MIN':
                            device_item.majmin = property_item_pair[1].strip('"')

                    device_item.device_id = self.get_device_id(self.get_device_path(device_item.name))

                    if device_item.type is None:
                        device_item.type = ''

                    if device_item.type.lower() == 'lvm':
                        for lvm_item in lvm_items:
                            majmin = lvm_item.lv_kernel_major + ':' + lvm_item.lv_kernel_minor

                            if majmin == device_item.majmin:
                                device_item.name = lvm_item.vg_name + '/' + lvm_item.lv_name

                    device_items.append(device_item)

            return device_items

    def get_lvm_items(self):
        lvs_command = 'lvs --noheadings --nameprefixes --unquoted -o lv_name,vg_name,lv_kernel_major,lv_kernel_minor'
        proc_comm = ProcessCommunicator()

        if self.command_executor.Execute(lvs_command, communicator=proc_comm):
            return []

        lvm_items = []

        for line in proc_comm.stdout.decode("utf-8").splitlines():
            if not line:
                continue

            lvm_item = LvmItem()

            for pair in str(line).strip().split():
                if len(pair.split('=')) != 2:
                    continue

                key, value = pair.split('=')

                if key == 'LVM2_LV_NAME':
                    lvm_item.lv_name = value

                if key == 'LVM2_VG_NAME':
                    lvm_item.vg_name = value

                if key == 'LVM2_LV_KERNEL_MAJOR':
                    lvm_item.lv_kernel_major = value

                if key == 'LVM2_LV_KERNEL_MINOR':
                    lvm_item.lv_kernel_minor = value

            lvm_items.append(lvm_item)

        return lvm_items

    def is_os_disk_lvm(self):
        if DiskUtil.os_disk_lvm is not None:
            return DiskUtil.os_disk_lvm

        device_items = self.get_device_items(None)

        if not any([item.type.lower() == 'lvm' for item in device_items]):
            DiskUtil.os_disk_lvm = False
            return False

        lvm_items = [item for item in self.get_lvm_items() if item.vg_name == "rootvg"]

        current_lv_names = set([item.lv_name for item in lvm_items])

        DiskUtil.os_disk_lvm = False

        expected_lv_names = set(['homelv', 'optlv', 'rootlv', 'swaplv', 'tmplv', 'usrlv', 'varlv'])
        if expected_lv_names == current_lv_names:
            DiskUtil.os_disk_lvm = True

        expected_lv_names = set(['homelv', 'optlv', 'rootlv', 'tmplv', 'usrlv', 'varlv'])
        if expected_lv_names == current_lv_names:
            DiskUtil.os_disk_lvm = True

        return DiskUtil.os_disk_lvm

    def is_data_disk(self, device_item, special_azure_devices_to_skip):
        # Root disk
        if device_item.device_id.startswith('00000000-0000'):
            self.logger.log(msg="skipping root disk", level=CommonVariables.WarningLevel)
            return False
        # Resource Disk. Not considered a "data disk" exactly (is not attached via portal and we have a separate code path for encrypting it)
        if device_item.device_id.startswith('00000000-0001'):
            self.logger.log(msg="skipping resource disk", level=CommonVariables.WarningLevel)
            return False
        # BEK VOLUME
        if device_item.file_system == "vfat" and device_item.label.lower() == "bek":
            self.logger.log(msg="skipping BEK VOLUME", level=CommonVariables.WarningLevel)
            return False

        # We let the caller specify a list of devices to skip. Usually its just a list of IDE devices.
        # IDE devices (in Gen 1) include Resource disk and BEK VOLUME. This check works pretty wel in Gen 1, but not in Gen 2.
        for azure_blk_item in special_azure_devices_to_skip:
            if azure_blk_item.name == device_item.name:
                if device_item.name:
                    self.logger.log(msg="{0} is one of special azure devices that should be not considered data disks.".format(device_item.name))
                return False

        return True

    def should_skip_for_inplace_encryption(self, device_item, special_azure_devices_to_skip, encrypt_volume_type):
        """
        TYPE="raid0"
        TYPE="part"
        TYPE="crypt"

        first check whether there's one file system on it.
        if the type is disk, then to check whether it have child-items, say the part, lvm or crypt luks.
        if the answer is yes, then skip it.
        """

        if encrypt_volume_type.lower() == 'data' and not self.is_data_disk(device_item, special_azure_devices_to_skip):
            return True  # Skip non-data disks

        if device_item.file_system is None or device_item.file_system == "":
            self.logger.log(msg=("there's no file system on this device: {0}, so skip it.").format(device_item))
            return True
        else:
            if device_item.size < CommonVariables.min_filesystem_size_support:
                self.logger.log(msg="the device size is too small," + str(device_item.size) + " so skip it.", level=CommonVariables.WarningLevel)
                return True

            supported_device_type = ["disk", "part", "raid0", "raid1", "raid5", "raid10", "lvm"]
            if device_item.type not in supported_device_type:
                self.logger.log(msg="the device type: " + str(device_item.type) + " is not supported yet, so skip it.", level=CommonVariables.WarningLevel)
                return True

            if device_item.uuid is None or device_item.uuid == "":
                self.logger.log(msg="the device do not have the related uuid, so skip it.", level=CommonVariables.WarningLevel)
                return True
            sub_items = self.get_device_items(self.get_device_path(device_item.name))
            if len(sub_items) > 1:
                self.logger.log(msg=("there's sub items for the device:{0} , so skip it.".format(device_item.name)), level=CommonVariables.WarningLevel)
                return True

            if device_item.type == "crypt":
                self.logger.log(msg=("device_item.type is:{0}, so skip it.".format(device_item.type)), level=CommonVariables.WarningLevel)
                return True

            if device_item.mount_point == "/":
                self.logger.log(msg=("the mountpoint is root:{0}, so skip it.".format(device_item)), level=CommonVariables.WarningLevel)
                return True

            for azure_blk_item in special_azure_devices_to_skip:
                if azure_blk_item.name == device_item.name:
                    self.logger.log(msg="the mountpoint is the azure disk root or resource, so skip it.")
                    return True
            return False

    def get_azure_devices(self):
        ide_devices = self.get_ide_devices()
        blk_items = []
        for ide_device in ide_devices:
            current_blk_items = self.get_device_items("/dev/" + ide_device)
            for current_blk_item in current_blk_items:
                blk_items.append(current_blk_item)
        return blk_items

    def get_ide_devices(self):
        """
        this only return the device names of the ide.
        """
        ide_devices = []
        for vmbus in os.listdir(self.vmbus_sys_path):
            f = open('%s/%s/%s' % (self.vmbus_sys_path, vmbus, 'class_id'), 'r')
            class_id = f.read()
            f.close()
            if class_id.strip() == self.ide_class_id:
                device_sdx_path = self.find_block_sdx_path(vmbus)
                self.logger.log("found one ide with vmbus: {0} and the sdx path is: {1}".format(vmbus,
                                                                                                device_sdx_path))
                ide_devices.append(device_sdx_path)
        return ide_devices

    def find_block_sdx_path(self, vmbus):
        device = None
        for root, dirs, files in os.walk(os.path.join(self.vmbus_sys_path, vmbus)):
            if root.endswith("/block"):
                device = dirs[0]
            else:  # older distros
                for d in dirs:
                    if ':' in d and "block" == d.split(':')[0]:
                        device = d.split(':')[1]
                        break
        return device
