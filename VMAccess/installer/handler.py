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
Util=imp.load_source('HandlerUtil','./resources/HandlerUtil.py')
from waagent import LoggerInit

LoggerInit('/var/log/waagent.log','/dev/stdout')
ExtensionShortName = 'VMAccess'
waagent.Log("%s started to handle." %(ExtensionShortName)) 
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
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0,'Install','Installed','0', 'Install Succeeded')

def enable():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context('Install')
    hutil.exit_if_enabled()
    protect_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
    pub_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('publicSettings')
    waagent.MyDistro = waagent.GetMyDistro()
    output_msg = ''
    # Set the user name and password, if user name is specified in settings
    if pub_settings and pub_settings.has_key('UserName'):
        user_name = pub_settings['UserName']
        user_pass = protect_settings.get('Password')
        expire_date = pub_settings.get('Expiration')
        error_string= waagent.MyDistro.CreateAccount(user_name,user_pass, expire_date, None)
        if error_string != None:
            temp_output = "VMAccess failed to create the account or set the password: " + error_string
            hutil.error(temp_output)
            output_msg += temp_output + OutputSplitter
        else:
            temp_output = "VMAccess succeeded in creating the account or set the password for " + user_name 
            hutil.log(temp_output)
            output_msg += temp_output + OutputSplitter

    # if certificate is specified in settings, set the new host public key
    cert_txt = protect_settings.get('Certificate')
    if not (cert_txt == None):
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
                    hutil.log('public key path: ' + pub_path)
                    if not cert_txt:
                        waagent.Run('mv ' + pkey[0] + '.crt ./temp.crt')
                    break
            pub_path = ovf_env.PrepareDir(pub_path)
            if pub_path == None:
                temp_output = "VMAccess failed to set public key as the public key path is invalid:" + pub_path
                hutil.error(temp_output)
                output_msg += temp_output + OutputSplitter
            else:
                waagent.Run(waagent.Openssl + " x509 -in temp.crt -noout -pubkey > temp.pub")
                waagent.MyDistro.setSelinuxContext('temp.pub','unconfined_u:object_r:ssh_home_t:s0')
                waagent.MyDistro.sshDeployPublicKey('temp.pub',pub_path)
                waagent.MyDistro.setSelinuxContext(pub_path,'unconfined_u:object_r:ssh_home_t:s0')
                hutil.log("VMAccess succeeded in configuring the SSH public key.")
                waagent.ChangeOwner(pub_path, ssh_user_name)
                temp_output = "VMAccess succeeded in setting public key for user: " + ssh_user_name
                hutil.log(temp_output)
                output_msg += temp_output + OutputSplitter

    open_ssh_port = pub_settings.get('OpenSshPort')
    if open_ssh_port and open_ssh_port.lower() == 'true':
        waagent.Run("iptables -t filter -I INPUT -p tcp --dport 22 -j ACCEPT")
        hutil.log("VMAccess succeeded in opening ssh port.")
    # TODO: Reset the sshd config and restart ssh service.
    hutil.do_exit(0, 'Enable', 'success','0', output_msg)
    
def uninstall():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0,'Uninstall','success','0', 'Uninstall succeeded')

def disable():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context('Disable')
    hutil.do_exit(0,'Disable','success','0', 'Disable Succeeded')

def update():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context('Upadate')
    hutil.do_exit(0,'Update','success','0', 'Update Succeeded')

if __name__ == '__main__' :
    main()

