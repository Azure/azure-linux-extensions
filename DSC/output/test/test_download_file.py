#!/usr/bin/env python
#
# DSC Extension For Linux
#
# Copyright 2014 Microsoft Corporation
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

import unittest
import env
import dsc
import os
from Utils.WAAgentUtil import waagent
from MockUtil import MockUtil

waagent.LoggerInit('/tmp/test.log','/dev/null')

class TestDownloadFile(unittest.TestCase):
    def test_download_file(self):
        dsc.hutil = MockUtil(self)	
        dsc.download_external_file('https://raw.githubusercontent.com/balukambala/azure-linux-extensions/master/DSC/test/mof/dscnode.nxFile.meta.mof', '/tmp')
        
if __name__ == '__main__':
    unittest.main()
