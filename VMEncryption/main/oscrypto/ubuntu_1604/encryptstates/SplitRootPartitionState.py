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

import os
import re
import sys

import parted

from time import sleep
from OSEncryptionState import *

class SplitRootPartitionState(OSEncryptionState):
    def __init__(self, context):
        super(SplitRootPartitionState, self).__init__('SplitRootPartitionState', context)

    def should_enter(self):
        self.context.logger.log("Verifying if machine should enter split_root_partition state")

        if not super(SplitRootPartitionState, self).should_enter():
            return False
        
        self.context.logger.log("Performing enter checks for split_root_partition state")


        attempt = 1
        while attempt < 10:
            fsck_result = self.command_executor.Execute("e2fsck -yf {0}".format(self.rootfs_block_device))

            if fsck_result == 0:
                break

            self.command_executor.Execute('systemctl restart systemd-udevd')
            self.command_executor.Execute('systemctl restart systemd-timesyncd')
            self.command_executor.Execute('udevadm trigger')

            sleep(10)

            attempt += 1

        if not attempt < 10:
            return False
                
        return True

    def enter(self):
        if not self.should_enter():
            return

        self.context.logger.log("Entering split_root_partition state")

        device = parted.getDevice(self.rootfs_disk)
        disk = parted.newDisk(device)

        original_root_fs_size = self._get_root_fs_size_in(device.sectorSize)
        self.context.logger.log("Original root filesystem size (sectors): {0}".format(original_root_fs_size))

        desired_boot_partition_size = parted.sizeToSectors(256, 'MiB', device.sectorSize)
        self.context.logger.log("Desired boot partition size (sectors): {0}".format(desired_boot_partition_size))
      
        desired_root_fs_size = original_root_fs_size - desired_boot_partition_size
        self.context.logger.log("Desired root filesystem size (sectors): {0}".format(desired_root_fs_size))

        attempt = 1
        while attempt < 10:
            resize_result = self.command_executor.Execute("resize2fs {0} {1}s".format(self.rootfs_block_device, desired_root_fs_size))

            if resize_result == 0:
                break
            else:
                self.command_executor.Execute('systemctl restart systemd-udevd')
                self.command_executor.Execute('systemctl restart systemd-timesyncd')
                self.command_executor.Execute('udevadm trigger')

                sleep(10)

                attempt += 1

        resized_root_fs_size = self._get_root_fs_size_in(device.sectorSize)

        self.context.logger.log("Resized root filesystem size (sectors): {0}".format(resized_root_fs_size))

        if not desired_root_fs_size == resized_root_fs_size:
            raise Exception("resize2fs failed, desired: {0}, resized: {1}".format(desired_root_fs_size,
                                                                                  resized_root_fs_size))

        self.context.logger.log("Root filesystem resized successfully")

        root_partition = disk.partitions[0]

        original_root_partition_start = root_partition.geometry.start
        original_root_partition_end = root_partition.geometry.end

        self.context.logger.log("Original root partition start (sectors): {0}".format(original_root_partition_start))
        self.context.logger.log("Original root partition end (sectors): {0}".format(original_root_partition_end))

        desired_root_partition_start = original_root_partition_start
        desired_root_partition_end = original_root_partition_end - desired_boot_partition_size
        desired_root_partition_size = desired_root_partition_end - desired_root_partition_start

        self.context.logger.log("Desired root partition start (sectors): {0}".format(desired_root_partition_start))
        self.context.logger.log("Desired root partition end (sectors): {0}".format(desired_root_partition_end))
        self.context.logger.log("Desired root partition size (sectors): {0}".format(desired_root_partition_size))

        desired_root_partition_geometry = parted.Geometry(device=device,
                                                          start=desired_root_partition_start,
                                                          length=desired_root_partition_size)
        root_partition_constraint = parted.Constraint(exactGeom=desired_root_partition_geometry)
        disk.setPartitionGeometry(partition=root_partition,
                                  constraint=root_partition_constraint,
                                  start=desired_root_partition_start,
                                  end=desired_root_partition_end)

        desired_boot_partition_start = disk.getFreeSpaceRegions()[1].start
        desired_boot_partition_end = disk.getFreeSpaceRegions()[1].end
        desired_boot_partition_size = disk.getFreeSpaceRegions()[1].length

        self.context.logger.log("Desired boot partition start (sectors): {0}".format(desired_boot_partition_start))
        self.context.logger.log("Desired boot partition end (sectors): {0}".format(desired_boot_partition_end))

        desired_boot_partition_geometry = parted.Geometry(device=device,
                                                          start=desired_boot_partition_start,
                                                          length=desired_boot_partition_size)
        boot_partition_constraint = parted.Constraint(exactGeom=desired_boot_partition_geometry)
        desired_boot_partition = parted.Partition(disk=disk,
                                                  type=parted.PARTITION_NORMAL,
                                                  geometry=desired_boot_partition_geometry)

        disk.addPartition(partition=desired_boot_partition, constraint=boot_partition_constraint)

        disk.commit()

        probed_root_fs = parted.probeFileSystem(disk.partitions[0].geometry)
        if not probed_root_fs == 'ext4':
            raise Exception("Probed root fs is not ext4")

        disk.partitions[1].setFlag(parted.PARTITION_BOOT)

        disk.commit()
        
        self.command_executor.Execute("partprobe", True)
        self.command_executor.Execute("mkfs.ext2 {0}".format(self.bootfs_block_device), True)
        
        boot_partition_uuid = self._get_uuid(self.bootfs_block_device)

        # Move stuff from /oldroot/boot to new partition, make new partition mountable at the same spot
        self.command_executor.Execute("mount {0} /oldroot".format(self.rootfs_block_device), True)
        self.command_executor.Execute("mkdir /oldroot/memroot", True)
        self.command_executor.Execute("mount --make-rprivate /", True)
        self.command_executor.Execute("pivot_root /oldroot /oldroot/memroot", True)
        self.command_executor.ExecuteInBash("for i in dev proc sys; do mount --move /memroot/$i /$i; done", True)
        self.command_executor.Execute("mv /boot /boot.backup", True)
        self.command_executor.Execute("mkdir /boot", True)
        self._append_boot_partition_uuid_to_fstab(boot_partition_uuid)
        self.command_executor.Execute("cp /etc/fstab /memroot/etc/fstab", True)
        self.command_executor.Execute("mount /boot", True)
        self.command_executor.ExecuteInBash("mv /boot.backup/* /boot/", True)
        self.command_executor.Execute("rmdir /boot.backup", True)
        self.command_executor.Execute("mount --make-rprivate /", True)
        self.command_executor.Execute("pivot_root /memroot /memroot/oldroot", True)
        self.command_executor.Execute("rmdir /oldroot/memroot", True)
        self.command_executor.ExecuteInBash("for i in dev proc sys; do mount --move /oldroot/$i /$i; done", True)
        self.command_executor.Execute("systemctl restart rsyslog", True)
        self.command_executor.Execute("systemctl restart systemd-udevd", True)
        self.command_executor.Execute("systemctl restart walinuxagent", True)
        self.command_executor.Execute("umount /oldroot/boot", True)
        self.command_executor.Execute("umount /oldroot", True)
        
    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit split_root_partition state")
        
        self.command_executor.ExecuteInBash("mount /boot || mountpoint /boot", True)
        self.command_executor.ExecuteInBash("[ -e /boot/grub ]", True)
        self.command_executor.Execute("umount /boot", True)

        return super(SplitRootPartitionState, self).should_exit()

    def _get_uuid(self, partition_name):
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(command_to_execute="blkid -s UUID -o value {0}".format(partition_name),
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)
        return proc_comm.stdout.strip()

    def _append_boot_partition_uuid_to_fstab(self, boot_partition_uuid):
        self.context.logger.log("Updating fstab")

        contents = None

        with open('/etc/fstab', 'r') as f:
            contents = f.read()

        contents += '\n'
        contents += 'UUID={0}\t/boot\text2\tdefaults\t0 0'.format(boot_partition_uuid)
        contents += '\n'

        with open('/etc/fstab', 'w') as f:
            f.write(contents)

        self.context.logger.log("fstab updated successfully")

    def _get_root_fs_size_in(self, sector_size):
        proc_comm = ProcessCommunicator()

        attempt = 1
        while attempt < 10:
            dump_result = self.command_executor.Execute(command_to_execute="dumpe2fs -h {0}".format(self.rootfs_block_device),
                                                        raise_exception_on_failure=False,
                                                        communicator=proc_comm)

            if dump_result == 0:
                break

            self.command_executor.Execute('systemctl restart systemd-udevd')
            self.command_executor.Execute('systemctl restart systemd-timesyncd')
            self.command_executor.Execute('udevadm trigger')

            sleep(10)

            attempt += 1

        if not attempt < 10:
            return Exception("Could not dumpe2fs, stderr: \n{0}".format(proc_comm.stderr))
        

        root_fs_block_count = re.findall(r'Block count:\s*(\d+)', proc_comm.stdout)
        root_fs_block_size = re.findall(r'Block size:\s*(\d+)', proc_comm.stdout)

        if not root_fs_block_count or not root_fs_block_size:
            raise Exception("Error parsing dumpe2fs output, count={0}, size={1}".format(root_fs_block_count,
                                                                                        root_fs_block_size))

        root_fs_block_count = int(root_fs_block_count[0])
        root_fs_block_size = int(root_fs_block_size[0])
        root_fs_size = parted.sizeToSectors(root_fs_block_count * root_fs_block_size, 'B', sector_size)

        return root_fs_size
