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
# Requires Python 2.4+
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
from azure.storage import BlobService

waagent=imp.load_source('waagent','/usr/sbin/waagent')
from waagent import LoggerInit

LoggerInit('/var/log/waagent.log','/dev/stdout')
waagent.Log("CustomScript handler starts.") 


#Global Variables definition
HandlerLogFile = "CustomScriptHandler.log"
StatusFileSuffix = ".status"
ConfigFileSuffix = ".settings"
DownloadDirectory = "download"
logfile=waagent.Log
hutil=imp.load_source('HandlerUtil','./resources/HandlerUtil.py')


def main():
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
    name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Uninstall')
    hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Install','Installed','0', 'Install Succeeded', 'NotReady','0',name+' Installed.')

def enable():
    try:
        name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Install')
        LoggerInit('/var/log/'+name+'_Install.log','/dev/stdout')
        # Ensure the same configuration is executed only once
        # If the previous enable failed, we do not have retry logic here. Since the custom script may not work in an intermediate state
        hutil.exit_if_enabled(seqNo)
        waagent.Log("set most recent sequence number to , " + seqNo + ", done. Start enabling.")        
        protected_settings = config['runtimeSettings'][0]['handlerSettings']['protectedSettings']
        public_settings = config['runtimeSettings'][0]['handlerSettings']['publicSettings']
        #get script in storage blob
        storage_account_name = protected_settings["storageAccountName"]
        storage_account_key = protected_settings["storageAccountKey"]
        blob_uris = public_settings['fileUris']
        hutil.doStatusReport(name,seqNo,version,status_file,'NotReady', '0', 'Downloading files...')
        for blob_uri in blob_uris:
            download_blob(storage_account_name, storage_account_key, blob_uri, seqNo)
        #execute the script
        cmd = public_settings['commandToExecute']
        waagent.Log("Command to execute:" + cmd)
        args = shlex.split(cmd)
        hutil.doStatusReport(name,seqNo,version,status_file,'NotReady', '0', 'Executing commands...')
        if len(blob_uris) > 0:
            download_dir = get_download_directory(seqNo)
            subprocess.Popen(args, cwd=download_dir)
        else:
            subprocess.Popen(args)
        #report the status
        hutil.doExit(name,seqNo,version,0,status_file,
                heartbeat_file,'Enable','Ready','0', 'Enable Succeeded.',
                'Ready','0',name+' Enable completed.')
    except Exception, e:
        waagent.Log("Failed to enable the extension with error:" + str(e))
        hutil.doExit(name,seqNo,version,1,status_file,
                heartbeat_file,'Enable','Error','0', 'Enable failed.',
                'NotReady','1',name+' enable failed.')
def uninstall():
    name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Uninstall')
    hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Uninstall','Uninstalled','0', 'Uninstall Succeeded', 'NotReady','0',name+' uninstalled.')

def disable():
    name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Disable')
    hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Disable','success','0', 'Disable service.py Succeeded', 'NotReady','0',name+' disabled.')

def update():
    name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Update')
    hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Update','transitioning','0', 'Updating', 'NotReady','0',name+' updating.')


def get_blob_name_from_uri(uri):
    return get_properties_from_uri(uri)['blob_name']

def get_container_name_from_uri(uri):
    return get_properties_from_uri(uri)['container_name']

def get_properties_from_uri(uri):
    if uri.endswith('/'):
        uri = uri[:-1]
    blob_name = uri[uri.rfind('/')+1:]
    uri = uri[:uri.rfind('/')]
    container_name = uri[uri.rfind('/')+1:]
    return {'blob_name': blob_name, 'container_name': container_name}
    
def download_blob(storage_account_name, storage_account_key, blob_uri, seqNo):
    container_name = get_container_name_from_uri(blob_uri)
    blob_name = get_blob_name_from_uri(blob_uri)
    download_dir = get_download_directory(seqNo)
    download_path = os.path.join(download_dir, blob_name)
    # Guest agent already ensure the plugin is enabled one after another. The blob download will not conflict.
    blob_service = BlobService(storage_account_name, storage_account_key)
    try:
        blob_service.get_blob_to_path(container_name, blob_name, download_path)
    except Exception, e:
        waagent.Log("Failed to download blob with uri:" + blob_uri + "with error:" + str(e))
        raise

def get_download_directory(seqNo):
    download_dir_main = os.path.join(os.getcwd(), 'download')
    create_directory_if_not_exists(download_dir_main)
    download_dir = os.path.join(download_dir_main, seqNo)
    print download_dir
    create_directory_if_not_exists(download_dir)
    return download_dir

def create_directory_if_not_exists(directory):
    """create directory if no exists"""
    if not os.path.exists(directory):
        os.makedirs(directory)

if __name__ == '__main__' :
    main()
