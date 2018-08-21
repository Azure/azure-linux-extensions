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

""" Unit tests for the ResourceDiskUtil module """

import unittest
import os

import console_logger
import patch
import ResourceDiskUtil

class TestResourceDiskUtilMethods(unittest.TestCase):
    def setUp(self):
        self.logger = console_logger.ConsoleLogger()
        self.distro_patcher = patch.GetDistroPatcher(self.logger)
        self.resource_disk = ResourceDiskUtil.ResourceDiskUtil(self.logger, self.logger, self.distro_patcher)

    def test_is_luks_device(self):
        self.assertEqual(self.resource_disk.is_luks_device(), False)

    def test_is_luks_device_opened(self):
        self.assertEqual(self.resource_disk.is_luks_device_opened(), False)

    def test_is_valid_key(self):
        self.assertEqual(self.resource_disk.is_valid_key(), False)

    def test_configure_waagent(self):
        self.assertEqual(self.resource_disk.configure_waagent(), True)

    def test_is_crypt_mounted(self):
        self.assertEqual(self.resource_disk.is_crypt_mounted(), False)

    def test_try_remount(self):
        self.assertEqual(self.resource_disk.try_remount(), False)

    def test_automount(self):
        # validate preconditions
        self.assertEqual(self.resource_disk.is_luks_device(), False)
        self.assertEqual(self.resource_disk.is_luks_device_opened(), False)

        # run the function under test
        self.assertEqual(self.resource_disk.automount(), True)
        
        # validate postconditions
        self.assertEqual(self.resource_disk.is_luks_device(), True)
        self.assertEqual(self.resource_disk.is_luks_device_opened(), True)
        self.assertEqual(self.resource_disk.is_luks_device_opened(), True)
        self.assertEqual(self.resource_disk.is_valid_key(), True)
        self.assertEqual(self.resource_disk.try_remount(), True)

        # cleanup and restore original system state
        os.system("umount /mnt/resource")
        os.system('dmsetup remove /dev/mapper/' + self.resource_disk.mapper_name)
        os.system('dd if=/dev/urandom of=/dev/disk/azure/resource-part1 bs=512 count=20480')
        os.system('parted /dev/disk/azure/resource rm 1')

