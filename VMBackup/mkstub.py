#!/usr/bin/env python
#
# VM Backup extension
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

import sys
import json
import os
import shutil
from main.common import CommonVariables

def copytree(src,dst):
    names = os.listdir(src)
    if(os.path.isdir(dst) != True):
        os.makedirs(dst)
    for name in names:
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        if os.path.isdir(srcname):
                copytree(srcname, dstname)
        else:
            # Will raise a SpecialFileError for unsupported file types
            shutil.copy2(srcname, dstname)

target_zip_file_location = './dist/'
target_folder_name = CommonVariables.extension_name + '-' + str(CommonVariables.extension_version)
target_zip_file_path = target_zip_file_location + target_folder_name + '.zip'


final_folder_path = target_zip_file_location + target_folder_name

copytree(final_folder_path, '/var/lib/waagent/' + target_folder_name)

"""
we should also build up a HandlerEnvironment.json
"""
manifest_obj = [{
  "name": CommonVariables.extension_name,
  "seqNo": "1", 
  "version": 1.0,
    "handlerEnvironment": {    
        "logFolder": "/var/log/azure/" + CommonVariables.extension_name + "/" + str(CommonVariables.extension_version),
        "configFolder": "/var/lib/waagent/" + CommonVariables.extension_name + "-" + str(CommonVariables.extension_version) + "/config",
        "statusFolder": "/var/lib/waagent/" + CommonVariables.extension_name + "-" + str(CommonVariables.extension_version) + "/status",
        "heartbeatFile": "/var/lib/waagent/" + CommonVariables.extension_name + "-" + str(CommonVariables.extension_version) + "/heartbeat.log"
    }
}]

manifest_str = json.dumps(manifest_obj, sort_keys = True, indent = 4)
manifest_file = open('/var/lib/waagent/' + target_folder_name + "/HandlerEnvironment.json", "w") 
manifest_file.write(manifest_str)
manifest_file.close()
