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
import xml.parsers.expat
from mounts import Mounts
from mounts import Mount
from fsfreezer import FsFreezer
from common import CommonVariables
from parameterparser import ParameterParser
from Utils import HandlerUtil

#Main function is the only entrence to this extension handler
def main():
    HandlerUtil.LoggerInit('/var/log/waagent.log','/dev/stdout')
    HandlerUtil.waagent.Log("%s started to handle." % (CommonVariables.extension_name)) 

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
    hutil = HandlerUtil.HandlerUtility(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)
    hutil.do_parse_context('Install')
    hutil.do_exit(0, 'Install','Installed','0', 'Install Succeeded')

def snapshot(sasuri):
    connection = httplib.HTTPSConnection('andliu.blob.core.windows.net')
    body_content = ''
    connection.request('PUT', '/extensions/VMBackupForLinux5-1.0.zip?sv=2014-02-14&sr=c&sig=wuoL15FvNEIWiimN9BMQNmDiqt36kuzKy1JIX0EaMYo%3D&st=2014-08-28T16%3A00%3A00Z&se=2014-09-05T16%3A00%3A00Z&sp=rwdl&comp=snapshot', body_content)
    result = connection.getresponse()
    connection.close()

def snapshotall(blobs):
    try:
        for blob in blobs:
            snapshot(blob)
        #connection =  httplib.HTTPSConnection('andliu.blob.core.windows.net')
        #body_content = ''
        #connection.request('PUT', '/extensions/VMBackupForLinux5-1.0.zip?sv=2014-02-14&sr=c&sig=wuoL15FvNEIWiimN9BMQNmDiqt36kuzKy1JIX0EaMYo%3D&st=2014-08-28T16%3A00%3A00Z&se=2014-09-05T16%3A00%3A00Z&sp=rwdl&comp=snapshot', body_content)
        #result = connection.getresponse()
        #print(result.read())
    except Exception, e:
        print(e)
    print('snapshotall')

#    Public Configuration Object:
#{
#TaskId:"<taskid>", // This will be a string identifying the backup job, this needs to be put as metadata on the blob snapshot. And will also be used while reporting status back as part of  the operation name.
#CommandToExecute:"<Backup >", // There can be multiple commands which the agent extn will need to support, for V1 only ¡°Backup¡± is the valid command.
#Locale:"en-us", ¡°// (Currently unused ¨C reserved for future) We will use it to format the localized status object, as localization is not supported by current azure extension infra, hence it is not be used for V1¡±
#SerObjStr:<Serialized object string> // (Currently unused ¨C reserved for future) This will be empty string for backup command, this object is meant to be passed unencrypted by the service, this object is contains a serialized xml containing the input for the command (it is not required for Backup.)
#}
 
#Private Configuration Object:
#{
#SerObjStrInput: //This is an encrypted string, post decryption by the agent, this contains the input xml for the command. For Backup command, the xml contains the list of Blob SAS Uri for the vm vhds to be snapshotted. The SAS Uri will be valid for 1 hr only. 
#LogsBlobUri: //This is an encrypted string, post decryption by the agent, this contains the blobSASUri for the blob which can be used for logging. It is assumed by the service that the blob contains a single text file which it reads and then copies the log into the service logs. The blob size is preset by the service as 10MB.
#}

def enable():
    hutil = HandlerUtil.HandlerUtility(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)
    
    freezer = FsFreezer()
    try:
        hutil.do_parse_context('Enable')
        # Ensure the same configuration is executed only once
        # If the previous enable failed, we do not have retry logic here.
        # Since the custom script may not work in an intermediate state
        hutil.exit_if_enabled()
        # we need to freeze the file system first
       
        hutil.log('starting to enable')
        """
        protectedSettings is the privateConfig passed from Powershell.
        """
        protected_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
        public_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('publicSettings')
        para_parser = ParameterParser(protected_settings, public_settings)

        commandToExecute = para_parser.commandToExecute
        taskId = public_settings.get('TaskId')
        if(commandToExecute.lower() == 'backup'):
            freezer.freezeall()
            snapshotall(para_parser.blobs)
            freezer.unfreezeall()
            hutil.do_exit(0, 'Enable', 'success','0', 'Enable Succeeded')
        else:
            hutil.do_exit(1, 'Enable', 'error', '1', 'Enable failed since the command to execute is not right.')

    except Exception, e:
        print(str(e))
        hutil.error("Failed to enable the extension with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable','error','1', 'Enable failed.')
    finally:
        freezer.unfreezeall()

def uninstall():
    hutil = HandlerUtil.HandlerUtility(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0,'Uninstall','success','0', 'Uninstall succeeded')

def disable():
    hutil = HandlerUtil.HandlerUtility(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)
    hutil.do_parse_context('Disable')
    hutil.do_exit(0,'Disable','success','0', 'Disable Succeeded')

def update():
    hutil = HandlerUtil.HandlerUtility(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)
    hutil.do_parse_context('Upadate')
    hutil.do_exit(0,'Update','success','0', 'Update Succeeded')

if __name__ == '__main__' :
    main()
