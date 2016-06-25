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

waagent.LoggerInit('/tmp/test.log','/dev/null')

class TestIPhablesRule(unittest.TestCase):
    def test_insert_rule_if_not_exists(self):
        rule = 'INPUT -p tcp -m tcp --dport 9998 -j DROP'
        vmaccess._insert_rule_if_not_exists(rule)
        cmd_result = waagent.RunGetOutput("iptables-save | grep '%s'" %rule)
        self.assertEqual(cmd_result[0], 0)
        waagent.Run("iptables -D %s" %rule)

    def test_del_rule_if_exists(self):
        rule = 'INPUT -p tcp -m tcp --dport 9998 -j DROP'
        waagent.Run("iptables -I %s" %rule)
        vmaccess._del_rule_if_exists(rule)
        cmd_result = waagent.RunGetOutput("iptables-save | grep '%s'" %rule)
        self.assertNotEqual(cmd_result[0], 0)
        
if __name__ == '__main__':
    unittest.main()
