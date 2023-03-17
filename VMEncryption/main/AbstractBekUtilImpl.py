#!/usr/bin/env python
#
# Azure Disk Encryption For Linux extension
#
# Copyright 2016 Microsoft Corporation
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
import sys
from Common import TestHooks,CommonVariables
import base64
import abc
from abc import abstractmethod
# compatible with Python 2 *and* 3
ABC = abc.ABCMeta('ABC', (object,), {'__slots__': ()}) 

class BekMissingException(Exception):
    """
    BEK volume missing or not initialized. 
    add retry-logic to the network api call.
    """
    def __init__(self, value):
       self.value = value

    def __str__(self):
       return(repr(self.value))

class AbstractBekUtilImpl(ABC):
    '''
    This is an interface used for funcitonality implementation for BEK util class
    '''
    wrong_fs_msg = "BEK disk does not have vfat filesystem."
    not_mounted_msg = "BEK disk is not mounted."
    partition_missing_msg = "BEK disk does not have expected partition."
    bek_missing_msg = "BEK disk is not attached."
    
    def generate_passphrase(self):
        if TestHooks.use_hard_code_passphrase:
            return TestHooks.hard_code_passphrase
        else:
            with open("/dev/urandom", "rb") as _random_source:
                bytes = _random_source.read(CommonVariables.PassphraseLengthInBytes)
                passphrase_generated = base64.b64encode(bytes)
            return passphrase_generated    
    
    def store_passphrase(self,key_File_Path,bek_filename,passphrase):
        # ensure base64 encoded passphrase string is identically encoded in
        # python2 and python3 environments for consistency in output format
        if sys.version_info[0] < 3:
            if isinstance(passphrase, str):
                passphrase = passphrase.decode('utf-8')
        with open(os.path.join(key_File_Path, bek_filename), "wb") as f:
            f.write(passphrase)
        for bek_file in os.listdir(key_File_Path):
            if bek_filename in bek_file and bek_filename != bek_file:
                with open(os.path.join(key_File_Path, bek_file), "wb") as f:
                    f.write(passphrase)

    @abstractmethod
    def store_bek_passphrase(self, encryption_config, passphrase):
        pass
    @abstractmethod
    def get_bek_passphrase_file(self, encryption_config):
        pass
    
    def mount_bek_volume(self):
        pass

    def is_bek_volume_mounted_and_formatted(self):
        pass

    def is_bek_disk_attached_and_partitioned(self):
        pass

    def umount_azure_passhprase(self, encryption_config, force=False):
        pass

    def delete_bek_passphrase_file(self, encryption_config):
        bek_filename = encryption_config.get_bek_filename()
        bek_file = self.get_bek_passphrase_file(encryption_config)
        if not bek_file:
            return
        bek_dir = os.path.dirname(bek_file)
        for file in os.listdir(bek_dir):
            if bek_filename in file:
                os.remove(os.path.join(bek_dir, file))
