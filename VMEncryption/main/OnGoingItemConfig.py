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

import os
import os.path
import uuid
import time
import datetime
from Common import CommonVariables
from ConfigParser import ConfigParser
from ConfigUtil import ConfigUtil
from ConfigUtil import ConfigKeyValuePair


class OnGoingItemConfig(object):
    def __init__(self, encryption_environment,logger):
        self.encryption_environment = encryption_environment
        self.logger = logger
        self.original_dev_name_path = None
        self.original_dev_path = None
        self.mapper_name = None
        self.luks_header_file_path = None
        self.phase = None
        self.file_system = None
        self.mount_point = None 
        self.device_size = None
        self.from_end = None
        self.header_slice_file_path = None
        self.current_block_size = None
        self.current_source_path = None
        self.current_total_copy_size = None
        self.current_slice_index = None
        self.current_destination = None
        self.ongoing_item_config = ConfigUtil(encryption_environment.azure_crypt_ongoing_item_config_path, 'azure_crypt_ongoing_item_config', logger)

    def config_file_exists(self):
        return self.ongoing_item_config.config_file_exists()

    def get_original_dev_name_path(self):
        return self.ongoing_item_config.get_config(CommonVariables.OngoingItemOriginalDevNamePathKey)

    def get_original_dev_path(self):
        return self.ongoing_item_config.get_config(CommonVariables.OngoingItemOriginalDevPathKey)

    def get_mapper_name(self):
        return self.ongoing_item_config.get_config(CommonVariables.OngoingItemMapperNameKey)

    def get_header_file_path(self):
        return self.ongoing_item_config.get_config(CommonVariables.OngoingItemHeaderFilePathKey)

    def get_phase(self):
        return self.ongoing_item_config.get_config(CommonVariables.OngoingItemPhaseKey)

    def get_header_slice_file_path(self):
        return self.ongoing_item_config.get_config(CommonVariables.OngoingItemHeaderSliceFilePathKey)

    def get_file_system(self):
        return self.ongoing_item_config.get_config(CommonVariables.OngoingItemFileSystemKey)

    def get_mount_point(self):
        return self.ongoing_item_config.get_config(CommonVariables.OngoingItemMountPointKey)

    def get_device_size(self):
        device_size_value = self.ongoing_item_config.get_config(CommonVariables.OngoingItemDeviceSizeKey)
        if(device_size_value is None or device_size_value == ""):
            return None
        else:
            return long(device_size_value)

    def get_current_slice_index(self):
        current_slice_index_value = self.ongoing_item_config.get_config(CommonVariables.OngoingItemCurrentSliceIndexKey)
        if(current_slice_index_value is None or current_slice_index_value == ""):
            return None
        else:
            return long(current_slice_index_value)

    def get_from_end(self):
        return self.ongoing_item_config.get_config(CommonVariables.OngoingItemFromEndKey)

    def get_current_block_size(self):
        block_size_value = self.ongoing_item_config.get_config(CommonVariables.OngoingItemCurrentBlockSizeKey)
        if(block_size_value is None or block_size_value == ""):
            return None
        else:
            return long(block_size_value)

    def get_current_source_path(self):
        return self.ongoing_item_config.get_config(CommonVariables.OngoingItemCurrentSourcePathKey)

    def get_current_destination(self):
        return self.ongoing_item_config.get_config(CommonVariables.OngoingItemCurrentDestinationKey)
    
    def get_current_total_copy_size(self):
        total_copy_size_value = self.ongoing_item_config.get_config(CommonVariables.OngoingItemCurrentTotalCopySizeKey)
        if(total_copy_size_value is None or total_copy_size_value == ""):
            return None
        else:
            return long(total_copy_size_value)

    def get_luks_header_file_path(self):
        return self.ongoing_item_config.get_config(CommonVariables.OngoingItemCurrentLuksHeaderFilePathKey)

    def load_value_from_file(self):
        self.original_dev_name_path = self.get_original_dev_name_path()
        self.original_dev_path = self.get_original_dev_path()
        self.mapper_name = self.get_mapper_name()
        self.luks_header_file_path = self.get_luks_header_file_path()
        self.phase = self.get_phase()
        self.file_system = self.get_file_system()
        self.mount_point = self.get_mount_point() 
        self.device_size = self.get_device_size()
        self.from_end = self.get_from_end()
        self.header_slice_file_path = self.get_header_slice_file_path()
        self.current_block_size = self.get_current_block_size()
        self.current_source_path = self.get_current_source_path()
        self.current_total_copy_size = self.get_current_total_copy_size()
        self.current_slice_index = self.get_current_slice_index()
        self.current_destination = self.get_current_destination()

    def commit(self):
        key_value_pairs = []
        original_dev_name_path_pair = ConfigKeyValuePair(CommonVariables.OngoingItemOriginalDevNamePathKey, self.original_dev_name_path)
        key_value_pairs.append(original_dev_name_path_pair)

        original_dev_path_pair = ConfigKeyValuePair(CommonVariables.OngoingItemOriginalDevPathKey, self.original_dev_path)
        key_value_pairs.append(original_dev_path_pair)

        mapper_name_pair = ConfigKeyValuePair(CommonVariables.OngoingItemMapperNameKey, self.mapper_name)
        key_value_pairs.append(mapper_name_pair)

        header_file_pair = ConfigKeyValuePair(CommonVariables.OngoingItemHeaderFilePathKey, self.luks_header_file_path)
        key_value_pairs.append(header_file_pair)

        phase_pair = ConfigKeyValuePair(CommonVariables.OngoingItemPhaseKey, self.phase)
        key_value_pairs.append(phase_pair)

        header_slice_file_pair = ConfigKeyValuePair(CommonVariables.OngoingItemHeaderSliceFilePathKey, self.header_slice_file_path)
        key_value_pairs.append(header_slice_file_pair)

        file_system_pair = ConfigKeyValuePair(CommonVariables.OngoingItemFileSystemKey, self.file_system)
        key_value_pairs.append(file_system_pair)

        mount_point_pair = ConfigKeyValuePair(CommonVariables.OngoingItemMountPointKey, self.mount_point)
        key_value_pairs.append(mount_point_pair)

        device_size_pair = ConfigKeyValuePair(CommonVariables.OngoingItemDeviceSizeKey, self.device_size)
        key_value_pairs.append(device_size_pair)

        current_slice_index_pair = ConfigKeyValuePair(CommonVariables.OngoingItemCurrentSliceIndexKey, self.current_slice_index)
        key_value_pairs.append(current_slice_index_pair)

        from_end_pair = ConfigKeyValuePair(CommonVariables.OngoingItemFromEndKey, self.from_end)
        key_value_pairs.append(from_end_pair)

        current_source_path_pair = ConfigKeyValuePair(CommonVariables.OngoingItemCurrentSourcePathKey, self.current_source_path)
        key_value_pairs.append(current_source_path_pair)

        current_destination_pair = ConfigKeyValuePair(CommonVariables.OngoingItemCurrentDestinationKey, self.current_destination)
        key_value_pairs.append(current_destination_pair)

        current_total_copy_size_pair = ConfigKeyValuePair(CommonVariables.OngoingItemCurrentTotalCopySizeKey, self.current_total_copy_size)
        key_value_pairs.append(current_total_copy_size_pair)

        current_block_size_pair = ConfigKeyValuePair(CommonVariables.OngoingItemCurrentBlockSizeKey, self.current_block_size)
        key_value_pairs.append(current_block_size_pair)

        self.ongoing_item_config.save_configs(key_value_pairs)

    def clear_config(self):
        try:
            if(os.path.exists(self.encryption_environment.azure_crypt_ongoing_item_config_path)):
                self.logger.log(msg="archive the config file: {0}".format(self.encryption_environment.azure_crypt_ongoing_item_config_path))
                time_stamp = datetime.datetime.now()
                new_name = "{0}_{1}".format(self.encryption_environment.azure_crypt_ongoing_item_config_path, time_stamp)
                os.rename(self.encryption_environment.azure_crypt_ongoing_item_config_path, new_name)
            else:
                self.logger.log(msg=("the config file not exist: {0}".format(self.encryption_environment.azure_crypt_ongoing_item_config_path)), level = CommonVariables.WarningLevel)
            return True
        except OSError as e:
            self.logger.log("Failed to archive_backup_config with error: {0}, stack trace: {1}".format(e, traceback.format_exc()))
            return False

    def __str__(self):
        return "dev_uuid_path is {0}, mapper_name is {1}, luks_header_file_path is {2}, phase is {3}, header_slice_file_path is {4}, file system is {5}, mount_point is {6}, device size is {7}"\
                .format(self.original_dev_path,self.mapper_name,self.luks_header_file_path,self.phase,self.header_slice_file_path,self.file_system,self.mount_point,self.device_size)
