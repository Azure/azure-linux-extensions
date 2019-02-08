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

import time
import os

from CommandExecutor import CommandExecutor
from Common import CommonVariables


class ResourceDiskUtil(object):
    """ Resource Disk Encryption Utilities """

    RD_KEY_FILE = CommonVariables.PassphraseFileNameKey
    RD_MOUNT_POINT = '/mnt/resource'
    RD_BASE_DEV_PATH = os.path.join(CommonVariables.azure_symlinks_dir, 'resource')
    RD_DEV_PATH = os.path.join(CommonVariables.azure_symlinks_dir, 'resource-part1')
    DEV_DM_PREFIX = '/dev/dm-'
    # todo: consolidate this and other key file path references
    # (BekUtil.py, ExtensionParameter.py, and dracut patches)
    RD_KEY_FILE_MOUNT_POINT = '/mnt/azure_bek_disk'
    RD_KEY_VOLUME_LABEL = 'BEK VOLUME'
    RD_MAPPER_NAME = 'resourceencrypt'
    RD_MAPPER_PATH = os.path.join(CommonVariables.dev_mapper_root, RD_MAPPER_NAME)

    def __init__(self, logger, disk_util, passphrase_filename, public_settings):
        self.logger = logger
        self.executor = CommandExecutor(self.logger)
        self.disk_util = disk_util
        self.passphrase_filename = passphrase_filename  # WARNING: This may be null, in which case we mount the resource disk if its unencrypted and do nothing if it is.
        self.public_settings = public_settings

    def is_encrypt_format_all(self):
        """ return true if current encryption operation is EncryptFormatAll """
        encryption_operation = self.public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)
        if encryption_operation in [CommonVariables.EnableEncryptionFormatAll]:
            return True
        self.logger.log("unable to identify current encryption operation")
        return False

    def is_luks_device(self):
        """ checks if the device is set up with a luks header """
        if not self.resource_disk_partition_exists():
            return False
        cmd = 'cryptsetup isLuks ' + self.RD_DEV_PATH
        return (int)(self.executor.Execute(cmd, suppress_logging=True)) == CommonVariables.process_success

    def is_luks_device_opened(self):
        """ check for presence of luks uuid to see if device was already opened """
        # suppress logging to avoid log clutter if the device is not open yet
        if not self.resource_disk_partition_exists():
            return False
        cmd = 'test -b /dev/disk/by-uuid/$(cryptsetup luksUUID ' + self.RD_DEV_PATH + ')'
        return (int)(self.executor.ExecuteInBash(cmd, suppress_logging=True)) == CommonVariables.process_success

    def is_valid_key(self):
        """ test if current key can be used to open current partition """
        # suppress logging to avoid log clutter if the key doesn't match
        if not self.resource_disk_partition_exists():
            return False
        cmd = 'cryptsetup luksOpen ' + self.RD_DEV_PATH + ' --test-passphrase --key-file ' + self.passphrase_filename
        return (int)(self.executor.Execute(cmd, suppress_logging=True)) == CommonVariables.process_success

    def resource_disk_exists(self):
        """ true if the udev name for resource disk exists """
        cmd = 'test -b ' + self.RD_BASE_DEV_PATH
        return (int)(self.executor.Execute(cmd, suppress_logging=True)) == CommonVariables.process_success

    def resource_disk_partition_exists(self):
        """ true if udev name for resource disk partition exists """
        cmd = 'test -b ' + self.RD_DEV_PATH
        return (int)(self.executor.Execute(cmd, suppress_logging=True)) == CommonVariables.process_success

    def format_luks(self):
        """ set up resource disk crypt device layer using disk util """
        if not self.resource_disk_partition_exists():
            self.logger.log('LUKS format operation requested, but resource disk partition does not exist')
            return False
        return (int)(self.disk_util.luks_format(passphrase_file=self.RD_KEY_FILE, dev_path=self.RD_DEV_PATH, header_file=None)) == CommonVariables.process_success

    def encrypt(self):
        """ use disk util with the appropriate device mapper """
        return (int)(self.disk_util.encrypt_disk(dev_path=self.RD_DEV_PATH,
                                                 passphrase_file=self.passphrase_filename,
                                                 mapper_name=self.RD_MAPPER_PATH,
                                                 header_file=None)) == CommonVariables.process_success

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

    def mount(self, dev_path):
        """ mount the file system previously made on top of the crypt layer """
        # ensure that resource disk mount point directory has been created
        cmd = 'mkdir -p ' + self.RD_MOUNT_POINT
        if self.executor.Execute(cmd, suppress_logging=True) != CommonVariables.process_success:
            self.logger.log(msg='Failed to precreate mount point directory: ' + cmd, level=CommonVariables.ErrorLevel)
            return False

        # mount to mount point directory
        mount_result = self.disk_util.mount_filesystem(dev_path=dev_path, mount_point=self.RD_MOUNT_POINT)
        if mount_result != CommonVariables.process_success:
            self.logger.log(msg="Failed to mount file system on resource disk", level=CommonVariables.ErrorLevel)
            return False
        return True

    def configure_waagent(self):
        """ turn off waagent.conf resource disk management  """
        # set ResourceDisk.MountPoint to standard mount point
        cmd = "sed -i.rdbak1 's|ResourceDisk.MountPoint=.*|ResourceDisk.MountPoint=" + self.RD_MOUNT_POINT + "|' /etc/waagent.conf"
        if self.executor.ExecuteInBash(cmd) != CommonVariables.process_success:
            self.logger.log(msg="Failed to change ResourceDisk.MountPoint in /etc/waagent.conf", level=CommonVariables.WarningLevel)
            return False
        # set ResourceDiskFormat=n to ensure waagent does not attempt a simultaneous format
        cmd = "sed -i.rdbak2 's|ResourceDisk.Format=y|ResourceDisk.Format=n|' /etc/waagent.conf"
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
        """ unmount resource disk """
        self.disk_util.umount(self.RD_MOUNT_POINT)
        self.disk_util.umount('/mnt')

    def is_plain_mounted(self):
        """ return true if mount point is mounted from a non-crypt layer """
        mount_items = self.disk_util.get_mount_items()
        for mount_item in mount_items:
            if mount_item["dest"] == self.RD_MOUNT_POINT and not (mount_item["src"].startswith(CommonVariables.dev_mapper_root) or mount_item["src"].startswith(self.DEV_DM_PREFIX)):
                return True
        return False

    def is_crypt_mounted(self):
        """ return true if mount point is already on a crypt layer """
        mount_items = self.disk_util.get_mount_items()
        for mount_item in mount_items:
            if mount_item["dest"] == self.RD_MOUNT_POINT and (mount_item["src"].startswith(CommonVariables.dev_mapper_root) or mount_item["src"].startswith(self.DEV_DM_PREFIX)):
                return True
        return False

    def get_rd_device_mappers(self):
        """
        Retreive any device mapper device on the resource disk (e.g. /dev/dm-0).
        Can't imagine why there would be multiple device mappers here, but doesn't hurt to handle the case
        """
        device_items = self.disk_util.get_device_items(self.RD_DEV_PATH)
        device_mappers = []
        for device_item in device_items:
            # fstype should be crypto_LUKS
            dev_path = self.disk_util.get_device_path(device_item)
            if dev_path and dev_path.startswith("/dev/mapper"):
                device_mappers.append(device_item)
                self.logger.log('Found device mapper: ' + dev_path, level='Info')
        return device_mappers

    def remove_device_mappers(self):
        """
        Use dmsetup to remove the resource disk device mapper if it exists.
        This is to allow us to make sure that the resource disk is not being used by anything and we can
        safely luksFormat it.
        """

        # There could be a dependency between the
        something_closed = True
        while something_closed is True:
            # The mappers might be dependant on each other, like a crypt on an LVM.
            # Instead of trying to figure out the dependency tree we will try to close anything we can
            # and if anything does get closed we will refresh the list of devices and try to close everything again.
            # In effect we repeat until we either close everything or we reach a point where we can't close anything.
            dm_items = self.get_rd_device_mappers()
            something_closed = False

            if len(dm_items) == 0:
                self.logger.log('no resource disk device mapper found')
            for dm_item in dm_items:
                # try luksClose
                cmd = 'cryptsetup luksClose ' + dm_item.name
                if self.executor.Execute(cmd) == CommonVariables.process_success:
                    self.logger.log('Successfully closed cryptlayer: ' + dm_item.name)
                    something_closed = True
                else:
                    # try a dmsetup remove, in case its non-crypt device mapper (lvm, raid, something we don't know)
                    cmd = 'dmsetup remove ' + self.disk_util.get_device_path(dm_item)
                    if self.executor.Execute(cmd) == CommonVariables.process_success:
                        something_closed = True
                    else:
                        self.logger.log('failed to remove ' + dm_item.name)

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

    def wipe_partition_header(self):
        """ clear any possible header (luke or filesystem) by overwriting with 10MB of entropy """
        if not self.resource_disk_partition_exists():
            self.logger.log("resource partition does not exist, no header to clear")
            return True
        cmd = 'dd if=/dev/urandom of=' + self.RD_DEV_PATH + ' bs=512 count=20480'
        return self.executor.Execute(cmd) == CommonVariables.process_success

    def try_remount(self):
        """ mount the resource disk if not already mounted"""
        self.logger.log("In try_remount")

        if self.passphrase_filename:
            self.logger.log("passphrase_filename(value={0}) is not null, so trying to mount encrypted Resource Disk".format(self.passphrase_filename))

            if self.is_crypt_mounted():
                self.logger.log("Resource disk already encrypted and mounted")
                return True

            if self.resource_disk_partition_exists() and self.is_luks_device():
                self.disk_util.luks_open(passphrase_file=self.passphrase_filename, dev_path=self.RD_DEV_PATH, mapper_name=self.RD_MAPPER_NAME, header_file=None, uses_cleartext_key=False)
                self.logger.log("Trying to mount resource disk.")
                return self.mount(self.RD_MAPPER_PATH)
        else:
            self.logger.log("passphrase_filename(value={0}) is null, so trying to mount plain Resource Disk".format(self.passphrase_filename))
            if self.is_plain_mounted():
                self.logger.log("Resource disk already encrypted and mounted")
                return True
            return self.mount(self.RD_DEV_PATH)

        # conditions required to re-mount were not met
        return False

    def prepare(self):
        """ prepare a non-encrypted resource disk to be encrypted """
        self.configure_waagent()
        self.configure_fstab()
        if self.resource_disk_partition_exists():
            self.disk_util.swapoff()
            self.unmount_resource_disk()
            self.remove_device_mappers()
            self.wipe_partition_header()
        self.prepare_partition()
        return True

    def encrypt_format_mount(self):
        if not self.prepare():
            self.logger.error("Failed to prepare VM for Resource Disk Encryption")
            return False
        if not self.encrypt():
            self.logger.error("Failed to encrypt Resource Disk Encryption")
            return False
        if not self.make():
            self.logger.error("Failed to format the encrypted Resource Disk Encryption")
            return False
        if not self.mount():
            self.logger.error("Failed to mount after formatting and encrypting the Resource Disk Encryption")
            return False
        return True

    def automount(self):
        """ encrypt resource disk """
        # try to remount if the disk was previously encrypted and is still valid
        if self.try_remount():
            return True

        # unencrypted or unusable
        if self.is_encrypt_format_all():
            return self.encrypt_format_mount()
        else:
            self.logger.log('EncryptionFormatAll not in use, resource disk will not be automatically formatted and encrypted.')
            return False
