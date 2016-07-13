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

        self.command_executor.Execute("e2fsck -yf /dev/sda1", True)
                
        return True

    def enter(self):
        if not self.should_enter():
            return

        self.context.logger.log("Entering split_root_partition state")

        device = parted.getDevice('/dev/sda')
        disk = parted.newDisk(device)
        root_partition = disk.partitions[0]

        original_root_partition_size_sectors = root_partition.getLength()
        original_root_fs_size_sectors = self._get_root_fs_size_in_sectors(device.sectorSize)

        self.context.logger.log("Original root partition size (sectors): {0}".format(original_root_partition_size_sectors))
        self.context.logger.log("Original root filesystem size (sectors): {0}".format(original_root_fs_size_sectors))

        desired_boot_partition_size_sectors = parted.sizeToSectors(300, 'MiB', device.sectorSize)

        self.context.logger.log("Desired boot partition size (sectors): {0}".format(desired_boot_partition_size_sectors))
        
        desired_root_partition_size_sectors = original_root_partition_size_sectors - desired_boot_partition_size_sectors
        desired_root_fs_size_sectors = original_root_fs_size_sectors - desired_boot_partition_size_sectors

        self.context.logger.log("Desired root partition size (sectors): {0}".format(desired_root_partition_size_sectors))
        self.context.logger.log("Desired root filesystem size (sectors): {0}".format(desired_root_fs_size_sectors))

        self.command_executor.Execute("resize2fs /dev/sda1 {0}s".format(desired_root_fs_size_sectors), True)

        resized_root_fs_size_sectors = self._get_root_fs_size_in_sectors(device.sectorSize)

        self.context.logger.log("Resized root filesystem size (sectors): {0}".format(resized_root_fs_size_sectors))

        if not desired_root_fs_size_sectors == resized_root_fs_size_sectors:
            raise Exception("resize2fs failed, desired: {0}, resized: {1}".format(desired_root_fs_size_sectors,
                                                                                  resized_root_fs_size_sectors))

        self.context.logger.log("Root filesystem resized successfully")
        
    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit split_root_partition state")

        return super(SplitRootPartitionState, self).should_exit()

    def _get_root_fs_size_in_sectors(self, sector_size):
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(command_to_execute="dumpe2fs -h /dev/sda1",
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)

        root_fs_block_count = re.findall(r'Block count:\s*(\d+)', proc_comm.stdout)
        root_fs_block_size = re.findall(r'Block size:\s*(\d+)', proc_comm.stdout)

        if not root_fs_block_count or not root_fs_block_size:
            raise Exception("Error parsing dumpe2fs output, count={0}, size={1}".format(root_fs_block_count,
                                                                                        root_fs_block_size))

        root_fs_block_count = int(root_fs_block_count[0])
        root_fs_block_size = int(root_fs_block_size[0])
        root_fs_size_sectors = parted.sizeToSectors(root_fs_block_count * root_fs_block_size, 'B', sector_size)

        return root_fs_size_sectors
