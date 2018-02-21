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

""" Unit tests for MetadataUtil module """

import unittest
import console_logger
import MetadataUtil

class TestMetadataUtilMethods(unittest.TestCase):
    def setUp(self):
        self.logger = console_logger.ConsoleLogger()
        self.aims = MetadataUtil.MetadataUtil(self.logger)

    def test_isnt_vmss(self):
        self.aims.metadata = {u'compute': {u'placementGroupId': u''}}
        self.assertEqual(self.aims.is_vmss(), False)

    def test_is_vmss(self):
        self.aims.metadata = {u'compute': {u'placementGroupId': u'1d5a05c0-ce18-4950-8499-0bb2a26cc70a'}}
        self.assertEqual(self.aims.is_vmss(), True)