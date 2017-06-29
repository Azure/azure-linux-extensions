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

    '''
        case1: if there is no status file        
        --> return
        
        case 2: if there is a status file, only if enable is success
                update status file
        case 3: enable re-runs again and again
                code should be idempotent
        
    
    #case 1update should work if there is no status file
    #         should return without executing
    '''
    
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
    
    def test_status_update(self):
        status_file = 'status/0.status'
        dsc.distro_category = dsc.get_distro_category()
        dsc.hutil = MockUtil(self)
        dsc.update_statusfile(status_file, '123','345')
        if os.path.exists(status_file):
            jsonData = open(status_file)
            status_data = json.load(jsonData)[0]
            self.assertTrue('status' in status_data, "status doesn't exists")
            substatusArray = status_data['status']['substatus']
            isMetaDataFound = False
            metasubstatus = None
            for substatusDict in substatusArray:
                if 'metadata' in  substatusDict.viewvalues():
                    isMetaDataFound = True
                    metasubstatus = substatusDict
            self.assertTrue(isMetaDataFound, "metadata doesn't exists")
            self.assertTrue('formatedMessage' in metasubstatus, "formatedMessage doesn't exists")
            formatedMessage = metasubstatus['formatedMessage']
            self.assertTrue('message' in formatedMessage, "message doesn't exists")
            self.assertTrue('AgentID' in formatedMessage['message'], "AgentID doesn't exists")

    def verify_nodeid(self, status_file):
        if os.path.exists(status_file):
            jsonData = open(status_file)
            status_data = json.load(jsonData)[0]
            self.assertTrue('status' in status_data, "status doesn't exists")
            substatusArray = status_data['status']['substatus']
            isMetaDataFound = False
            metasubstatus = None
            for substatusDict in substatusArray:
                if 'metadata' in  substatusDict.viewvalues():
                    isMetaDataFound = True
                    metasubstatus = substatusDict
            self.assertTrue(isMetaDataFound, "metadata doesn't exists")
            self.assertTrue('formatedMessage' in metasubstatus, "formatedMessage doesn't exists")
            formatedMessage = metasubstatus['formatedMessage']
            self.assertTrue('message' in formatedMessage, "message doesn't exists")
            self.assertTrue('AgentID' in formatedMessage['message'], "AgentID doesn't exists")
        
if __name__ == '__main__':
    unittest.main()
