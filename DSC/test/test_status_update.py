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

class TestStatusUpdate(unittest.TestCase):

    def verify_nodeid_vmuuid(self, status_file):
        self.assertTrue(os.path.exists(status_file), "file exists")
        if os.path.exists(status_file):
            jsonData = open(status_file)
            status_data = json.load(jsonData)[0]
            self.assertTrue('status' in status_data, "status doesn't exists")
            substatusArray = status_data['status']['substatus']
            isMetaDataFound = False
            metasubstatus = None
            if 'metadata' in  substatusArray[0].viewvalues():
                metasubstatus = substatusArray[0]
            self.assertTrue('formatedMessage' in metasubstatus, "formatedMessage doesn't exists")
            formatedMessage = metasubstatus['formatedMessage']
            self.assertTrue('message' in formatedMessage, "message doesn't exists")
            self.assertTrue('AgentID' in formatedMessage['message'], "AgentID doesn't exists")
            
    def test_vmuuid(self):
        dsc.hutil = MockUtil(self)
        vmuuid = dsc.get_vmuuid()
        self.assertTrue(vmuuid is not None, "vm uuid is none")
    
    def test_nodeid_with_dsc(self):
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = MockUtil(self)
        dsc.install_dsc_packages()
        dsc.start_omiservice()
        config = dsc.apply_dsc_meta_configuration('mof/dscnode.nxFile.meta.push.mof')
        nodeid = dsc.get_nodeid('/etc/opt/omi/conf/omsconfig/agentid')
        self.assertTrue(nodeid is not None, "nodeid is none")

    def test_nodeid_without_dsc(self):
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = MockUtil(self)
        nodeid = dsc.get_nodeid('/etc/opt/omi/conf/omsconfig/agentid1')
        self.assertTrue(nodeid is None, "nodeid is not none")
    
    def test_statusfile_update(self):
        status_file = 'status/0.status'
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = MockUtil(self)
        dsc.update_statusfile(status_file, '123','345')
        self.verify_nodeid_vmuuid(status_file)
        
    def test_is_statusfile_update_idempotent(self):
        status_file = 'status/0.status'
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = MockUtil(self)
        dsc.update_statusfile(status_file, '123','345')
        dsc.update_statusfile(status_file, '123','345')
        self.verify_nodeid_vmuuid(status_file)

    def test_is_statusfile_update_register(self):
        status_file = 'status/0.status'
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = MockUtil(self)
        dsc.install_dsc_packages()
        dsc.start_omiservice()
        exit_code, output = dsc.register_automation('somekey','http://dummy','','','','')
        self.verify_nodeid_vmuuid(status_file)

    def test_is_statusfile_update_pull(self):
        status_file = 'status/0.status'
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = MockUtil(self)
        dsc.install_dsc_packages()
        dsc.start_omiservice()
        config = dsc.apply_dsc_meta_configuration('mof/dscnode.nxFile.meta.mof')
        self.assertTrue('ReturnValue=0' in config)
        self.verify_nodeid_vmuuid(status_file)

    def test_is_statusfile_update_push(self):
        status_file = 'status/0.status'
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = MockUtil(self)
        dsc.install_dsc_packages()
        dsc.start_omiservice()
        config = dsc.apply_dsc_meta_configuration('mof/dscnode.nxFile.meta.push.mof')
        dsc.apply_dsc_configuration('mof/localhost.nxFile.mof')
        self.assertTrue(os.path.exists('/tmp/dsctest'))
        self.verify_nodeid_vmuuid(status_file)

        
if __name__ == '__main__':
    unittest.main()
