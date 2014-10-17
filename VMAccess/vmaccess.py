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
    waagent.MyDistro = waagent.GetMyDistro()

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
            _reset_sshd_config("/etc/ssh/sshd_config")
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
    ovf_xml = waagent.GetFileContents('/var/lib/waagent/ovf-env.xml')
    ovf_env = waagent.OvfEnv().Parse(ovf_xml)

    # user name must be provided if set ssh key or password
    if not protect_settings and protect_settings.has_key('username'):
        raise Exception("No user name is specified")
    
    user_name = protect_settings['username']
    user_pass = protect_settings.get('password')
    cert_txt = protect_settings.get('ssh_key')
    
    if(not(user_pass) and not(cert_txt) and not(ovf_env.SshPublicKeys)):
        raise Exception("No password or ssh_key is specified.")

    #Reset user account and password, password could be empty
    error_string= waagent.MyDistro.CreateAccount(user_name, user_pass, None, None)
    if error_string != None:
        raise Exception("Failed to create the account or set the password: " + error_string)
    hutil.log("Succeeded in create the account or set the password.")

    #Reset ssh key with the new public key passed in or reuse old public key.
    if cert_txt or len(ovf_env.SshPublicKeys) > 0:
        pub_path = os.path.join('/home/', user_name, '.ssh','authorized_keys')
        ovf_env.UserName = user_name
        if cert_txt:
            _save_cert_str_as_file(cert_txt, 'temp.crt')
        else :
            for pkey in ovf_env.SshPublicKeys:
                if pkey[1]:
                    shutil.copy(os.path.join(waagent.LibDir, pkey[0] + '.crt'), os.path.join(os.getcwd(),'temp.crt'))
                    break
        pub_path = ovf_env.PrepareDir(pub_path)
        retcode = waagent.Run(waagent.Openssl + " x509 -in temp.crt -noout -pubkey > temp.pub")
        if retcode > 0:
            raise Exception("Failed to generate public key file.")
        waagent.MyDistro.sshDeployPublicKey('temp.pub',pub_path)
        waagent.MyDistro.setSelinuxContext(pub_path,'unconfined_u:object_r:ssh_home_t:s0')
        waagent.ChangeOwner(pub_path, user_name)
        os.remove('temp.pub')
        os.remove('temp.crt')
        hutil.log("Succeeded in resetting ssh_key.")

def _reset_sshd_config(sshd_file_path):
    distro = platform.dist()
    distro_name = distro[0]
    version = distro[1]
    config_file_path = os.path.join(os.getcwd(), 'resources', '%s_%s' %(distro_name,version))
    if not(os.path.exists(config_file_path)):
        config_file_path = os.path.join(os.getcwd(), 'resources', '%s_%s' %(distro_name,'default'))
        if not(os.path.exists(config_file_path)):
            config_file_path = os.path.join(os.getcwd(), 'resources', 'default')
    _backup_sshd_config(sshd_file_path)
    
    if distro_name == "CoreOS":
        # Parse sshd port from config_file_path
        sshd_port = 22        
        regex = re.compile(r"^Port\s+(\d+)", re.VERBOSE)
        with open(config_file_path) as f:
            for line in f:
                match = regex.match(line)
                if match:
                    sshd_port = match.group(1)
                    break                
        
        # Prepare cloud init config for coreos-cloudinit
        cfg_tempfile = "/tmp/cloudinit.cfg"
        cfg_content = "#cloud-config\n\n"
        
        # Overwrite /etc/ssh/sshd_config
        cfg_content += "write_files:\n"
        cfg_content += "  - path: {0}\n".format(sshd_file_path)
        cfg_content += "    permissions: 0600\n"
        cfg_content += "    owner: root:root\n"
        cfg_content += "    content: |\n"
        for line in GetFileContents(config_file_path).split('\n'):
            cfg_content += "      {0}\n".format(line)
        
        # Change the sshd port in /etc/systemd/system/sshd.socket
        cfg_content += "\ncoreos:\n"
        cfg_content += "  units:\n"
        cfg_content += "  - name: sshd.socket\n"
        cfg_content += "    command: restart\n"
        cfg_content += "    content: |\n"
        cfg_content += "      [Socket]\n"
        cfg_content += "      ListenStream={0}\n".format(sshd_port)
        cfg_content += "      Accept=yes\n"
        
        SetFileContents(cfg_tempfile, cfg_content)
        
        Run("coreos-cloudinit -from-file " + cfg_tempfile, chk_err=False)
        os.remove(cfg_tempfile)
    else:
        shutil.copyfile(config_file_path, sshd_file_path)
        waagent.MyDistro.restartSshService()

def _backup_sshd_config(sshd_file_path):
    if(os.path.exists(sshd_file_path)):
        backup_file_name = '%s_%s' %(sshd_file_path, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        shutil.copyfile(sshd_file_path, backup_file_name)

def _save_cert_str_as_file(cert_txt, file_name):
    cert_start = cert_txt.index(BeginCertificateTag)
    if(cert_txt >= 0):
        cert_txt = cert_txt[cert_start + len(BeginCertificateTag):]
    cert_end =  cert_txt.index(EndCertificateTag)
    if(cert_end >= 0):
        cert_txt = cert_txt[:cert_end]
    cert_txt = cert_txt.strip()
    cert_txt = "{0}\n{1}\n{2}\n".format(BeginCertificateTag, cert_txt, EndCertificateTag)
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
    if cmd_result[0] == 0 and (rule_string not in cmd_result[1]):
        waagent.Run("iptables -I %s" %rule_string)


if __name__ == '__main__' :
    main()

