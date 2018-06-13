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

""" Unit tests for the DiskUtil module """

import unittest
import os

import console_logger
import patch
import DiskUtil

class TestDiskUtilMethods(unittest.TestCase):
    def setUp(self):
        self.logger = console_logger.ConsoleLogger()
        self.distro_patcher = patch.GetDistroPatcher(self.logger)
        self.disk_util = DiskUtil.DiskUtil(None, None, self.logger, None)

    def test_get_simulated_pkname_output(self):
        self.assertIn('PKNAME',self.disk_util.get_simulated_pkname_output())

    def test_get_lsblk_output(self):
        self.assertIn('PKNAME',self.disk_util.get_lsblk_output())

    def test_get_lsblk_tree(self):
        self.assertIsNotNone(self.disk_util.get_lsblk_tree())
