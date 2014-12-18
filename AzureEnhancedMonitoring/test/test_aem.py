#!/usr/bin/env python
#
#CustomScript extension
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
#
# Requires Python 2.6+
#

import unittest
import env
import os
import aem
import json

TestConfig="""{
        "vm.size" : "Small (A1)",
        "vm.roleinstance" : "haha",
        "vm.role" : "hehe",
        "vm.deploymentid" : "should-be-a-guid",
        "vm.memory.isovercommitted" : 1,
        "vm.cpu.isovercommitted" :  1,
        "script.version" : "1.0",
        "verbose" : 0,
        "osdisk.name" : "test-aem",
        "osdisk.connminute":"",
        "osdisk.connhour":"",
        "disk.count" : 2,
        "disk.lun.1" : 1,
        "disk.name.1" : "test-aem-dd1",
        "disk.connminute.1" : "",
        "disk.connhour.1" : "",
        "disk.lun.2" : 1,
        "disk.name.2" : "test-aem-dd2",
        "disk.connminute.2" : "",
        "disk.connhour.2" : "",
        "account.names" :["testaemstorage"],
        "testaemstorage.key" : "1sdf209unljnlfjahsdlfh===",
        "testaemstorage.hour.uri" : "http://foo.bar/",
        "testaemstorage.minute.uri" : "http://foo.bar/",
        "lad.isenable" : 1,
        "lad.key" : "23rsdf2fzcvf=+12",
        "lad.name" : "asdf",
        "lad.uri": "http://foo.bar/"
}
"""

class TestAEM(unittest.TestCase):
    def test_config(self):
        configData = json.loads(TestConfig)
        config = aem.EnhancedMonitorConfig(configData)
        self.assertNotEquals(None, config)
        return config

if __name__ == '__main__':
    unittest.main()
