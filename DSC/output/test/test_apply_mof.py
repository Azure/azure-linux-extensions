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
import platform
from Utils.WAAgentUtil import waagent
from MockUtil import MockUtil

waagent.LoggerInit('/tmp/test.log','/dev/null')

class TestApplyMof(unittest.TestCase):
    def test_apply_mof(self):
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = MockUtil(self)
        dsc.install_dsc_packages()
        dsc.start_omiservice()
        config = dsc.apply_dsc_meta_configuration('mof/dscnode.nxFile.meta.push.mof')
        dsc.apply_dsc_configuration('mof/localhost.nxFile.mof')
        self.assertTrue(os.path.exists('/tmp/dsctest'))
        
if __name__ == '__main__':
    unittest.main()
