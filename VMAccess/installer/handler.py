#!/usr/bin/env python
#
# VMAccess extension
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


import os
import sys
import imp
import base64
import re
import json

# Global variables definition
# waagent has no '.py' therefore create waagent module import manually.
waagent=imp.load_source('waagent','/usr/sbin/waagent')
HandlerUtil=imp.load_source('HandlerUtil','./resources/HandlerUtil.py')
from waagent import LoggerInit

LoggerInit('/var/log/waagent.log','/dev/stdout')
waagent.Log("VMAccess handler starts.")
logfile=waagent.Log
BeginCertificateTag = '-----BEGIN CERTIFICATE-----'
EndCertificateTag = '-----END CERTIFICATE-----'
OutputSplitter = ';'


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
    HandlerUtil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Install','Installed','0', 'Install Succeeded', 'NotReady','0',name+' Installed.')


def enable():
    name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=HandlerUtil.doParse(logfile,'Install')
    LoggerInit('/var/log/'+name+'_Install.log','/dev/stdout')
    waagent.Log(name+" - install.py starting.")
    waagent.Log('name:' + name + ';seqNo:' + seqNo + ';version:' + version
            + ';config_dir:' + config_dir + ';log_dir' + log_dir)
    HandlerUtil.exit_if_enabled(seqNo)
    protect_settings = config['runtimeSettings'][0]['handlerSettings']['protectedSettings']
    pub_settings = config['runtimeSettings'][0]['handlerSettings']['publicSettings']
    waagent.MyDistro = waagent.GetMyDistro()
    output_msg = ''
    # if user name is specified in settings, set the user name and password
    if pub_settings.has_key('UserName'):
        user_name = pub_settings['UserName']
        user_pass = None
        if protect_settings.has_key('Password'):
            user_pass = protect_settings['Password']
        expire_date = None
        if pub_settings.has_key('Expiration'):
            expire_date = pub_settings['Expiration']
        error_string= waagent.MyDistro.CreateAccount(user_name,user_pass, expire_date, None)
        if error_string != None:
            temp_output = "VMAccess failed to create the account or set the password: " + error_string
            waagent.Error(temp_output)
            output_msg += temp_output + OutputSplitter
        else:
            temp_output = "VMAccess succeeded in creating the account or set the password for " + user_name 
            waagent.Log(temp_output)
            output_msg += temp_output + OutputSplitter

    # if certificate is specified in settings, set the new host public key
    cert_txt = None
    if(protect_settings.has_key('Certificate')):
        cert_txt = protect_settings['Certificate']
        # save the certificate string as a crt file
        cert_txt = cert_txt.replace(BeginCertificateTag, '').replace(EndCertificateTag,'').replace(' ', '\n')
        cert_txt = BeginCertificateTag + cert_txt + EndCertificateTag + '\n'
        waagent.SetFileContents('temp.crt', cert_txt)
    # if neither cert text nor user name is specified, reset the ssh pub key
    reset_host_key = None
    if pub_settings.has_key('ResetHostKey'):
        reset_host_key = pub_settings['ResetHostKey']
    if cert_txt or ( reset_host_key and reset_host_key.lower() == 'true') :
        # get the path to store the public key
        ovf_xml = waagent.GetFileContents('/var/lib/waagent/ovf-env.xml')
        if ovf_xml:
            ovf_env = waagent.OvfEnv().Parse(ovf_xml)
            ssh_user_name = ovf_env.UserName
            if(user_name):
                ssh_user_name = user_name
                # ovf_env.UserName will be used when invoke ovf_env.PrepareDir
                ovf_env.UserName = user_name
            pub_path = None
            for pkey in ovf_env.SshPublicKeys:
                if pkey[1]:
                    pub_path = pkey[1]
                    pub_path = re.sub(r'^/home/\w+/','/home/'+ssh_user_name+'/', pub_path)
                    waagent.Log('public key path: ' + pub_path)
                    if not cert_txt:
                        waagent.Run('mv ' + pkey[0] + '.crt ./temp.crt')
                    break
            pub_path = ovf_env.PrepareDir(pub_path)
            if pub_path == None:
                temp_output = "VMAccess failed to set public key as the public key path is invalid:" + pub_path
                waagent.Error(temp_output)
                output_msg += temp_output + OutputSplitter
            else:
                waagent.Run(waagent.Openssl + " x509 -in temp.crt -noout -pubkey > temp.pub")
                waagent.MyDistro.setSelinuxContext('temp.pub','unconfined_u:object_r:ssh_home_t:s0')
                waagent.MyDistro.sshDeployPublicKey('temp.pub',pub_path)
                waagent.MyDistro.setSelinuxContext(pub_path,'unconfined_u:object_r:ssh_home_t:s0')
                waagent.Log("VMAccess succeeded in configuring the SSH public key.")
                waagent.ChangeOwner(pub_path, ssh_user_name)
                temp_output = "VMAccess succeeded in setting public key for user: " + ssh_user_name
                waagent.Log(temp_output)
                output_msg += temp_output + OutputSplitter
    open_ssh_port = None
    if pub_settings.has_key('OpenSshPort'):
        open_ssh_port = pub_settings['OpenSshPort']
    if open_ssh_port and open_ssh_port.lower() == 'true':
        waagent.Run("iptables -t filter -I INPUT -p tcp --dport 22 -j ACCEPT")
        waagent.Log("VMAccess succeeded in opening ssh port.")
    # TODO: Reset the sshd config and restart ssh service.
    HandlerUtil.doExit(name,seqNo,version,0,status_file,
            heartbeat_file,'Enable','Ready','0', 'Enable Succeeded.',
            'Ready','0',name+' Enable completed.')
    
def uninstall():
    name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Uninstall')
    HandlerUtil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Uninstall','Uninstalled','0', 'Uninstall Succeeded', 'NotReady','0',name+' uninstalled.')

def disable():
    name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Disable')
    HandlerUtil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Disable','success','0', 'Disable service.py Succeeded', 'NotReady','0',name+' disabled.')

def update():
    name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Update')
    HandlerUtil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Update','transitioning','0', 'Updating', 'NotReady','0',name+' updating.')

if __name__ == '__main__' :
    main()

