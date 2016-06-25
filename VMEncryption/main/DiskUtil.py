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
import os
import os.path
import re
import shlex
import sys
from subprocess import *
import shutil
import uuid
import glob
from TransactionalCopyTask import TransactionalCopyTask
from Common import *

class DiskUtil(object):
    def __init__(self, hutil, patching, logger, encryption_environment):
        self.encryption_environment = encryption_environment
        self.hutil = hutil
        self.patching = patching
        self.logger = logger
        self.ide_class_id = "{32412632-86cb-44a2-9b5c-50d1417354f5}"
        self.vmbus_sys_path = '/sys/bus/vmbus/devices'

    def copy(self, ongoing_item_config):
        copy_task = TransactionalCopyTask(logger = self.logger, disk_util = self, ongoing_item_config = ongoing_item_config, patching=self.patching, encryption_environment = self.encryption_environment)
        try:
            mem_fs_result = copy_task.prepare_mem_fs()
            if(mem_fs_result != CommonVariables.process_success):
                return CommonVariables.tmpfs_error
            else:
                returnCode = copy_task.begin_copy()
                return returnCode
        finally:
            copy_task.clear_mem_fs()

    def format_disk(self, dev_path, file_system):
        mkfs_command = ""
        if(file_system == "ext4"):
            mkfs_command = "mkfs.ext4"
        elif(file_system == "ext3"):
            mkfs_command = "mkfs.ext3"
        elif(file_system == "xfs"):
            mkfs_command = "mkfs.xfs"
        elif(file_system == "btrfs"):
            mkfs_command = "mkfs.btrfs"
        mkfs_cmd = "{0} {1}".format(mkfs_command, dev_path)
        self.logger.log("command to execute:{0}".format(mkfs_cmd))
        mkfs_cmd_args = shlex.split(mkfs_cmd)
        proc = Popen(mkfs_cmd_args)
        returnCode = proc.wait()
        return returnCode

    def make_sure_path_exists(self,path):
        mkdir_cmd = self.patching.mkdir_path + ' -p ' + path
        self.logger.log("make sure path exists, execute:{0}".format(mkdir_cmd))
        mkdir_cmd_args = shlex.split(mkdir_cmd)
        proc = Popen(mkdir_cmd_args)
        returnCode = proc.wait()
        return returnCode

    def get_crypt_items(self):
        crypt_items = []
        if not os.path.exists(self.encryption_environment.azure_crypt_mount_config_path):
            self.logger.log("{0} not exists".format(self.encryption_environment.azure_crypt_mount_config_path))
            return None
        else:
            with open(self.encryption_environment.azure_crypt_mount_config_path,'r') as f:
                existing_content = f.read()
                crypt_mount_items = existing_content.splitlines()
                for i in range(0,len(crypt_mount_items)):
                    crypt_mount_item = crypt_mount_items[i]
                    if(crypt_mount_item.strip() != ""):
                        crypt_mount_item_properties = crypt_mount_item.strip().split()
                        crypt_item = CryptItem()
                        crypt_item.mapper_name = crypt_mount_item_properties[0]
                        crypt_item.dev_path = crypt_mount_item_properties[1]
                        header_file_path = None
                        if(crypt_mount_item_properties[2] != "None"):
                            header_file_path = crypt_mount_item_properties[2]
                        crypt_item.luks_header_path = header_file_path
                        crypt_item.mount_point = crypt_mount_item_properties[3]
                        crypt_item.file_system = crypt_mount_item_properties[4]
                        crypt_item.uses_cleartext_key = True if crypt_mount_item_properties[5] == "True" else False
                        crypt_items.append(crypt_item)
        return crypt_items

    def add_crypt_item(self,crypt_item):
        """
        TODO we should judge that the second time.
        format is like this:
        <target name> <source device> <key file> <options>
        """
        try:
            mount_content_item = (crypt_item.mapper_name + " " +
                                  crypt_item.dev_path + " " +
                                  crypt_item.luks_header_path + " " +
                                  crypt_item.mount_point + " " +
                                  crypt_item.file_system + " " +
                                  str(crypt_item.uses_cleartext_key))

            if os.path.exists(self.encryption_environment.azure_crypt_mount_config_path):
                with open(self.encryption_environment.azure_crypt_mount_config_path,'r') as f:
                    existing_content = f.read()
                    if(existing_content is not None and existing_content.strip() != ""):
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
        self.remove_crypt_item(crypt_item)
        self.add_crypt_item(crypt_item)

    def create_luks_header(self,mapper_name):
        luks_header_file_path = self.encryption_environment.luks_header_base_path + mapper_name
        if(os.path.exists(luks_header_file_path)):
            return luks_header_file_path
        else:
            commandToExecute = self.patching.bash_path + ' -c "' + self.patching.dd_path + ' if=/dev/zero bs=33554432 count=1 > ' + luks_header_file_path + '"'
            proc = Popen(commandToExecute, shell=True)
            returnCode = proc.wait()
            if(returnCode == CommonVariables.process_success):
                return luks_header_file_path
            else:
                self.logger.log(msg=("make luks header failed and return code is:{0}".format(returnCode)), level=CommonVariables.ErrorLevel)
                return None

    def create_cleartext_key(self, mapper_name):
        cleartext_key_file_path = self.encryption_environment.cleartext_key_base_path + mapper_name
        if(os.path.exists(cleartext_key_file_path)):
            return cleartext_key_file_path
        else:
            commandToExecute = self.patching.bash_path + ' -c "' + self.patching.dd_path + ' if=/dev/urandom bs=128 count=1 > ' + cleartext_key_file_path + '"'
            proc = Popen(commandToExecute, shell=True)
            returnCode = proc.wait()
            if(returnCode == CommonVariables.process_success):
                return cleartext_key_file_path
            else:
                self.logger.log(msg=("dd failed with return code: {0}".format(returnCode)), level=CommonVariables.ErrorLevel)
                return None

    def encrypt_disk(self, dev_path, passphrase_file, mapper_name, header_file):
        returnCode = self.luks_format(passphrase_file=passphrase_file, dev_path=dev_path, header_file=header_file)
        if(returnCode != CommonVariables.process_success):
            self.logger.log(msg=('cryptsetup luksFormat failed, returnCode is:{0}'.format(returnCode)), level=CommonVariables.ErrorLevel)
            return returnCode
        else:
            returnCode = self.luks_open(passphrase_file=passphrase_file,
                                        dev_path=dev_path,
                                        mapper_name=mapper_name,
                                        header_file=header_file,
                                        uses_cleartext_key=False)
            if(returnCode != CommonVariables.process_success):
                self.logger.log(msg=('cryptsetup luksOpen failed, returnCode is:{0}'.format(returnCode)), level=CommonVariables.ErrorLevel)
            return returnCode

    def check_fs(self, dev_path):
        self.logger.log("checking fs:" + str(dev_path))
        check_fs_cmd = self.patching.e2fsck_path + " -f -y " + dev_path
        self.logger.log("check fs command is:{0}".format(check_fs_cmd))
        check_fs_cmd_args = shlex.split(check_fs_cmd)
        check_fs_cmd_p = Popen(check_fs_cmd_args)
        returnCode = check_fs_cmd_p.wait()
        return returnCode

    def expand_fs(self, dev_path):
        expandfs_cmd = self.patching.resize2fs_path + " " + str(dev_path)
        self.logger.log("expand_fs command is:{0}".format(expandfs_cmd))
        expandfs_cmd_args = shlex.split(expandfs_cmd)
        expandfs_p = Popen(expandfs_cmd_args)
        returnCode = expandfs_p.wait()
        return returnCode

    def shrink_fs(self,dev_path, size_shrink_to):
        """
        size_shrink_to is in sector (512 byte)
        """
        shrinkfs_cmd = self.patching.resize2fs_path + ' ' + str(dev_path) + ' ' + str(size_shrink_to) + 's'
        self.logger.log("shrink_fs command is {0}".format(shrinkfs_cmd))
        shrinkfs_cmd_args = shlex.split(shrinkfs_cmd)
        shrinkfs_p = Popen(shrinkfs_cmd_args)
        returnCode = shrinkfs_p.wait()
        return returnCode

    def check_shrink_fs(self,dev_path, size_shrink_to):
        returnCode = self.check_fs(dev_path)
        if(returnCode == CommonVariables.process_success):
            returnCode = self.shrink_fs(dev_path = dev_path, size_shrink_to = size_shrink_to)
            return returnCode
        else:
            return returnCode

    def luks_format(self, passphrase_file, dev_path, header_file):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("dev path to cryptsetup luksFormat {0}".format(dev_path))
        #walkaround for sles sp3
        if(self.patching.distro_info[0].lower() == 'suse' and self.patching.distro_info[1] == '11'):
            passphrase_cmd = self.patching.cat_path + ' ' + passphrase_file
            passphrase_cmd_args = shlex.split(passphrase_cmd)
            self.logger.log("passphrase_cmd is:{0}".format(passphrase_cmd))
            passphrase_p = Popen(passphrase_cmd_args,stdout=subprocess.PIPE)

            cryptsetup_cmd = "{0} luksFormat {1} -q".format(self.patching.cryptsetup_path , dev_path)
            self.logger.log("cryptsetup_cmd is:{0}".format(cryptsetup_cmd))
            cryptsetup_cmd_args = shlex.split(cryptsetup_cmd)
            cryptsetup_p = Popen(cryptsetup_cmd_args,stdin=passphrase_p.stdout)
            returnCode = cryptsetup_p.wait()
            return returnCode
        else:
            if(header_file is not None):
                cryptsetup_cmd = "{0} luksFormat {1} --header {2} -d {3} -q".format(self.patching.cryptsetup_path , dev_path , header_file , passphrase_file)
            else:
                cryptsetup_cmd = "{0} luksFormat {1} -d {2} -q".format(self.patching.cryptsetup_path ,dev_path , passphrase_file)
            self.logger.log("cryptsetup_cmd is:" + cryptsetup_cmd)
            cryptsetup_cmd_args = shlex.split(cryptsetup_cmd)
            cryptsetup_p = Popen(cryptsetup_cmd_args)
            returnCode = cryptsetup_p.wait()
            return returnCode
        
    def luks_add_cleartext_key(self, passphrase_file, dev_path, mapper_name, header_file):
        """
        return the return code of the process for error handling.
        """
        cleartext_key_file_path = self.encryption_environment.cleartext_key_base_path + mapper_name

        self.hutil.log("cleartext key path: " + (cleartext_key_file_path))

        if not os.path.exists(cleartext_key_file_path):
            self.hutil.error("cleartext key does not exist")
            return None

        if(header_file is not None or header_file == ""):
            cryptsetup_cmd = "{0} luksAddKey {1} {2} -d {3} -q".format(self.patching.cryptsetup_path, header_file, cleartext_key_file_path, passphrase_file)
        else:
            cryptsetup_cmd = "{0} luksAddKey {1} {2} -d {3} -q".format(self.patching.cryptsetup_path, dev_path, cleartext_key_file_path, passphrase_file)

        self.logger.log("cryptsetup_cmd is: " + cryptsetup_cmd)
        cryptsetup_cmd_args = shlex.split(cryptsetup_cmd)
        cryptsetup_p = Popen(cryptsetup_cmd_args)
        returnCode = cryptsetup_p.wait()
        return returnCode

    def luks_open(self, passphrase_file, dev_path, mapper_name, header_file, uses_cleartext_key):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("dev mapper name to cryptsetup luksOpen " + (mapper_name))

        if uses_cleartext_key:
            passphrase_file = self.encryption_environment.cleartext_key_base_path + mapper_name

        self.hutil.log("keyfile: " + (passphrase_file))

        if(header_file is not None or header_file == ""):
            cryptsetup_cmd = "{0} luksOpen {1} {2} --header {3} -d {4} -q".format(self.patching.cryptsetup_path , dev_path ,mapper_name, header_file ,passphrase_file)
        else:
            cryptsetup_cmd = "{0} luksOpen {1} {2} -d {3} -q".format(self.patching.cryptsetup_path , dev_path , mapper_name , passphrase_file)
        self.logger.log("cryptsetup_cmd is:" + cryptsetup_cmd)
        cryptsetup_cmd_args = shlex.split(cryptsetup_cmd)
        cryptsetup_p = Popen(cryptsetup_cmd_args)
        returnCode = cryptsetup_p.wait()
        return returnCode

    def luks_close(self, mapper_name):
        """
        returns the exit code for cryptsetup process.
        """
        self.hutil.log("dev mapper name to cryptsetup luksOpen " + (mapper_name))
        cryptsetup_cmd = "{0} luksClose {1} -q".format(self.patching.cryptsetup_path, mapper_name)
        self.logger.log("cryptsetup_cmd is:" + cryptsetup_cmd)
        cryptsetup_cmd_args = shlex.split(cryptsetup_cmd)
        cryptsetup_p = Popen(cryptsetup_cmd_args)
        returnCode = cryptsetup_p.wait()
        return returnCode

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

    def mount_filesystem(self,dev_path,mount_point,file_system=None):
        """
        mount the file system.
        """
        returnCode = -1
        if file_system is None:
            mount_cmd = self.patching.mount_path + ' ' + dev_path + ' ' + mount_point
            self.logger.log("mount file system, execute:{0}".format(mount_cmd))
            mount_cmd_args = shlex.split(mount_cmd)
            proc = Popen(mount_cmd_args)
            returnCode = proc.wait()
        else: 
            mount_cmd = self.patching.mount_path + ' ' + dev_path + ' ' + mount_point + ' -t ' + file_system
            self.logger.log("mount file system, execute:{0}".format(mount_cmd))
            mount_cmd_args = shlex.split(mount_cmd)
            proc = Popen(mount_cmd_args)
            returnCode = proc.wait()
        return returnCode

    def mount_crypt_item(self, crypt_item, passphrase):
        self.logger.log("trying to mount the crypt item:" + str(crypt_item))
        mount_filesystem_result = self.mount_filesystem(os.path.join('/dev/mapper',crypt_item.mapper_name),crypt_item.mount_point,crypt_item.file_system)
        self.logger.log("mount file system result:{0}".format(mount_filesystem_result))

    def umount(self, path):
        umount_cmd = self.patching.umount_path + ' ' + path
        self.logger.log("umount, execute:{0}".format(umount_cmd))
        umount_cmd_args = shlex.split(umount_cmd)
        proc = Popen(umount_cmd_args)
        returnCode = proc.wait()
        return returnCode

    def umount_all_crypt_items(self):
        for crypt_item in self.get_crypt_items():
            self.logger.log("Unmounting {0}".format(crypt_item.mount_point))
            self.umount(crypt_item.mount_point)

    def mount_all(self):
        mount_all_cmd = self.patching.mount_path + ' -a'
        self.logger.log("command to execute:{0}".format(mount_all_cmd))
        mount_all_cmd_args = shlex.split(mount_all_cmd)
        proc = Popen(mount_all_cmd_args)
        returnCode = proc.wait()
        return returnCode

    def query_dev_sdx_path_by_scsi_id(self,scsi_number): 
        p = Popen([self.patching.lsscsi_path, scsi_number], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        identity, err = p.communicate()
        # identity sample: [5:0:0:0] disk Msft Virtual Disk 1.0 /dev/sdc
        self.logger.log("lsscsi output is: {0}\n".format(identity))
        vals = identity.split()
        if(vals is None or len(vals) == 0):
            return None
        sdx_path = vals[len(vals) - 1]
        return sdx_path

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
        p = Popen([self.patching.blkid_path,sdx_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        identity,err = p.communicate()
        identity = identity.lower()
        self.logger.log("blkid output is: \n" + identity)
        uuid_pattern = 'uuid="'
        index_of_uuid = identity.find(uuid_pattern)
        identity = identity[index_of_uuid + len(uuid_pattern):]
        index_of_quote = identity.find('"')
        uuid = identity[0:index_of_quote]
        if(uuid.strip() == ""):
            #TODO this is strange?  BUGBUG
            return sdx_path
        return os.path.join("/dev/disk/by-uuid/",uuid)

    def query_dev_uuid_path_by_scsi_number(self,scsi_number):
        # find the scsi using the filter
        # TODO figure out why the disk formated using fdisk do not have uuid
        sdx_path = self.query_dev_sdx_path_by_scsi_id(scsi_number)
        return self.query_dev_uuid_path_by_sdx_path(sdx_path)

    def get_device_items_property(self, dev_name, property_name):
        self.logger.log("getting property of device {0}".format(dev_name))

        device_path = None
        if os.path.exists("/dev/" + dev_name):
            device_path = "/dev/" + dev_name
        elif os.path.exists("/dev/mapper/" + dev_name):
            device_path = "/dev/mapper/" + dev_name

        if property_name == "SIZE":
            get_property_cmd = self.patching.blockdev_path + " --getsize64 " + device_path
            get_property_cmd_args = shlex.split(get_property_cmd)
            get_property_cmd_p = Popen(get_property_cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output,err = get_property_cmd_p.communicate()
            return output.strip()
        else:
            get_property_cmd = self.patching.lsblk_path + " " + device_path + " -b -nl -o NAME," + property_name
            get_property_cmd_args = shlex.split(get_property_cmd)
            get_property_cmd_p = Popen(get_property_cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output,err = get_property_cmd_p.communicate()
            lines = output.splitlines()
            for i in range(0,len(lines)):
                item_value_str = lines[i].strip()
                if(item_value_str != ""):
                    disk_info_item_array = item_value_str.split()
                    if(dev_name == disk_info_item_array[0]):
                        if(len(disk_info_item_array) > 1):
                            return disk_info_item_array[1]
        return None

    def get_device_items_sles(self, dev_path):
        self.logger.log(msg=("getting the blk info from:{0}".format(dev_path)))
        device_items_to_return = []
        device_items = []
        #first get all the device names
        if(dev_path is None):
            get_device_cmd = self.patching.lsblk_path + " -b -nl -o NAME"
        else:
            get_device_cmd = "{0} -b -nl -o NAME {1}".format(self.patching.lsblk_path , dev_path)
        get_device_cmd_args = shlex.split(get_device_cmd)
        p = Popen(get_device_cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out_lsblk_output, err = p.communicate()
        lines = out_lsblk_output.splitlines()
        for i in range(0,len(lines)):
            item_value_str = lines[i].strip()
            if(item_value_str != ""):
                disk_info_item_array = item_value_str.split()
                device_item = DeviceItem()
                device_item.name = disk_info_item_array[0]
                device_items.append(device_item)

        for i in range(0, len(device_items)):
            device_item = device_items[i]
            device_item.file_system = self.get_device_items_property(dev_name=device_item.name, property_name='FSTYPE')
            device_item.mount_point = self.get_device_items_property(dev_name=device_item.name, property_name='MOUNTPOINT')
            device_item.label = self.get_device_items_property(dev_name=device_item.name, property_name='LABEL')
            device_item.uuid = self.get_device_items_property(dev_name=device_item.name, property_name='UUID')
            # get the type of device
            model_file_path = '/sys/block/' + device_item.name + '/device/model'
            if(os.path.exists(model_file_path)):
                with open(model_file_path,'r') as f:
                    device_item.model = f.read().strip()
            else:
                self.logger.log(msg=("no model file found for device {0}".format(device_item.name)))
            if(device_item.model == 'Virtual Disk'):
                self.logger.log(msg="model is virtual disk")
                device_item.type = 'disk'
            else:
                partition_files = glob.glob('/sys/block/*/' + device_item.name + '/partition')
                self.logger.log(msg="partition files exists")
                if(partition_files is not None and len(partition_files) > 0):
                    device_item.type = 'part'
            size_string = self.get_device_items_property(dev_name=device_item.name,property_name='SIZE')
            if size_string is not None and size_string != "":
                device_item.size = int(size_string)
            if(device_item.size is not None):
                device_items_to_return.append(device_item)
            else:
                self.logger.log(msg=("skip the device {0} because we could not get size of it.".format(device_item.name)))
        return device_items_to_return

    def get_device_items(self, dev_path):
        if(self.patching.distro_info[0].lower() == 'suse' and self.patching.distro_info[1] == '11'):
            return self.get_device_items_sles(dev_path)
        else:
            self.logger.log(msg=("getting the blk info from " + str(dev_path)))
            device_items = []
            if(dev_path is None):
                p = Popen([self.patching.lsblk_path, '-b', '-n','-P','-o','NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                p = Popen([self.patching.lsblk_path, '-b', '-n','-P','-o','NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE',dev_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out_lsblk_output, err = p.communicate()
            out_lsblk_output = str(out_lsblk_output)
            error_msg = str(err)
            if(error_msg is not None and error_msg.strip() != ""):
                self.logger.log(msg=str(err),level=CommonVariables.ErrorLevel)
            lines = out_lsblk_output.splitlines()
            for i in range(0,len(lines)):
                item_value_str = lines[i].strip()
                if(item_value_str != ""):
                    disk_info_item_array = item_value_str.split()
                    device_item = DeviceItem()
                    disk_info_item_array_length = len(disk_info_item_array)
                    for j in range(0, disk_info_item_array_length):
                        disk_info_property = disk_info_item_array[j]
                        property_item_pair = disk_info_property.split('=')
                        if(property_item_pair[0] == 'SIZE'):
                            device_item.size = int(property_item_pair[1].strip('"'))

                        if(property_item_pair[0] == 'NAME'):
                            device_item.name = property_item_pair[1].strip('"')

                        if(property_item_pair[0] == 'TYPE'):
                            device_item.type = property_item_pair[1].strip('"')

                        if(property_item_pair[0] == 'FSTYPE'):
                            device_item.file_system = property_item_pair[1].strip('"')
                        
                        if(property_item_pair[0] == 'MOUNTPOINT'):
                            device_item.mount_point = property_item_pair[1].strip('"')

                        if(property_item_pair[0] == 'LABEL'):
                            device_item.label = property_item_pair[1].strip('"')

                        if(property_item_pair[0] == 'UUID'):
                            device_item.uuid = property_item_pair[1].strip('"')

                        if(property_item_pair[0] == 'MODEL'):
                            device_item.model = property_item_pair[1].strip('"')

                    device_items.append(device_item)
            return device_items
    
    def should_skip_for_inplace_encryption(self, device_item):
        """
        TYPE="raid0"
        TYPE="part"
        TYPE="crypt"

        first check whether there's one file system on it.
        if the type is disk, then to check whether it have child-items, say the part, lvm or crypt luks.
        if the answer is yes, then skip it.
        """
        if(device_item.file_system is None or device_item.file_system == ""):
            self.logger.log(msg=("there's no file system on this device: {0}, so skip it.").format(device_item))
            return True
        else:
            if(device_item.size < CommonVariables.min_filesystem_size_support):
                self.logger.log(msg="the device size is too small," + str(device_item.size) + " so skip it.",level=CommonVariables.WarningLevel)
                return True

            supported_device_type = ["disk","part","raid0","raid1","raid5","raid10","lvm"]
            if(device_item.type not in supported_device_type):
                self.logger.log(msg="the device type: " + str(device_item.type) + " is not supported yet, so skip it.",level=CommonVariables.WarningLevel)
                return True

            if(device_item.uuid is None or device_item.uuid == ""):
                self.logger.log(msg="the device do not have the related uuid, so skip it.",level=CommonVariables.WarningLevel)
                return True
            sub_items = self.get_device_items("/dev/" + device_item.name)
            if(len(sub_items) > 1):
                self.logger.log(msg=("there's sub items for the device:{0} , so skip it.".format(device_item.name)),level=CommonVariables.WarningLevel)
                return True

            azure_blk_items = self.get_azure_devices()
            if(device_item.type == "crypt"):
                self.logger.log(msg=("device_item.type is:{0}, so skip it.".format(device_item.type)),level=CommonVariables.WarningLevel)
                return True

            if(device_item.mount_point == "/"):
                self.logger.log(msg=("the mountpoint is root:{0}, so skip it.".format(device_item)),level=CommonVariables.WarningLevel)
                return True
            for azure_blk_item in azure_blk_items:
                if(azure_blk_item.name == device_item.name):
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
            if(class_id.strip() == self.ide_class_id):
                device_sdx_path = self.find_block_sdx_path(vmbus)
                self.logger.log("found one ide with vmbus: {0} and the sdx path is:".format(vmbus,device_sdx_path))
                ide_devices.append(device_sdx_path)
        return ide_devices

    def find_block_sdx_path(self,vmbus):
        device = None
        for root, dirs, files in os.walk(os.path.join(self.vmbus_sys_path ,vmbus)):
            if root.endswith("/block"):
                device = dirs[0]
            else : #older distros
                for d in dirs:
                    if ':' in d and "block" == d.split(':')[0]:
                        device = d.split(':')[1]
                        break
        return device
