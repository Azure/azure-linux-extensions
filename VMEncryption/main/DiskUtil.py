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
import shlex
import sys
from subprocess import *
import shutil
import traceback
import uuid
import glob

from EncryptionConfig import EncryptionConfig
from DecryptionMarkConfig import DecryptionMarkConfig
from EncryptionMarkConfig import EncryptionMarkConfig
from TransactionalCopyTask import TransactionalCopyTask
from CommandExecutor import *
from Common import *

class DiskUtil(object):
    os_disk_lvm = None
    sles_cache = {}
    device_id_cache = {}

    def __init__(self, hutil, patching, logger, encryption_environment):
        self.encryption_environment = encryption_environment
        self.hutil = hutil
        self.distro_patcher = patching
        self.logger = logger
        self.ide_class_id = "{32412632-86cb-44a2-9b5c-50d1417354f5}"
        self.vmbus_sys_path = '/sys/bus/vmbus/devices'

        self.command_executor = CommandExecutor(self.logger)

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
        if file_system == "ext4":
            mkfs_command = "mkfs.ext4"
        elif file_system == "ext3":
            mkfs_command = "mkfs.ext3"
        elif file_system == "xfs":
            mkfs_command = "mkfs.xfs"
        elif file_system == "btrfs":
            mkfs_command = "mkfs.btrfs"
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

    def get_crypt_items(self):
        crypt_items = []
        rootfs_crypt_item_found = False

        if not os.path.exists(self.encryption_environment.azure_crypt_mount_config_path):
            self.logger.log("{0} does not exist".format(self.encryption_environment.azure_crypt_mount_config_path))
        else:
            with open(self.encryption_environment.azure_crypt_mount_config_path,'r') as f:
                for line in f:
                    if not line.strip():
                        continue

                    crypt_mount_item_properties = line.strip().split()

                    crypt_item = CryptItem()
                    crypt_item.mapper_name = crypt_mount_item_properties[0]
                    crypt_item.dev_path = crypt_mount_item_properties[1]

                    header_file_path = None
                    if crypt_mount_item_properties[2] and crypt_mount_item_properties[2] != "None":
                        header_file_path = crypt_mount_item_properties[2]

                    crypt_item.luks_header_path = header_file_path
                    crypt_item.mount_point = crypt_mount_item_properties[3]

                    if crypt_item.mount_point == "/":
                        rootfs_crypt_item_found = True

                    crypt_item.file_system = crypt_mount_item_properties[4]
                    crypt_item.uses_cleartext_key = True if crypt_mount_item_properties[5] == "True" else False

                    try:
                        crypt_item.current_luks_slot = int(crypt_mount_item_properties[6])
                    except IndexError:
                        crypt_item.current_luks_slot = -1

                    crypt_items.append(crypt_item)

            encryption_status = json.loads(self.get_encryption_status())

            if encryption_status["os"] == "Encrypted" and not rootfs_crypt_item_found:
                crypt_item = CryptItem()
                crypt_item.mapper_name = "osencrypt"

                proc_comm = ProcessCommunicator()
                grep_result = self.command_executor.ExecuteInBash("cryptsetup status osencrypt | grep device:", communicator=proc_comm)

                if grep_result == 0:
                    crypt_item.dev_path = proc_comm.stdout.strip().split()[1]
                else:
                    proc_comm = ProcessCommunicator()
                    self.command_executor.Execute("dmsetup table --target crypt", communicator=proc_comm)

                    for line in proc_comm.stdout.splitlines():
                        if 'osencrypt' in line:
                            majmin = filter(lambda p: re.match(r'\d+:\d+', p), line.split())[0]
                            src_device = filter(lambda d: d.majmin == majmin, self.get_device_items(None))[0]
                            crypt_item.dev_path = '/dev/' + src_device.name
                            break

                rootfs_dev = next((m for m in self.get_mount_items() if m["dest"] == "/"))
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

    def add_crypt_item(self, crypt_item):
        """
        TODO we should judge that the second time.
        format is like this:
        <target name> <source device> <key file> <options>
        """
        try:
            if not crypt_item.luks_header_path:
                crypt_item.luks_header_path = "None"

            mount_content_item = (crypt_item.mapper_name + " " +
                                  crypt_item.dev_path + " " +
                                  crypt_item.luks_header_path + " " +
                                  crypt_item.mount_point + " " +
                                  crypt_item.file_system + " " +
                                  str(crypt_item.uses_cleartext_key) + " " +
                                  str(crypt_item.current_luks_slot))

            if os.path.exists(self.encryption_environment.azure_crypt_mount_config_path):
                with open(self.encryption_environment.azure_crypt_mount_config_path,'r') as f:
                    existing_content = f.read()
                    if existing_content is not None and existing_content.strip() != "":
                        new_mount_content = existing_content + "\n" + mount_content_item
                    else:
                        new_mount_content = mount_content_item
            else:
                new_mount_content = mount_content_item

            with open(self.encryption_environment.azure_crypt_mount_config_path,'w') as wf:
                wf.write('\n')
                wf.write(new_mount_content)
                wf.write('\n')
            return True
        except Exception as e:
            return False

    def remove_crypt_item(self, crypt_item):
        if not os.path.exists(self.encryption_environment.azure_crypt_mount_config_path):
            return False

        try:
            mount_lines = []

            with open(self.encryption_environment.azure_crypt_mount_config_path, 'r') as f:
                mount_lines = f.readlines()

            filtered_mount_lines = filter(lambda line: not crypt_item.mapper_name in line, mount_lines)

            with open(self.encryption_environment.azure_crypt_mount_config_path, 'w') as wf:
                wf.write('\n')
                wf.write('\n'.join(filtered_mount_lines))
                wf.write('\n')

            return True

        except Exception as e:
            return False

    def update_crypt_item(self, crypt_item):
        self.logger.log("Updating entry for crypt item {0}".format(crypt_item))
        self.remove_crypt_item(crypt_item)
        self.add_crypt_item(crypt_item)

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
            return_code = self.shrink_fs(dev_path = dev_path, size_shrink_to = size_shrink_to)
            return return_code
        else:
            return return_code

    def luks_format(self, passphrase_file, dev_path, header_file):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("dev path to cryptsetup luksFormat {0}".format(dev_path))
        #walkaround for sles sp3
        if self.distro_patcher.distro_info[0].lower() == 'suse' and self.distro_patcher.distro_info[1] == '11':
            proc_comm = ProcessCommunicator()
            passphrase_cmd = self.distro_patcher.cat_path + ' ' + passphrase_file
            self.command_executor.Execute(passphrase_cmd, communicator=proc_comm)
            passphrase = proc_comm.stdout

            cryptsetup_cmd = "{0} luksFormat {1} -q".format(self.distro_patcher.cryptsetup_path, dev_path)
            return self.command_executor.Execute(cryptsetup_cmd, input=passphrase)
        else:
            if header_file is not None:
                cryptsetup_cmd = "{0} luksFormat {1} --header {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path , dev_path , header_file , passphrase_file)
            else:
                cryptsetup_cmd = "{0} luksFormat {1} -d {2} -q".format(self.distro_patcher.cryptsetup_path , dev_path , passphrase_file)
            
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

        lines = filter(lambda l: "key slot" in l.lower(), proc_comm.stdout.split("\n"))
        keyslots = map(lambda l: "enabled" in l.lower(), lines)

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
            cryptsetup_cmd = "{0} luksOpen {1} {2} --header {3} -d {4} -q".format(self.distro_patcher.cryptsetup_path , dev_path , mapper_name, header_file , passphrase_file)
        else:
            cryptsetup_cmd = "{0} luksOpen {1} {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path , dev_path , mapper_name , passphrase_file)

        return self.command_executor.Execute(cryptsetup_cmd)

    def luks_close(self, mapper_name):
        """
        returns the exit code for cryptsetup process.
        """
        self.hutil.log("dev mapper name to cryptsetup luksOpen " + (mapper_name))
        cryptsetup_cmd = "{0} luksClose {1} -q".format(self.distro_patcher.cryptsetup_path, mapper_name)

        return self.command_executor.Execute(cryptsetup_cmd)

    #TODO error handling.
    def append_mount_info(self, dev_path, mount_point):
        shutil.copy2('/etc/fstab', '/etc/fstab.backup.' + str(str(uuid.uuid4())))
        mount_content_item = dev_path + " " + mount_point + "  auto defaults 0 0"
        new_mount_content = ""
        with open("/etc/fstab",'r') as f:
            existing_content = f.read()
            new_mount_content = existing_content + "\n" + mount_content_item
        with open("/etc/fstab",'w') as wf:
            wf.write(new_mount_content)

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
                pattern = '\s' + re.escape(mount_point) + '\s'

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

    def restore_mount_info(self, mount_point):
        if not mount_point:
            self.logger.log("restore_mount_info: mount_point is empty")
            return

        shutil.copy2('/etc/fstab', '/etc/fstab.backup.' + str(str(uuid.uuid4())))

        filtered_contents = []
        removed_lines = []

        with open('/etc/fstab.azure.backup', 'r') as f:
            for line in f.readlines():
                line = line.strip()
                pattern = '\s' + re.escape(mount_point) + '\s'

                if re.search(pattern, line):
                    self.logger.log("removing fstab.azure.backup line: {0}".format(line))
                    removed_lines.append(line)
                    continue

                filtered_contents.append(line)

        with open('/etc/fstab.azure.backup', 'w') as f:
            f.write('\n')
            f.write('\n'.join(filtered_contents))
            f.write('\n')

        self.logger.log("fstab.azure.backup updated successfully")

        with open('/etc/fstab', 'a+') as f:
            f.write('\n')
            f.write('\n'.join(removed_lines))
            f.write('\n')

        self.logger.log("fstab updated successfully")

    def mount_filesystem(self, dev_path, mount_point, file_system=None):
        """
        mount the file system.
        """
        self.make_sure_path_exists(mount_point)
        return_code = -1
        if file_system is None:
            mount_cmd = self.distro_patcher.mount_path + ' ' + dev_path + ' ' + mount_point
        else: 
            mount_cmd = self.distro_patcher.mount_path + ' ' + dev_path + ' ' + mount_point + ' -t ' + file_system

        return self.command_executor.Execute(mount_cmd)

    def mount_crypt_item(self, crypt_item, passphrase):
        self.logger.log("trying to mount the crypt item:" + str(crypt_item))
        mount_filesystem_result = self.mount_filesystem(os.path.join('/dev/mapper', crypt_item.mapper_name), crypt_item.mount_point, crypt_item.file_system)
        self.logger.log("mount file system result:{0}".format(mount_filesystem_result))

    def swapoff(self):
        return self.command_executor.Execute('swapoff -a')

    def umount(self, path):
        umount_cmd = self.distro_patcher.umount_path + ' ' + path
        return self.command_executor.Execute(umount_cmd)

    def umount_all_crypt_items(self):
        for crypt_item in self.get_crypt_items():
            self.logger.log("Unmounting {0}".format(crypt_item.mount_point))
            self.umount(crypt_item.mount_point)

    def mount_all(self):
        mount_all_cmd = self.distro_patcher.mount_path + ' -a'
        return self.command_executor.Execute(mount_all_cmd)

    def get_mount_items(self):
        items = []

        for line in file('/proc/mounts'):
            line = [s.decode('string_escape') for s in line.split()]
            item = {
                "src": line[0],
                "dest": line[1],
                "fs": line[2]
            }
            items.append(item)

        return items

    def get_encryption_status(self):
        encryption_status = {
            "data": "NotEncrypted",
            "os": "NotEncrypted"
        }

        mount_items = self.get_mount_items()

        os_drive_encrypted = False
        data_drives_found = False
        data_drives_encrypted = True
        for mount_item in mount_items:
            if mount_item["fs"] in ["ext2", "ext4", "ext3", "xfs"] and \
                not "/mnt" == mount_item["dest"] and \
                not "/" == mount_item["dest"] and \
                not "/oldroot/mnt/resource" == mount_item["dest"] and \
                not "/oldroot/boot" == mount_item["dest"] and \
                not "/oldroot" == mount_item["dest"] and \
                not "/mnt/resource" == mount_item["dest"] and \
                not "/boot" == mount_item["dest"]:

                data_drives_found = True

                if not "/dev/mapper" in mount_item["src"]:
                    self.logger.log("Data volume {0} is mounted from {1}".format(mount_item["dest"], mount_item["src"]))
                    data_drives_encrypted = False

            if self.is_os_disk_lvm():
                grep_result = self.command_executor.ExecuteInBash('pvdisplay | grep /dev/mapper/osencrypt', suppress_logging=True)
                if grep_result == 0 and not os.path.exists('/volumes.lvm'):
                    self.logger.log("OS PV is encrypted")
                    os_drive_encrypted = True
            elif mount_item["dest"] == "/" and \
                "/dev/mapper" in mount_item["src"] or \
                "/dev/dm" in mount_item["src"]:
                self.logger.log("OS volume {0} is mounted from {1}".format(mount_item["dest"], mount_item["src"]))
                os_drive_encrypted = True
    
        if not data_drives_found:
            encryption_status["data"] = "NotMounted"
        elif data_drives_encrypted:
            encryption_status["data"] = "Encrypted"
        if os_drive_encrypted:
            encryption_status["os"] = "Encrypted"

        encryption_marker = EncryptionMarkConfig(self.logger, self.encryption_environment)
        decryption_marker = DecryptionMarkConfig(self.logger, self.encryption_environment)
        if decryption_marker.config_file_exists():
            encryption_status["data"] = "DecryptionInProgress"
        elif encryption_marker.config_file_exists():
            encryption_config = EncryptionConfig(self.encryption_environment, self.logger)
            volume_type = encryption_config.get_volume_type().lower()

            if volume_type == CommonVariables.VolumeTypeData.lower() or \
                volume_type == CommonVariables.VolumeTypeAll.lower():
                encryption_status["data"] = "EncryptionInProgress"

            if volume_type == CommonVariables.VolumeTypeOS.lower() or \
                volume_type == CommonVariables.VolumeTypeAll.lower():
                encryption_status["os"] = "EncryptionInProgress"
        elif os.path.exists('/dev/mapper/osencrypt') and not os_drive_encrypted:
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
        """
        for disk_by_id in os.listdir(CommonVariables.disk_by_id_root):
            disk_by_id_path = os.path.join(CommonVariables.disk_by_id_root, disk_by_id)
            if os.path.realpath(disk_by_id_path) == sdx_path:
                return disk_by_id_path

        return sdx_path

    def query_dev_uuid_path_by_sdx_path(self, sdx_path):
        """
        the behaviour is if we could get the uuid, then return, if not, just return the sdx.
        """
        self.logger.log("querying the sdx path of:{0}".format(sdx_path))
        #blkid path
        p = Popen([self.distro_patcher.blkid_path, sdx_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        identity, err = p.communicate()
        identity = identity.lower()
        self.logger.log("blkid output is: \n" + identity)
        uuid_pattern = 'uuid="'
        index_of_uuid = identity.find(uuid_pattern)
        identity = identity[index_of_uuid + len(uuid_pattern):]
        index_of_quote = identity.find('"')
        uuid = identity[0:index_of_quote]
        if uuid.strip() == "":
            #TODO this is strange?  BUGBUG
            return sdx_path
        return os.path.join("/dev/disk/by-uuid/", uuid)

    def query_dev_uuid_path_by_scsi_number(self, scsi_number):
        # find the scsi using the filter
        # TODO figure out why the disk formated using fdisk do not have uuid
        sdx_path = self.query_dev_sdx_path_by_scsi_id(scsi_number)
        return self.query_dev_uuid_path_by_sdx_path(sdx_path)

    def get_device_path(self, dev_name):
        device_path = None

        if os.path.exists("/dev/" + dev_name):
            device_path = "/dev/" + dev_name
        elif os.path.exists("/dev/mapper/" + dev_name):
            device_path = "/dev/mapper/" + dev_name

        return device_path

    def get_device_id(self, dev_path):
        if (dev_path) in DiskUtil.device_id_cache:
            return DiskUtil.device_id_cache[dev_path]

        udev_cmd = "udevadm info -a -p $(udevadm info -q path -n {0}) | grep device_id".format(dev_path)
        proc_comm = ProcessCommunicator()
        self.command_executor.ExecuteInBash(udev_cmd, communicator=proc_comm, suppress_logging=True)
        match = re.findall(r'"{(.*)}"', proc_comm.stdout.strip())
        DiskUtil.device_id_cache[dev_path] = match[0] if match else ""

        return DiskUtil.device_id_cache[dev_path]

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
            property_value = proc_comm.stdout.strip()
        elif property_name == "DEVICE_ID":
            property_value = self.get_device_id(device_path)
        else:
            get_property_cmd = self.distro_patcher.lsblk_path + " " + device_path + " -b -nl -o NAME," + property_name
            proc_comm = ProcessCommunicator()
            self.command_executor.Execute(get_property_cmd, communicator=proc_comm, raise_exception_on_failure=True, suppress_logging=True)
            for line in proc_comm.stdout.splitlines():
                if line.strip():
                    disk_info_item_array = line.strip().split()
                    if dev_name == disk_info_item_array[0]:
                        if len(disk_info_item_array) > 1:
                            property_value = disk_info_item_array[1]

        DiskUtil.sles_cache[(dev_name, property_name)] = property_value
        return property_value

    def get_azure_symlinks(self):
        azure_udev_links = {}

        if os.path.exists('/dev/disk/azure'):
            wdbackup = os.getcwd()
            os.chdir('/dev/disk/azure')
            for symlink in os.listdir('/dev/disk/azure'):
                azure_udev_links[os.path.basename(symlink)] = os.path.realpath(symlink)
            os.chdir(wdbackup)

        return azure_udev_links

    def get_device_items_sles(self, dev_path):
        if dev_path:
            self.logger.log(msg=("getting blk info for: {0}".format(dev_path)))
        device_items_to_return = []
        device_items = []

        #first get all the device names
        if dev_path is None:
            lsblk_command = 'lsblk -b -nl -o NAME'
        else:
            lsblk_command = 'lsblk -b -nl -o NAME ' + dev_path

        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(lsblk_command, communicator=proc_comm, raise_exception_on_failure=True)

        for line in proc_comm.stdout.splitlines():
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

            device_item.azure_name = ''
            for symlink, target in self.get_azure_symlinks().items():
                if device_item.name in target:
                    device_item.azure_name = symlink

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
            for line in proc_comm.stdout.splitlines():
                if line:
                    device_item = DeviceItem()

                    for disk_info_property in line.split():
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

                    device_item.azure_name = ''
                    for symlink, target in self.get_azure_symlinks().items():
                        if device_item.name in target:
                            device_item.azure_name = symlink

                    device_items.append(device_item)

            return device_items

    def get_lvm_items(self):
        lvs_command = 'lvs --noheadings --nameprefixes --unquoted -o lv_name,vg_name,lv_kernel_major,lv_kernel_minor'
        proc_comm = ProcessCommunicator()

        if self.command_executor.Execute(lvs_command, communicator=proc_comm):
            return []

        lvm_items = []

        for line in proc_comm.stdout.splitlines():
            if not line:
                continue

            lvm_item = LvmItem()

            for pair in line.strip().split():
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

        lvm_items = filter(lambda item: item.vg_name == "rootvg", self.get_lvm_items())

        current_lv_names = set([item.lv_name for item in lvm_items])
        expected_lv_names = set(['homelv', 'optlv', 'rootlv', 'swaplv', 'tmplv', 'usrlv', 'varlv'])

        if expected_lv_names == current_lv_names:
            DiskUtil.os_disk_lvm = True
        else:
            DiskUtil.os_disk_lvm = False

        return DiskUtil.os_disk_lvm

    def should_skip_for_inplace_encryption(self, device_item, encrypt_volume_type):
        """
        TYPE="raid0"
        TYPE="part"
        TYPE="crypt"

        first check whether there's one file system on it.
        if the type is disk, then to check whether it have child-items, say the part, lvm or crypt luks.
        if the answer is yes, then skip it.
        """

        if encrypt_volume_type.lower() == 'data':
            self.logger.log(msg="enabling encryption for data volumes", level=CommonVariables.WarningLevel)
            if device_item.device_id.startswith('00000000-0000'):
                self.logger.log(msg="skipping root disk", level=CommonVariables.WarningLevel)
                return True
            if device_item.device_id.startswith('00000000-0001'):
                self.logger.log(msg="skipping resource disk", level=CommonVariables.WarningLevel)
                return True

        if device_item.file_system is None or device_item.file_system == "":
            self.logger.log(msg=("there's no file system on this device: {0}, so skip it.").format(device_item))
            return True
        else:
            if device_item.size < CommonVariables.min_filesystem_size_support:
                self.logger.log(msg="the device size is too small," + str(device_item.size) + " so skip it.", level=CommonVariables.WarningLevel)
                return True

            supported_device_type = ["disk","part","raid0","raid1","raid5","raid10","lvm"]
            if device_item.type not in supported_device_type:
                self.logger.log(msg="the device type: " + str(device_item.type) + " is not supported yet, so skip it.", level=CommonVariables.WarningLevel)
                return True

            if device_item.uuid is None or device_item.uuid == "":
                self.logger.log(msg="the device do not have the related uuid, so skip it.", level=CommonVariables.WarningLevel)
                return True
            sub_items = self.get_device_items("/dev/" + device_item.name)
            if len(sub_items) > 1:
                self.logger.log(msg=("there's sub items for the device:{0} , so skip it.".format(device_item.name)), level=CommonVariables.WarningLevel)
                return True

            azure_blk_items = self.get_azure_devices()
            if device_item.type == "crypt":
                self.logger.log(msg=("device_item.type is:{0}, so skip it.".format(device_item.type)), level=CommonVariables.WarningLevel)
                return True

            if device_item.mount_point == "/":
                self.logger.log(msg=("the mountpoint is root:{0}, so skip it.".format(device_item)), level=CommonVariables.WarningLevel)
                return True
            for azure_blk_item in azure_blk_items:
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
        for root, dirs, files in os.walk(os.path.join(self.vmbus_sys_path , vmbus)):
            if root.endswith("/block"):
                device = dirs[0]
            else : #older distros
                for d in dirs:
                    if ':' in d and "block" == d.split(':')[0]:
                        device = d.split(':')[1]
                        break
        return device
