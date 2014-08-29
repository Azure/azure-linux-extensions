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
# Requires Python 2.7+
#


import array
import base64
import os
import os.path
import re
import string
import subprocess
import sys
import imp
import shlex
import traceback
import urllib2
import urlparse
from azure.storage import BlobService
from main.mounts import Mounts
from main.mounts import Mount
from main.fsfreezer import FsFreezer

#Main function is the only entrence to this extension handler
def main():
    global Common
    Common = imp.load_source('CommonVariables','./main/common.py')
    global Util
    Util = imp.load_source('HandlerUtil','./Utils/HandlerUtil.py')
    Util.LoggerInit('/var/log/waagent.log','/dev/stdout')
    Util.waagent.Log("%s started to handle." % (Common.CommonVariables.extension_name)) 

    for a in sys.argv[1:]:
        if re.match("^([-/]*)(disable)", a):
            disable()
        elif re.match("^([-/]*)(uninstall)", a):
            uninstall()
        elif re.match("^([-/]*)(install)", a):
            install()
        elif re.match("^([-/]*)(enable)", a):
            enable()
        elif re.match("^([-/]*)(update)", a):
            update()

def install():
    hutil = Util.HandlerUtility(Util.waagent.Log, Util.waagent.Error, Common.CommonVariables.extension_name)
    hutil.do_parse_context('Install')
    hutil.do_exit(0, 'Install','Installed','0', 'Install Succeeded')

def enable():
    hutil = Util.HandlerUtility(Util.waagent.Log, Util.waagent.Error, Common.CommonVariables.extension_name)
    try:
        hutil.do_parse_context('Enable')
        # Ensure the same configuration is executed only once
        # If the previous enable failed, we do not have retry logic here.
        # Since the custom script may not work in an intermediate state
        hutil.exit_if_enabled()
        # we need to freeze the file system first
       
        """
        protectedSettings is the privateConfig passed from Powershell.
        """
        protected_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
        public_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('publicSettings')

        storage_account_name = protected_settings.get("storageAccountName")
        storage_account_key = protected_settings.get("storageAccountKey")
        container_name = protected_settings.get("containerName")
        blob_name = protected_settings.get("blobName")

        freezer = FsFreezer()
        freezer.freezeall()
        bs = BlobService(storage_account_name, storage_account_key)
        bs.snapshot_blob(container_name, blob_name)
        freezer.unfreezeall()

    except Exception, e:
        hutil.error("Failed to enable the extension with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable','error','0', 'Enable failed.')

def uninstall():
    hutil = Util.HandlerUtility(Util.waagent.Log, Util.waagent.Error, Common.CommonVariables.extension_name)
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0,'Uninstall','success','0', 'Uninstall succeeded')

def disable():
    hutil = Util.HandlerUtility(Util.waagent.Log, Util.waagent.Error, Common.CommonVariables.extension_name)
    hutil.do_parse_context('Disable')
    hutil.do_exit(0,'Disable','success','0', 'Disable Succeeded')

def update():
    hutil = Util.HandlerUtility(Util.waagent.Log, Util.waagent.Error, Common.CommonVariables.extension_name)
    hutil.do_parse_context('Upadate')
    hutil.do_exit(0,'Update','success','0', 'Update Succeeded')

if __name__ == '__main__' :
    main()
