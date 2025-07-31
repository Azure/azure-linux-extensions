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

""" Unit tests for the ExtensionParameter module """

import unittest
import Common
import EncryptionEnvironment
import json
from console_logger import ConsoleLogger

try:
    import unittest.mock as mock # python 3+ 
except ImportError:
    import mock # python2

# waagentloader is a python3+ compatible loader
from Utils.waagentloader import load_waagent  

class Test_EncryptionConfig(unittest.TestCase):
    @mock.patch('Utils.waagentloader.load_waagent', return_value=None)
    def setUp(self, load_waagent_mock):
        #mock load_waagent before importing ExtensionParameter so that unit tests can run outside of Azure VM context
        import ExtensionParameter
        self.logger = ConsoleLogger()
        mock_public_settings = json.loads('{"EncryptionOperation": ""}')
        self.extension_parameter = ExtensionParameter.ExtensionParameter(None, self.logger, None, EncryptionEnvironment.EncryptionEnvironment(None, self.logger), None, mock_public_settings)

    def test_kv_equivalent_true(self):
        self.assertEqual(self.extension_parameter._is_kv_equivalent("https://ASDF","https://asdf"),True)
        self.assertEqual(self.extension_parameter._is_kv_equivalent("https://asdf","https://asdf/"),True)
        self.assertEqual(self.extension_parameter._is_kv_equivalent("https://asdf/","https://asdf"),True)
        self.assertEqual(self.extension_parameter._is_kv_equivalent("https://ASDF/","https://asdf"),True)
        self.assertEqual(self.extension_parameter._is_kv_equivalent("https://asdf","https://ASDF/"),True)

        kv_urls = [
            'https://testkv1.vault.windows.net',
            'https://testkv1.vault.windows.net/',
            'https://testkv1.vault.windows.net:443',
            'https://testkv1.vault.windows.net:443/'
            ]

        for i in range(len(kv_urls)):
            self.assertEqual(self.extension_parameter._is_kv_equivalent(kv_urls[0],kv_urls[i].upper()),True)
            self.assertEqual(self.extension_parameter._is_kv_equivalent(kv_urls[0].upper(),kv_urls[i]),True)


        kek_urls = [
            'https://testkv1.vault.windows.net/keys/kekname/00000000000000000000000000000000',
            'https://testkv1.vault.windows.net/keys/kekname/00000000000000000000000000000000',
            'https://testkv1.vault.windows.net:443/keys/kekname/00000000000000000000000000000000',
            'https://testkv1.vault.windows.net:443/keys/kekname/00000000000000000000000000000000/'
            ]

        for i in range(len(kek_urls)):
            self.assertEqual(self.extension_parameter._is_kv_equivalent(kek_urls[0],kek_urls[i].upper()),True)
            self.assertEqual(self.extension_parameter._is_kv_equivalent(kek_urls[0].upper(),kek_urls[i]),True)

    def test_kv_equivalent_false(self):
        self.assertEqual(self.extension_parameter._is_kv_equivalent(None,"https://asdf"),False)
        self.assertEqual(self.extension_parameter._is_kv_equivalent("https://asdf",None),False)
        self.assertEqual(self.extension_parameter._is_kv_equivalent("https://old","https://new"),False)
        self.assertEqual(self.extension_parameter._is_kv_equivalent("https://old/","https://new/"),False)
