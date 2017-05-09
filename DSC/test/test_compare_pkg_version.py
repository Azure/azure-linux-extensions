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

class Dummy(object):
    pass

class CompareRPMPackageVersions(unittest.TestCase):
    def test_with_equal_version(self):
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = Dummy()
        dsc.hutil.log = waagent.Log 
        output = dsc.compare_pkg_version('1.1.1.294', 1, 1, 1, 294)
        self.assertEqual(1, output)

    def test_with_higher_version(self):
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = Dummy()
        dsc.hutil.log = waagent.Log 
        output = dsc.compare_pkg_version('1.2.0.35', 1, 1, 1, 294)
        self.assertEqual(1, output)	

    def test_with_lower_version(self):
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = Dummy()
        dsc.hutil.log = waagent.Log 
        output = dsc.compare_pkg_version('1.0.4.35', 1, 1, 1, 294)
        self.assertEqual(0, output)			

if __name__ == '__main__':
    unittest.main()
