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

""" Unit tests for the EncryptionConfig module """

import unittest

from EncryptionConfig import EncryptionConfig
from EncryptionEnvironment import EncryptionEnvironment
from .console_logger import ConsoleLogger

class Test_EncryptionConfig(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()
        self.encryption_config = EncryptionConfig(EncryptionEnvironment(None, self.logger), self.logger)

    def test_get_cfg_none(self):
        self.assertEqual(self.encryption_config.get_cfg_val(None),"")
        
    def test_get_cfg_empty_string(self):
        self.assertEqual(self.encryption_config.get_cfg_val(""),"")