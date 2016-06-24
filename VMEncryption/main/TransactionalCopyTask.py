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
import sys
import shlex
from subprocess import *
from CommandExecuter import CommandExecuter
from Common import CommonVariables
from ConfigUtil import ConfigUtil
from OnGoingItemConfig import *


class TransactionalCopyTask(object):
    """
    copy_total_size is in byte, skip_target_size is also in byte
    slice_size is in byte 50M
    """
    def __init__(self, logger, disk_util, ongoing_item_config, patching, encryption_environment):
        """
        copy_total_size is in bytes.
        """
        self.command_executer = CommandExecuter(logger)
        self.ongoing_item_config = ongoing_item_config
        self.total_size = self.ongoing_item_config.get_current_total_copy_size()
        self.block_size = self.ongoing_item_config.get_current_block_size()
        self.source_dev_full_path = self.ongoing_item_config.get_current_source_path()
        self.destination = self.ongoing_item_config.get_current_destination()
        self.current_slice_index = self.ongoing_item_config.get_current_slice_index()
        self.from_end = self.ongoing_item_config.get_from_end()

        self.last_slice_size = self.total_size % self.block_size
        # we add 1 even the last_slice_size is zero.
        self.total_slice_size = ((self.total_size - self.last_slice_size) / self.block_size) + 1

        self.encryption_environment = encryption_environment
        self.logger = logger
        self.patching = patching
        self.disk_util = disk_util
        self.tmpfs_mount_point = "/mnt/azure_encrypt_tmpfs"
        self.slice_file_path = self.tmpfs_mount_point + "/slice_file"
        self.copy_command = self.patching.dd_path

    def resume_copy_internal(self, copy_slice_item_backup_file_size, skip_block, original_total_copy_size):
        block_size_of_slice_item_backup = 512
        #copy the left slice
        if(copy_slice_item_backup_file_size <= original_total_copy_size):
            skip_of_slice_item_backup_file = copy_slice_item_backup_file_size / block_size_of_slice_item_backup
            left_count = ((original_total_copy_size - copy_slice_item_backup_file_size) / block_size_of_slice_item_backup)
            total_count = original_total_copy_size / block_size_of_slice_item_backup
            original_device_skip_count = (self.block_size * skip_block) / block_size_of_slice_item_backup 
            if(left_count != 0):
                dd_cmd = str(self.copy_command) + ' if=' + self.source_dev_full_path + ' of=' + self.encryption_environment.copy_slice_item_backup_file \
                                 + ' bs=' + str(block_size_of_slice_item_backup) + ' skip=' + str(original_device_skip_count + skip_of_slice_item_backup_file) + ' seek=' + str(skip_of_slice_item_backup_file) + ' count=' + str(left_count)
                returnCode = self.command_executer.Execute(dd_cmd)
                if(returnCode != CommonVariables.process_success):
                    return returnCode
            dd_cmd = str(self.copy_command) + ' if=' + self.encryption_environment.copy_slice_item_backup_file + ' of=' + self.destination \
                        + ' bs=' + str(block_size_of_slice_item_backup) + ' seek=' + str(original_device_skip_count) + ' count=' + str(total_count)
            returnCode = self.command_executer.Execute(dd_cmd)
            if(returnCode != CommonVariables.process_success):
                return returnCode
            else:
                self.current_slice_index += 1
                self.ongoing_item_config.current_slice_index = self.current_slice_index
                self.ongoing_item_config.commit()
                if(os.path.exists(self.encryption_environment.copy_slice_item_backup_file)):
                    os.remove(self.encryption_environment.copy_slice_item_backup_file)
                return returnCode
        else:
            self.logger.log(msg="copy_slice_item_backup_file_size is bigger than original_total_copy_size ",level=CommonVariables.ErrorLevel)
            return CommonVariables.backup_slice_file_error

    def resume_copy(self):
        if(self.from_end.lower() == 'true'):
            skip_block = (self.total_slice_size - self.current_slice_index - 1)
        else:
            skip_block = self.current_slice_index

        returnCode = CommonVariables.process_success

        if(self.current_slice_index == 0):
            if(self.last_slice_size > 0):
                if(os.path.exists(self.encryption_environment.copy_slice_item_backup_file)):
                    copy_slice_item_backup_file_size = os.path.getsize(self.encryption_environment.copy_slice_item_backup_file)
                    returnCode = self.resume_copy_internal(copy_slice_item_backup_file_size = copy_slice_item_backup_file_size,
                                                            skip_block = skip_block,
                                                            original_total_copy_size = self.last_slice_size)
                else:
                    self.logger.log(msg = "1. the slice item backup file not exists.", level = CommonVariables.WarningLevel)
            else:
                self.logger.log(msg = "the last slice", level = CommonVariables.WarningLevel)
        else:
            if(os.path.exists(self.encryption_environment.copy_slice_item_backup_file)):
                copy_slice_item_backup_file_size = os.path.getsize(self.encryption_environment.copy_slice_item_backup_file)
                returnCode = self.resume_copy_internal(copy_slice_item_backup_file_size,skip_block=skip_block, original_total_copy_size=self.block_size)
            else:
                self.logger.log(msg = "2. unfortunately the slice item backup file not exists.", level = CommonVariables.WarningLevel)
        return returnCode

    def copy_last_slice(self,skip_block):
        block_size_of_last_slice = 512
        skip_of_last_slice = (skip_block * self.block_size) / block_size_of_last_slice
        count_of_last_slice = self.last_slice_size / block_size_of_last_slice

        copy_result = self.copy_internal(from_device = self.source_dev_full_path, to_device = self.destination,
                                         skip = skip_of_last_slice, seek = skip_of_last_slice, block_size = block_size_of_last_slice, count = count_of_last_slice)
        return copy_result

    def begin_copy(self):
        """
        check the device_item size first, cut it
        """
        self.resume_copy()
        if(self.from_end.lower() == 'true'):
            while(self.current_slice_index < self.total_slice_size):
                skip_block = (self.total_slice_size - self.current_slice_index - 1)

                if(self.current_slice_index == 0):
                    if(self.last_slice_size > 0):
                        copy_result = self.copy_last_slice(skip_block)
                        if(copy_result != CommonVariables.process_success):
                            return copy_result
                    else:
                        self.logger.log(msg = "the last slice size is zero, so skip the 0 index.")
                else:
                    copy_result = self.copy_internal(from_device = self.source_dev_full_path, to_device = self.destination, \
                                                     skip = skip_block, seek = skip_block, block_size = self.block_size)
                    if(copy_result != CommonVariables.process_success):
                        return copy_result

                self.current_slice_index += 1
                self.ongoing_item_config.current_slice_index = self.current_slice_index
                self.ongoing_item_config.commit()

            return CommonVariables.process_success
        else:
            while(self.current_slice_index < self.total_slice_size):
                skip_block = self.current_slice_index

                if(self.current_slice_index == (self.total_slice_size - 1)):
                    if(self.last_slice_size > 0):
                        copy_result = self.copy_last_slice(skip_block)
                        if(copy_result != CommonVariables.process_success):
                            return copy_result
                    else:
                        self.logger.log(msg = "the last slice size is zero, so skip the last slice index.")
                else:
                    copy_result = self.copy_internal(from_device = self.source_dev_full_path, to_device = self.destination,\
                                                    skip = skip_block, seek = skip_block, block_size = self.block_size)
                    if(copy_result != CommonVariables.process_success):
                        return copy_result

                self.current_slice_index += 1
                self.ongoing_item_config.current_slice_index = self.current_slice_index
                self.ongoing_item_config.commit()
            return CommonVariables.process_success

    """
    TODO: if the copy failed?
    """
    def copy_internal(self, from_device, to_device,  block_size, skip=0, seek=0, count=1):
        """
        first, copy the data to the middle cache
        """
        dd_cmd = str(self.copy_command) + ' if=' + from_device + ' of=' + self.slice_file_path + ' bs=' + str(block_size) + ' skip=' + str(skip) + ' count=' + str(count)
        returnCode = self.command_executer.Execute(dd_cmd)
        if(returnCode != CommonVariables.process_success):
            self.logger.log(msg=("{0} is {1}".format(dd_cmd,returnCode)), level = CommonVariables.ErrorLevel)
            return returnCode
        else:
            slice_file_size = os.path.getsize(self.slice_file_path)
            self.logger.log(msg=("slice_file_size is: {0}".format(slice_file_size)))
            """
            second, copy the data in the middle cache to the backup slice.
            """
            backup_slice_item_cmd = str(self.copy_command) + ' if=' + self.slice_file_path + ' of=' + self.encryption_environment.copy_slice_item_backup_file + ' bs=' + str(block_size) + ' count=' + str(count)
            backup_slice_args = shlex.split(backup_slice_item_cmd)
            backup_process = Popen(backup_slice_args)
            self.logger.log("backup_slice_item_cmd is:{0}".format(backup_slice_item_cmd))

            """
            third, copy the data in the middle cache to the target device.
            """
            dd_cmd = str(self.copy_command) + ' if=' + self.slice_file_path + ' of=' + to_device + ' bs=' + str(block_size) + ' seek=' + str(seek) + ' count=' + str(count)
            returnCode = self.command_executer.Execute(dd_cmd)
            if(returnCode != CommonVariables.process_success):
                self.logger.log(msg=("{0} is: {1}".format(dd_cmd, returnCode)), level = CommonVariables.ErrorLevel)
            else:
                #the copy done correctly, so clear the backup slice file item.
                backup_process.kill()
                if(os.path.exists(self.encryption_environment.copy_slice_item_backup_file)):
                    self.logger.log(msg = "clean up the backup file")
                    os.remove(self.encryption_environment.copy_slice_item_backup_file)
                if(os.path.exists(self.slice_file_path)):
                    self.logger.log(msg = "clean up the slice file")
                    os.remove(self.slice_file_path)
            return returnCode

    def prepare_mem_fs(self):
        self.disk_util.make_sure_path_exists(self.tmpfs_mount_point)
        commandToExecute = self.patching.mount_path + " -t tmpfs -o size=" + str(self.block_size + 1024) + " tmpfs " + self.tmpfs_mount_point
        self.logger.log("prepare mem fs script is: {0}".format(commandToExecute))
        returnCode = self.command_executer.Execute(commandToExecute)
        return returnCode

    def clear_mem_fs(self):
        commandToExecute = self.patching.umount_path + " " + self.tmpfs_mount_point
        returnCode = self.command_executer.Execute(commandToExecute)
        return returnCode
