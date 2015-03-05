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
import httplib
from common import CommonVariables
from parameterparser import ParameterParser
from Utils import HandlerUtil
from encryption import *

#Main function is the only entrence to this extension handler
def main():
    global hutil
    HandlerUtil.LoggerInit('/var/log/waagent.log','/dev/stdout')
    HandlerUtil.waagent.Log("%s started to handle." % (CommonVariables.extension_name)) 
    hutil = HandlerUtil.HandlerUtility(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)

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
    hutil.do_parse_context('Install')
    hutil.do_exit(0, 'Install','Installed','0', 'Install Succeeded')

def enable():
    try:
        hutil.do_parse_context('Enable')
        # Ensure the same configuration is executed only once
        # If the previous enable failed, we do not have retry logic here.
        hutil.exit_if_enabled()

        """
        protectedSettings is the privateConfig passed from Powershell.
        """
        protected_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
        public_settings    = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('publicSettings')

        para_parser = ParameterParser(protected_settings, public_settings)
        para_validate_result = para_parser.validate()
        if(para_validate_result != 0):
            pass

        MyPatching = GetMyPatching()
        if MyPatching == None:
            hutil.do_exit(0,'Enable','error',str(CommonVariables.os_not_supported),'the os is not supported')
        else:
            MyPatching.install_extras(para_parser)

        if(para_parser.query is None):
            hutil.do_exit(0,'Enable','error','3','you should specify the device query')
        else:
            if(para_parser.query.has_key("path")):
                para_parser.path = para_parser.query["path"]
            else:
                #scsi_host,channel,target_number,LUN
                p = subprocess.Popen(['lsscsi', para_parser.query["scsi_number"]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                identity, err = p.communicate()
                if(identity is None or identity.strip() == ""):
                    hutil.do_exit(0,'Enable','error','2','the scsi_number not found')
                vals = identity.split()
                para_parser.path = vals[len(vals) - 1]

        if(para_parser.mountname is None or para_parser.mountname == ""):
            para_parser.mountname = "encrypted"
            path = os.path.join(para_parser.mountpoint, para_parser.mountname)
            finalpath = path
            i = 0
            while(os.path.exists(finalpath) or os.path.exists("/dev/mapper/" + para_parser.mountname)):
                print("finalpath==" + finalpath)
                i+=1
                finalpath = path + str(i)
                para_parser.mountname = "encrypted" + str(i)

        if(para_parser.filesystem is None or para_parser.filesystem == ""):
            para_parser.filesystem = "ext4"

        encryption = Encryption(para_parser)
        encryption_result = encryption.encrypt()
        hutil.do_exit(0, 'Enable', encryption_result.state,str(encryption_result.code), encryption_result.info)

    except Exception, e:
        print(str(e))
        hutil.error("Failed to enable the extension with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable','error','1', 'Enable failed.')
    finally:
        pass

def uninstall():
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0,'Uninstall','success','0', 'Uninstall succeeded')

def disable():
    hutil.do_parse_context('Disable')
    hutil.do_exit(0,'Disable','success','0', 'Disable Succeeded')

def update():
    hutil.do_parse_context('Upadate')
    hutil.do_exit(0,'Update','success','0', 'Update Succeeded')

if __name__ == '__main__' :
    main()
