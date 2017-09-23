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
import json
from Utils.WAAgentUtil import waagent
from MockUtil import MockUtil

waagent.LoggerInit('/tmp/test.log','/dev/null')

class TestNodeExtensionProperties(unittest.TestCase):
    def test_properties_for_pull(self):
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = MockUtil(self)
        dsc.install_dsc_packages()
        dsc.start_omiservice()
        config = dsc.apply_dsc_meta_configuration('mof/dscnode.nxFile.meta.mof')
        self.assertTrue('ReturnValue=0' in config)
        
        content = dsc.construct_node_extension_properties(config)
        data = json.dumps(content)
        self.assertTrue('OMSCloudId' in data, "OMSCLoudID doesn't exist")
        
        
        #self.assertTrue('ExtHandlerVersion' in extensionInformation, "ExtHandlerVersion doesn't exist")
        
        #self.assertEqual('Microsoft.OSTCExtensions.DSCForLinux', extensionInformation['ExtHandlerName'])

    def test_send_request_to_pullserver(self):
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = MockUtil(self)
        dsc.install_dsc_packages()
        dsc.start_omiservice()
        config = dsc.apply_dsc_meta_configuration('mof/azureautomation.df.meta.mof')
        self.assertTrue('ReturnValue=0' in config)
        
        response  = dsc.send_heart_beat_msg_to_agent_service()
        self.assertEqual(response.status_code, 200)
  
    def test_push_request_properties(self):
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = MockUtil(self)
        dsc.install_dsc_packages()
        dsc.start_omiservice()
        config = dsc.apply_dsc_meta_configuration('mof/dscnode.nxFile.meta.push.mof')
        self.assertTrue('ReturnValue=0' in config)
        
        response  = dsc.send_heart_beat_msg_to_agent_service()
        self.assertIsNone(response)
       
if __name__ == '__main__':
    unittest.main()
