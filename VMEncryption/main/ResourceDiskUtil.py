#!/usr/bin/env python
#
# *********************************************************
# Copyright (c) Microsoft. All rights reserved.
#
# Apache 2.0 License
#
# You may obtain a copy of the License at
# http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# *********************************************************

""" Functionality to encrypt the Azure resource disk"""

import uuid
import time
import json
import types
import os

from CommandExecutor import CommandExecutor
from Common import CommonVariables
from DiskUtil import DiskUtil

class ResourceDiskUtil(object):
    """ Resource Disk Encryption Utilities """

    RD_KEY_FILE = CommonVariables.PassphraseFileNameKey
    RD_MOUNT_POINT = '/mnt/resource'
    RD_BASE_DEV_PATH = '/dev/disk/azure/resource'
    RD_DEV_PATH = '/dev/disk/azure/resource-part1'
    DM_PREFIX = '/dev/mapper/'
    # todo: consolidate this and other key file path references
    # (BekUtil.py, ExtensionParameter.py, and dracut patches)
    RD_KEY_FILE = '/mnt/azure_bek_disk/LinuxPassPhraseFileName'
    RD_KEY_FILE_MOUNT_POINT = '/mnt/azure_bek_disk'
    RD_KEY_VOLUME_LABEL = 'BEK VOLUME'

    def __init__(self, hutil, logger, distro_patcher):
        self.hutil = hutil
        self.logger = logger
        self.executor = CommandExecutor(self.logger)
        self.disk_util = DiskUtil(hutil=self.hutil, patching=distro_patcher, logger=self.logger, encryption_environment=None)
        self.mapper_name = str(uuid.uuid4())
        self.mapper_path = self.DM_PREFIX + self.mapper_name

    def is_encrypt_format_all(self):
        """ return true if current encryption operation is EncryptFormatAll """
        try:                
            public_settings_str = self.hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('publicSettings')
            if isinstance(public_settings_str, basestring):
                public_settings = json.loads(public_settings_str)
            else:
                public_settings = public_settings_str
            encryption_operation = public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)
            if encryption_operation in [CommonVariables.EnableEncryptionFormatAll]:
                return True
        except:
            self.logger.log("unable to identify current encryption operation")
        return False

    def is_luks_device(self):
        """ checks if the device is set up with a luks header """
        if not self.resource_disk_partition_exists():
            return False
        cmd = 'cryptsetup isLuks ' + self.RD_DEV_PATH
        return (int)(self.executor.Execute(cmd, suppress_logging=True)) == 0

    def is_luks_device_opened(self):
        """ check for presence of luks uuid to see if device was already opened """
        # suppress logging to avoid log clutter if the device is not open yet
        if not self.resource_disk_partition_exists():
            return False
        cmd = 'test -b /dev/disk/by-uuid/$(cryptsetup luksUUID ' + self.RD_DEV_PATH + ')'
        return (int)(self.executor.ExecuteInBash(cmd, suppress_logging=True)) == 0

    def is_valid_key(self):
        """ test if current key can be used to open current partition """
        # suppress logging to avoid log clutter if the key doesn't match
        if not self.resource_disk_partition_exists():
            return False
        cmd = 'cryptsetup luksOpen ' + self.RD_DEV_PATH + ' --test-passphrase --key-file ' + self.RD_KEY_FILE
        return (int)(self.executor.Execute(cmd, suppress_logging=True)) == 0

    def resource_disk_exists(self):
        """ true if the udev name for resourced disk exists """
        cmd = 'test -b ' + self.RD_BASE_DEV_PATH
        return (int)(self.executor.Execute(cmd, suppress_logging=True)) == 0

    def resource_disk_partition_exists(self):
        """ true if udev name for resource disk partition exists """
        cmd = 'test -b ' + self.RD_DEV_PATH
        return (int)(self.executor.Execute(cmd, suppress_logging=True)) == 0

    def format_luks(self):
        """ set up resource disk crypt device layer using disk util """
        if not self.resource_disk_partition_exists():
            self.logger.log('LUKS format operation requested, but resource disk partition does not exist')
            return False
        return (int)(self.disk_util.luks_format(passphrase_file=self.RD_KEY_FILE, dev_path=self.RD_DEV_PATH, header_file=None)) == 0

    def encrypt(self):
        """ use disk util with the appropriate device mapper """
        self.mount_key_volume()
        return (int)(self.disk_util.encrypt_disk(dev_path=self.RD_DEV_PATH, passphrase_file=self.RD_KEY_FILE, mapper_name=self.mapper_name, header_file=None)) == 0

    def make(self):
        """ make a default file system on top of the crypt layer """
        make_result = self.disk_util.format_disk(dev_path=self.mapper_path, file_system=CommonVariables.default_file_system)
        if make_result != CommonVariables.process_success:
            self.logger.log(msg="Failed to make file system on ephemeral disk", level=CommonVariables.ErrorLevel)
            return False
        # todo - drop DATALOSS_WARNING_README.txt file to disk
        return True

    def mount_key_volume(self):
        """ attempt to mount the key volume and verify existence of key file"""
        if not os.path.exists(self.RD_KEY_FILE):
            self.disk_util.make_sure_path_exists(self.RD_KEY_FILE_MOUNT_POINT)
            key_volume_device_name = os.popen('blkid -L "' + self.RD_KEY_VOLUME_LABEL + '"').read().strip()
            self.disk_util.mount_filesystem(key_volume_device_name, self.RD_KEY_FILE_MOUNT_POINT)
        return os.path.exists(self.RD_KEY_FILE)
        
    def mount(self):
        """ mount the file system previously made on top of the crypt layer """
        #ensure that resource disk mount point directory has been created
        cmd = 'mkdir -p ' + self.RD_MOUNT_POINT
        if self.executor.Execute(cmd, suppress_logging=True) != CommonVariables.process_success:
            self.logger.log(msg='Failed to precreate mount point directory: ' + cmd, level=CommonVariables.ErrorLevel)
            return False

        # mount to mount point directory
        mount_result = self.disk_util.mount_filesystem(dev_path=self.mapper_path, mount_point=self.RD_MOUNT_POINT, file_system=CommonVariables.default_file_system)
        if mount_result != CommonVariables.process_success:
            self.logger.log(msg="Failed to mount file system on resource disk", level=CommonVariables.ErrorLevel)
            return False
        return True

    def configure_waagent(self):
        """ turn off waagent.conf resource disk management  """ 
        # set ResourceDisk.MountPoint to standard /mnt mount point
        cmd = "sed -i.bak 's|ResourceDisk.MountPoint=.*|ResourceDisk.MountPoint=/mnt|' /etc/waagent.conf"

        # set ResourceDiskFormat=n to ensure waagent does not attempt a simultaneous format
        cmd = "sed -i.bak 's|ResourceDisk.Format=y|ResourceDisk.Format=n|' /etc/waagent.conf"
        if self.executor.ExecuteInBash(cmd) != CommonVariables.process_success:
            self.logger.log(msg="Failed to set ResourceDiskFormat in /etc/waagent.conf", level=CommonVariables.WarningLevel)
            return False
        # todo: restart waagent if necessary to ensure changes are picked up?
        return True

    def configure_fstab(self):
        """ remove resource disk from /etc/fstab if present """
        cmd = "sed -i.bak '/azure_resource-part1/d' /etc/fstab"        
        if self.executor.ExecuteInBash(cmd) != CommonVariables.process_success:
            self.logger.log(msg="Failed to configure resource disk entry of /etc/fstab", level=CommonVariables.WarningLevel)
            return False        
        return True

    def unmount_resource_disk(self):
        """ return true if mount point is mounted regardless of crypt status """
        # after service healing multiple unmounts of key file mount point may be required
        self.disk_util.umount(self.RD_KEY_FILE_MOUNT_POINT)
        self.disk_util.umount(self.RD_KEY_FILE_MOUNT_POINT)
        self.disk_util.umount(self.RD_MOUNT_POINT)
        self.disk_util.umount('/mnt')

    def is_crypt_mounted(self):
        """ return true if mount point is already on a crypt layer """
        mount_items = self.disk_util.get_mount_items()
        for mount_item in mount_items:
            if mount_item["dest"] == self.RD_MOUNT_POINT and mount_item["src"].startswith(self.DM_PREFIX):
                return True
        return False

    def get_rd_device_mapper(self):
        """ retrieve current device mapper path backing the encrypted resource disk mount point """
        device_items = self.disk_util.get_device_items(self.RD_DEV_PATH)
        for device_item in device_items:
            if device_item.type.lower() == 'crypt':
                self.logger.log('Found device mapper: ' + device_item.name.lower(), level='Info')
                return device_item.name.lower()
        return None

    def remove_device_mapper(self):
        """ use dmsetup to remove the resource disk device mapper if it exists """
        dm_name = self.get_rd_device_mapper()
        if dm_name:
            cmd = 'dmsetup remove ' + self.DM_PREFIX + dm_name
            if self.executor.Execute(cmd) == 0:
                return True
            else:
                self.logger.log('failed to remove ' + dm_name)
        else:
            self.logger.log('no resource disk device mapper found')
        return False

    def prepare_partition(self):
        """ create partition on resource disk if missing """
        if self.resource_disk_partition_exists():
            return True
        self.logger.log("resource disk partition does not exist", level='Info')
        cmd = 'parted ' + self.RD_BASE_DEV_PATH + ' mkpart primary ext4 0% 100%'
        if self.executor.ExecuteInBash(cmd) == CommonVariables.process_success:
            # wait for the corresponding udev name to become available
            for i in range(0, 10):
                time.sleep(i)
                if self.resource_disk_partition_exists():
                    return True
        self.logger.log('unable to make resource disk partition')
        return False


    def clear_luks_header(self):
        """ clear luks header by overwriting with 10MB of entropy """
        if not self.resource_disk_partition_exists():
            self.logger.log("resource partition does not exist, no luks header to clear")
            return True
        cmd = 'dd if=/dev/urandom of=' + self.RD_DEV_PATH + ' bs=512 count=20480'
        return self.executor.Execute(cmd) == CommonVariables.process_success
            
    def try_remount(self):
        """ mount encrypted resource disk if not already mounted"""
        if self.is_crypt_mounted():
            self.logger.log("resource disk already encrypted and mounted", level='Info')
            return True

        if self.resource_disk_exists() and self.resource_disk_partition_exists() and self.is_luks_device() and self.is_valid_key():
            # store the currently associated path and name
            current_mapper_name = self.get_rd_device_mapper()
            if current_mapper_name:
                self.mapper_name = current_mapper_name
                self.mapper_path = self.DM_PREFIX + self.mapper_name
                if not self.is_luks_device_opened:
                    # attempt to open
                    self.disk_util.luks_open(passphrase_file=self.RD_KEY_FILE, dev_path=self.RD_DEV_PATH, mapper_name=self.mapper_name, header_file=None, uses_cleartext_key=False)
                    if not self.is_luks_device_opened:
                        return False
                # attempt mount
                return self.mount()

        # conditions required to re-mount were not met
        return False

    def prepare(self):
        """ prepare a non-encrypted resource disk to be encrypted """
        self.configure_waagent()
        self.configure_fstab()
        if self.resource_disk_partition_exists():
            self.disk_util.swapoff()
            self.unmount_resource_disk()
            self.remove_device_mapper()
            self.clear_luks_header()
        self.prepare_partition()
        return True

    def automount(self):
        """ encrypt resource disk """
        # try to remount if the disk was previously encrypted and is still valid
        if self.try_remount():
            return True

        # unencrypted or unusable
        if self.is_encrypt_format_all():
            return self.prepare() and self.encrypt() and self.make() and self.mount()
        else:
            self.logger.log('EncryptionFormatAll not in use, resource disk will not be automatically formatted and encrypted.')
             