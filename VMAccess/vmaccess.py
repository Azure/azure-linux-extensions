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
# Requires Python 2.7+


import os
import sys
import imp
import base64
import re
import json
import platform
import shutil
import time
import traceback

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

#Define global variables
ExtensionShortName = 'VMAccess'
BeginCertificateTag = '-----BEGIN CERTIFICATE-----'
EndCertificateTag = '-----END CERTIFICATE-----'
OutputSplitter = ';'

def main():
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
    waagent.Log("%s started to handle." %(ExtensionShortName)) 

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
    hutil.do_parse_context('Enable')
    try:
        protect_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
        reset_ssh = protect_settings.get('reset_ssh')
        # check port each time the VM boots up
        if reset_ssh:
            _open_ssh_port()
            hutil.log("Succeeded in check and open ssh port.")
        hutil.exit_if_enabled()
        _set_user_account_pub_key(protect_settings, hutil)
        if reset_ssh:
            _reset_sshd_config()
            hutil.log("Succeeded in reset sshd_config.")
        hutil.do_exit(0, 'Enable', 'success','0', 'Enable succeeded.')
    except Exception, e:
        hutil.error("Failed to enable the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable','error','0', 'Enable failed.')

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
    
def _set_user_account_pub_key(protect_settings, hutil):
    waagent.MyDistro = waagent.GetMyDistro()
    ovf_xml = waagent.GetFileContents('/var/lib/waagent/ovf-env.xml')
    ovf_env = waagent.OvfEnv().Parse(ovf_xml)
    # user name must be provided if set ssh key or password
    if protect_settings and protect_settings.has_key('username'):
        user_name = protect_settings['username']
        user_pass = protect_settings.get('password')
        cert_txt = protect_settings.get('ssh_key')
        if user_pass or cert_txt or len(ovf_env.SshPublicKeys) > 0:
            error_string= waagent.MyDistro.CreateAccount(user_name,user_pass,None, None)
            if error_string != None:
                raise Exception("Failed to create the account or set the password: " + error_string)
            hutil.log("Succeeded in create the account or set the password.")
            if cert_txt or not(user_pass) and len(ovf_env.SshPublicKeys)> 0:
                pub_path = os.path.join('/home/', user_name, '.ssh','authorized_keys')
                ovf_env.UserName = user_name
                if cert_txt:
                    _save_cert_str_as_file(cert_txt, 'temp.crt')
                else :
                    for pkey in ovf_env.SshPublicKeys:
                        if pkey[1]:
                            os.rename(pkey[0] + '.crt', os.path.join(os.getcwd(),'temp.crt'))
                            break
                pub_path = ovf_env.PrepareDir(pub_path)
                retcode = waagent.Run(waagent.Openssl + " x509 -in temp.crt -noout -pubkey > temp.pub")
                if retcode > 0:
                    raise Exception("Failed to generate public key file.")
                waagent.MyDistro.setSelinuxContext('temp.pub','unconfined_u:object_r:ssh_home_t:s0')
                waagent.MyDistro.sshDeployPublicKey('temp.pub',pub_path)
                waagent.MyDistro.setSelinuxContext(pub_path,'unconfined_u:object_r:ssh_home_t:s0')
                waagent.ChangeOwner(pub_path, user_name)

def _reset_sshd_config():
    distro = platform.dist()
    distro_name = distro[0]
    version = distro[1]
    sshd_file_path = "/etc/ssh/sshd_config"
    config_file_path = os.path.join(os.getcwd(), 'resources', '%s_%s' %(distro_name,version))
    if not(os.path.exists(config_file_path)):
        config_file_path = os.path.join(os.getcwd(), 'resources', '%s_%s' %(distro_name,'default'))
        if not(os.path.exists(config_file_path)):
            config_file_path = os.path.join(os.getcwd(), 'resources', 'default')
    _backup_sshd_config(sshd_file_path)
    shutil.copyfile(config_file_path, sshd_file_path)
    waagent.MyDistro.restartSshService()

def _backup_sshd_config(sshd_file_path):
    backup_file_name = '%s_%s' %(sshd_file_path, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    shutil.copyfile(sshd_file_path, backup_file_name)

def _save_cert_str_as_file(cert_txt, file_name):
    cert_txt = cert_txt.replace(BeginCertificateTag, '').replace(EndCertificateTag,'').replace(' ', '\n')
    cert_txt = BeginCertificateTag + cert_txt + EndCertificateTag + '\n'
    waagent.SetFileContents(file_name, cert_txt)

def _open_ssh_port():
    _del_rule_if_exists('INPUT -p tcp -m tcp --dport 22 -j DROP')
    _del_rule_if_exists('INPUT -p tcp -m tcp --dport 22 -j REJECT')
    _del_rule_if_exists('INPUT -p -j DROP')
    _del_rule_if_exists('INPUT -p -j REJECT')
    _insert_rule_if_not_exists('INPUT -p tcp -m tcp --dport 22 -j ACCEPT')

    _del_rule_if_exists('OUTPUT -p tcp -m tcp --sport 22 -j DROP')
    _del_rule_if_exists('OUTPUT -p tcp -m tcp --sport 22 -j REJECT')
    _del_rule_if_exists('OUTPUT -p -j DROP')
    _del_rule_if_exists('OUTPUT -p -j REJECT')
    _insert_rule_if_not_exists('OUTPUT -p tcp -m tcp --dport 22 -j ACCEPT')

def _del_rule_if_exists(rule_string):
    match_string = '-A %s' %rule_string
    cmd_result = waagent.RunGetOutput("iptables-save")
    while cmd_result[0] == 0 and (rule_string in cmd_result[1]):
        waagent.Run("iptables -D %s" %rule_string)
        cmd_result = waagent.RunGetOutput("iptables-save")

def _insert_rule_if_not_exists(rule_string):
    match_string = '-A %s' %rule_string
    cmd_result = waagent.RunGetOutput("iptables-save")
    if cmd_result[0] == 0 and (rule_string in cmd_result[1]):
        waagent.Run("iptables -I %s" %rule_string)


if __name__ == '__main__' :
    main()

