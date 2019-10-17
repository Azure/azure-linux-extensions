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
from Common import CommonVariables, CryptItem


class ResourceDiskUtil(object):
    """ Resource Disk Encryption Utilities """

    RD_MOUNT_POINT = '/mnt/resource'
    RD_BASE_DEV_PATH = os.path.join(CommonVariables.azure_symlinks_dir, 'resource')
    RD_DEV_PATH = os.path.join(CommonVariables.azure_symlinks_dir, 'resource-part1')
    DEV_DM_PREFIX = '/dev/dm-'
    # todo: consolidate this and other key file path references
    # (BekUtil.py, ExtensionParameter.py, and dracut patches)
    RD_MAPPER_NAME = 'resourceencrypt'
    RD_MAPPER_PATH = os.path.join(CommonVariables.dev_mapper_root, RD_MAPPER_NAME)

    def __init__(self, logger, disk_util, passphrase_filename, public_settings, distro_info):
        self.logger = logger
        self.executor = CommandExecutor(self.logger)
        self.disk_util = disk_util
        self.passphrase_filename = passphrase_filename  # WARNING: This may be null, in which case we mount the resource disk if its unencrypted and do nothing if it is.
        self.public_settings = public_settings
        self.distro_info = distro_info

    def _is_encrypt_format_all(self):
        """ return true if current encryption operation is EncryptFormatAll """
        encryption_operation = self.public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)
        if encryption_operation in [CommonVariables.EnableEncryptionFormatAll]:
            return True
        self.logger.log("Current encryption operation is not EnableEncryptionFormatAll")
        return False

    def _is_luks_device(self):
        """ checks if the device is set up with a luks header """
        if not self._resource_disk_partition_exists():
            return False
        cmd = 'cryptsetup isLuks ' + self.RD_DEV_PATH
        return (int)(self.executor.Execute(cmd, suppress_logging=True)) == CommonVariables.process_success

    def _resource_disk_partition_exists(self):
        """ true if udev name for resource disk partition exists """
        cmd = 'test -b ' + self.RD_DEV_PATH
        return (int)(self.executor.Execute(cmd, suppress_logging=True)) == CommonVariables.process_success

    def _encrypt(self):
        """ use disk util with the appropriate device mapper """
        return (int)(self.disk_util.encrypt_disk(dev_path=self.RD_DEV_PATH,
                                                 passphrase_file=self.passphrase_filename,
                                                 mapper_name=self.RD_MAPPER_NAME,
                                                 header_file=None)) == CommonVariables.process_success

    def _format_encrypted_partition(self):
        """ make a default file system on top of the crypt layer """
        make_result = self.disk_util.format_disk(dev_path=self.RD_MAPPER_PATH, file_system=CommonVariables.default_file_system)
        if make_result != CommonVariables.process_success:
            self.logger.log(msg="Failed to make file system on ephemeral disk", level=CommonVariables.ErrorLevel)
            return False
        # todo - drop DATALOSS_WARNING_README.txt file to disk
        return True

    def _mount_resource_disk(self, dev_path):
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

    def _configure_waagent(self):
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

    def _configure_fstab(self):
        """ remove resource disk from /etc/fstab if present """
        cmd = "sed -i.bak '/azure_resource-part1/d' /etc/fstab"
        if self.executor.ExecuteInBash(cmd) != CommonVariables.process_success:
            self.logger.log(msg="Failed to configure resource disk entry of /etc/fstab", level=CommonVariables.WarningLevel)
            return False
        return True

    def _unmount_resource_disk(self):
        """ unmount resource disk """
        self.disk_util.umount(self.RD_MOUNT_POINT)
        self.disk_util.umount(CommonVariables.encryption_key_mount_point)
        self.disk_util.umount('/mnt')
        self.disk_util.make_sure_path_exists(CommonVariables.encryption_key_mount_point)
        self.disk_util.mount_bek_volume("BEK VOLUME", CommonVariables.encryption_key_mount_point, "fmask=077")

    def _is_plain_mounted(self):
        """ return true if mount point is mounted from a non-crypt layer """
        mount_items = self.disk_util.get_mount_items()
        for mount_item in mount_items:
            if mount_item["dest"] == self.RD_MOUNT_POINT and not (mount_item["src"].startswith(CommonVariables.dev_mapper_root) or mount_item["src"].startswith(self.DEV_DM_PREFIX)):
                return True
        return False

    def _is_crypt_mounted(self):
        """ return true if mount point is already on a crypt layer """
        mount_items = self.disk_util.get_mount_items()
        for mount_item in mount_items:
            if mount_item["dest"] == self.RD_MOUNT_POINT and (mount_item["src"].startswith(CommonVariables.dev_mapper_root) or mount_item["src"].startswith(self.DEV_DM_PREFIX)):
                return True
        return False

    def _get_rd_device_mappers(self):
        """
        Retreive any device mapper device on the resource disk (e.g. /dev/dm-0).
        Can't imagine why there would be multiple device mappers here, but doesn't hurt to handle the case
        """
        device_items = self.disk_util.get_device_items(self.RD_DEV_PATH)
        device_mappers = []
        mapper_device_types = ["raid0", "raid1", "raid5", "raid10", "lvm", "crypt"]
        for device_item in device_items:
            # fstype should be crypto_LUKS
            dev_path = self.disk_util.get_device_path(device_item.name)
            if device_item.type in mapper_device_types:
                device_mappers.append(device_item)
                self.logger.log('Found device mapper: ' + dev_path, level='Info')
        return device_mappers

    def _remove_device_mappers(self):
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
            dm_items = self._get_rd_device_mappers()
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
                    cmd = 'dmsetup remove ' + self.disk_util.get_device_path(dm_item.name)
                    if self.executor.Execute(cmd) == CommonVariables.process_success:
                        something_closed = True
                    else:
                        self.logger.log('failed to remove ' + dm_item.name)

    def _prepare_partition(self):
        """ create partition on resource disk if missing """
        if self._resource_disk_partition_exists():
            return True
        self.logger.log("resource disk partition does not exist", level='Info')
        cmd = 'parted ' + self.RD_BASE_DEV_PATH + ' mkpart primary ext4 0% 100%'
        if self.executor.ExecuteInBash(cmd) == CommonVariables.process_success:
            # wait for the corresponding udev name to become available
            for i in range(0, 10):
                time.sleep(i)
                if self._resource_disk_partition_exists():
                    return True
        self.logger.log('unable to make resource disk partition')
        return False

    def _wipe_partition_header(self):
        """ clear any possible header (luke or filesystem) by overwriting with 10MB of entropy """
        if not self._resource_disk_partition_exists():
            self.logger.log("resource partition does not exist, no header to clear")
            return True
        cmd = 'dd if=/dev/urandom of=' + self.RD_DEV_PATH + ' bs=512 count=20480'
        return self.executor.Execute(cmd) == CommonVariables.process_success

    def try_remount(self):
        """ mount the resource disk if not already mounted"""
        self.logger.log("In try_remount")

        if self.passphrase_filename:
            self.logger.log("passphrase_filename(value={0}) is not null, so trying to mount encrypted Resource Disk".format(self.passphrase_filename))

            if self._is_crypt_mounted():
                self.logger.log("Resource disk already encrypted and mounted")
                return True

            if self._resource_disk_partition_exists() and self._is_luks_device():
                self.disk_util.luks_open(passphrase_file=self.passphrase_filename, dev_path=self.RD_DEV_PATH, mapper_name=self.RD_MAPPER_NAME, header_file=None, uses_cleartext_key=False)
                self.logger.log("Trying to mount resource disk.")
                return self._mount_resource_disk(self.RD_MAPPER_PATH)
        else:
            self.logger.log("passphrase_filename(value={0}) is null, so trying to mount plain Resource Disk".format(self.passphrase_filename))
            if self._is_plain_mounted():
                self.logger.log("Resource disk already encrypted and mounted")
                return True
            return self._mount_resource_disk(self.RD_DEV_PATH)

        # conditions required to re-mount were not met
        return False

    def prepare(self):
        """ prepare a non-encrypted resource disk to be encrypted """
        self._configure_waagent()
        self._configure_fstab()
        if self._resource_disk_partition_exists():
            self.disk_util.swapoff()
            self._unmount_resource_disk()
            self._remove_device_mappers()
            self._wipe_partition_header()
        self._prepare_partition()
        return True

    def add_to_fstab(self):
        with open("/etc/fstab") as f:
            lines = f.readlines()

        if not self.disk_util.is_bek_in_fstab_file(lines):
            lines.append(self.disk_util.get_fstab_bek_line())
            self.disk_util.add_bek_to_default_cryptdisks()

        if not any([line.startswith(self.RD_MAPPER_PATH) for line in lines]):
            if self.distro_info[0].lower() == 'ubuntu' and self.distro_info[1].startswith('14'):
                lines.append('{0} {1} auto defaults,discard,nobootwait 0 0\n'.format(self.RD_MAPPER_PATH, self.RD_MOUNT_POINT))
            else:
                lines.append('{0} {1} auto defaults,discard,nofail 0 0\n'.format(self.RD_MAPPER_PATH, self.RD_MOUNT_POINT))

        with open('/etc/fstab', 'w') as f:
            f.writelines(lines)

    def encrypt_format_mount(self):
        if not self.prepare():
            self.logger.log("Failed to prepare VM for Resource Disk Encryption", CommonVariables.ErrorLevel)
            return False
        if not self._encrypt():
            self.logger.log("Failed to encrypt Resource Disk Encryption", CommonVariables.ErrorLevel)
            return False
        if not self._format_encrypted_partition():
            self.logger.log("Failed to format the encrypted Resource Disk Encryption", CommonVariables.ErrorLevel)
            return False
        if not self._mount_resource_disk(self.RD_MAPPER_PATH):
            self.logger.log("Failed to mount after formatting and encrypting the Resource Disk Encryption", CommonVariables.ErrorLevel)
            return False
        if not self.disk_util.should_use_azure_crypt_mount():
            self.add_resource_disk_to_crypttab()
        return True

    def add_resource_disk_to_crypttab(self):
        self.logger.log("Adding resource disk to the crypttab file")
        crypt_item = CryptItem()
        crypt_item.dev_path = self.RD_DEV_PATH
        crypt_item.mapper_name = self.RD_MAPPER_NAME
        crypt_item.uses_cleartext_key = False
        self.disk_util.remove_crypt_item(crypt_item) # Remove old item in case it was already there
        self.disk_util.add_crypt_item_to_crypttab(crypt_item, self.passphrase_filename)
        self.add_to_fstab()

    def automount(self):
        """ encrypt resource disk """
        rd_mounted = False
        # try to remount if the disk was previously encrypted and is still valid
        if self.try_remount():
            rd_mounted = True
        # unencrypted or unusable
        elif self._is_encrypt_format_all():
            rd_mounted = self.encrypt_format_mount()
        else:
            self.logger.log('EncryptionFormatAll not in use, resource disk will not be automatically formatted and encrypted.')
        
        if rd_mounted and self._is_crypt_mounted() and self.disk_util.should_use_azure_crypt_mount():
            self.add_resource_disk_to_crypttab()
        
        return rd_mounted
