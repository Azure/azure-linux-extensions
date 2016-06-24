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

import unittest
import env
import vmaccess
import os
from Utils.WAAgentUtil import waagent
import shutil

waagent.LoggerInit('/tmp/test.log','/dev/stdout')
waagent.MyDistro = waagent.GetMyDistro()
class Dummy(object):
    pass

hutil = Dummy()
hutil.log = waagent.Log

class TestResetSshdConfig(unittest.TestCase):
    def test_reset_sshd_config(self):
        path = '/tmp/sshd_config'
        resources=os.path.join(env.root, 'resources')
        if(os.path.exists(path)):
            os.remove(path)
        if(os.path.isdir('resources')):
            shutil.rmtree('resources')
        shutil.copytree(resources, 'resources')
        vmaccess._reset_sshd_config(path)
        self.assertTrue(os.path.exists(path))
        config = waagent.GetFileContents(path)
        self.assertFalse(config.startswith("#Default sshd_config"))
        os.remove(path)

    def test_backup_sshd_config(self):
        test_dir = '/tmp/test_vmaccess'
        path = os.path.join(test_dir, "old_sshd_config")
        if(not os.path.isdir(test_dir)):
            os.mkdir(test_dir)
        if(not os.path.exists(path)):
            waagent.Run("echo > %s" %path)
        vmaccess._backup_sshd_config(path)
        os.remove(path)
        files = os.listdir(test_dir)
        self.assertNotEqual(len(files), 0)
        shutil.rmtree(test_dir)

if __name__ == '__main__':
    unittest.main()
