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

import os
import platform
import re
import shutil
import sys
import time
import traceback

import Utils.HandlerUtil as Util
from waagentloader import load_waagent

waagent = load_waagent()

# Define global variables
ExtensionShortName = 'VMAccess'
BeginCertificateTag = '-----BEGIN CERTIFICATE-----'
EndCertificateTag = '-----END CERTIFICATE-----'
OutputSplitter = ';'


def main():
    waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
    waagent.Log("%s started to handle." % (ExtensionShortName))
    waagent.MyDistro = waagent.GetMyDistro()

    try:
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
    except Exception as e:
        err_msg = "Failed with error: {0}, {1}".format(e, traceback.format_exc())
        waagent.Error(err_msg)


def install():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0, 'Install', 'Installed', '0', 'Install Succeeded')


def enable():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    hutil.do_parse_context('Enable')
    try:
        reset_ssh = None
        remove_user = None
        protect_settings = hutil.get_protected_settings()
        if protect_settings:
            reset_ssh = protect_settings.get('reset_ssh')
            remove_user = protect_settings.get('remove_user')

        # check port each time the VM boots up
        if reset_ssh:
            _open_ssh_port()
            hutil.log("Succeeded in check and open ssh port.")

        hutil.exit_if_enabled()

        if reset_ssh:
            _reset_sshd_config("/etc/ssh/sshd_config")
            hutil.log("Succeeded in reset sshd_config.")
        if remove_user:
            _remove_user_account(remove_user, hutil)
        _set_user_account_pub_key(protect_settings, hutil)

        check_and_repair_disk(hutil)

        hutil.do_exit(0, 'Enable', 'success', '0', 'Enable succeeded.')
    except Exception as e:
        hutil.error(("Failed to enable the extension with error: {0}, "
            "stack trace: {1}").format(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable', 'error', '0', 'Enable failed.')


def uninstall():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0, 'Uninstall', 'success', '0', 'Uninstall succeeded')


def disable():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    hutil.do_parse_context('Disable')
    hutil.do_exit(0, 'Disable', 'success', '0', 'Disable Succeeded')


def update():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    hutil.do_parse_context('Upadate')
    hutil.do_exit(0, 'Update', 'success', '0', 'Update Succeeded')


def _remove_user_account(user_name, hutil):
    try:
        sudoers = _get_other_sudoers(user_name)
        waagent.MyDistro.DeleteAccount(user_name)
        _save_other_sudoers(sudoers)
    except Exception as e:
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=waagent.WALAEventOperation.Enable,
                                  isSuccess=False,
                                  message="(02102)Failed to remove user.")
        raise Exception("Failed to remove user {0}".format(e))


def _set_user_account_pub_key(protect_settings, hutil):
    ovf_xml = waagent.GetFileContents('/var/lib/waagent/ovf-env.xml')
    ovf_env = waagent.OvfEnv().Parse(ovf_xml)

    # user name must be provided if set ssh key or password
    if not protect_settings or not protect_settings.has_key('username'):
        return

    user_name = protect_settings['username']
    user_pass = protect_settings.get('password')
    cert_txt = protect_settings.get('ssh_key')
    no_convert = False
    if(not(user_pass) and not(cert_txt) and not(ovf_env.SshPublicKeys)):
        raise Exception("No password or ssh_key is specified.")

    # Reset user account and password, password could be empty
    sudoers = _get_other_sudoers(user_name)
    error_string = waagent.MyDistro.CreateAccount(
        user_name, user_pass, None, None)
    _save_other_sudoers(sudoers)

    if error_string != None:
        err_msg = "Failed to create the account or set the password"
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=waagent.WALAEventOperation.Enable,
                                  isSuccess=False,
                                  message="(02101)" + err_msg)
        raise Exception(err_msg + " with " + error_string)
    hutil.log("Succeeded in create the account or set the password.")

    # Allow password authentication if user_pass is provided
    if user_pass is not None:
        _allow_password_auth()

    # Reset ssh key with the new public key passed in or reuse old public key.
    if cert_txt or len(ovf_env.SshPublicKeys) > 0:
        if cert_txt and cert_txt.strip().lower().startswith("ssh-rsa"):
            no_convert = True
        try:
            pub_path = os.path.join('/home/', user_name, '.ssh',
                'authorized_keys')
            ovf_env.UserName = user_name
            if(no_convert):
                if(cert_txt):
                    pub_path = ovf_env.PrepareDir(pub_path)
                    final_cert_txt = cert_txt
                    if(not cert_txt.endswith("\n")):
                        final_cert_txt = final_cert_txt+"\n"
                    waagent.AppendFileContents(pub_path, final_cert_txt)
                    waagent.MyDistro.setSelinuxContext(pub_path,
                        'unconfined_u:object_r:ssh_home_t:s0')
                    waagent.ChangeOwner(pub_path, user_name)
                    hutil.log("Succeeded in resetting ssh_key.")
                else:
                    err_msg = "Failed to reset ssh key because the cert content is empty."
                    waagent.AddExtensionEvent(name=hutil.get_name(),
                                      op=waagent.WALAEventOperation.Enable,
                                      isSuccess=False,
                                      message="(02100)"+err_msg)
            else:
                if cert_txt:
                    _save_cert_str_as_file(cert_txt, 'temp.crt')
                else:
                    for pkey in ovf_env.SshPublicKeys:
                        if pkey[1]:
                            shutil.copy(
                                os.path.join(waagent.LibDir, pkey[0] + '.crt'),
                                os.path.join(os.getcwd(), 'temp.crt'))
                            break
                pub_path = ovf_env.PrepareDir(pub_path)
                retcode = waagent.Run(waagent.Openssl + " x509 -in temp.crt -noout -pubkey > temp.pub")
                if retcode > 0:
                    raise Exception("Failed to generate public key file.")
                waagent.MyDistro.sshDeployPublicKey('temp.pub', pub_path)
                waagent.MyDistro.setSelinuxContext(pub_path,
                    'unconfined_u:object_r:ssh_home_t:s0')
                waagent.ChangeOwner(pub_path, user_name)
                os.remove('temp.pub')
                os.remove('temp.crt')
                hutil.log("Succeeded in resetting ssh_key.")
        except Exception as e:
            hutil.log(str(e))
            waagent.AddExtensionEvent(name=hutil.get_name(),
                                      op=waagent.WALAEventOperation.Enable,
                                      isSuccess=False,
                                      message="(02100)Failed to reset ssh key.")


def _get_other_sudoers(userName):
    sudoersFile = '/etc/sudoers.d/waagent'
    if not os.path.isfile(sudoersFile):
        return None
    sudoers = waagent.GetFileContents(sudoersFile).split("\n")
    pattern = '^{0}\s'.format(userName)
    sudoers = filter(lambda x : re.match(pattern, x) is None, sudoers)
    return sudoers


def _save_other_sudoers(sudoers):
    sudoersFile = '/etc/sudoers.d/waagent'
    if sudoers is None:
        return
    waagent.AppendFileContents(sudoersFile, "\n".join(sudoers))
    os.chmod("/etc/sudoers.d/waagent", 0o440)


def _allow_password_auth():
    configPath = '/etc/ssh/sshd_config'
    config = waagent.GetFileContents(configPath).split("\n")
    _set_sshd_config(config, "PasswordAuthentication", "yes")
    _set_sshd_config(config, "ChallengeResponseAuthentication", "yes")
    waagent.ReplaceFileContentsAtomic(configPath, "\n".join(config))


def _set_sshd_config(config, name, val):
    notfound = True
    for i in range(0, len(config)):
        if config[i].startswith(name):
            config[i] = "{0} {1}".format(name, val)
            notfound = False
        elif config[i].startswith("Match"):
            # Match block must be put in the end of sshd config
            break
    if notfound:
        config.insert(i, "{0} {1}".format(name, val))
    return config


def _reset_sshd_config(sshd_file_path):
    distro = platform.dist()
    distro_name = distro[0]
    version = distro[1]
    config_file_path = os.path.join(os.getcwd(), 'resources', '%s_%s' % (distro_name, version))
    if not(os.path.exists(config_file_path)):
        config_file_path = os.path.join(os.getcwd(), 'resources', '%s_%s' % (distro_name, 'default'))
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
        for line in waagent.GetFileContents(config_file_path).split('\n'):
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
        
        waagent.SetFileContents(cfg_tempfile, cfg_content)
        
        waagent.Run("coreos-cloudinit -from-file " + cfg_tempfile, chk_err=False)
        os.remove(cfg_tempfile)
    else:
        shutil.copyfile(config_file_path, sshd_file_path)
        waagent.MyDistro.restartSshService()


def _backup_sshd_config(sshd_file_path):
    if(os.path.exists(sshd_file_path)):
        backup_file_name = '%s_%s' % (
            sshd_file_path, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        shutil.copyfile(sshd_file_path, backup_file_name)


def _save_cert_str_as_file(cert_txt, file_name):
    cert_start = cert_txt.find(BeginCertificateTag)
    if(cert_start >= 0):
        cert_txt = cert_txt[cert_start + len(BeginCertificateTag):]
    cert_end = cert_txt.find(EndCertificateTag)
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
    match_string = '-A %s' % rule_string
    cmd_result = waagent.RunGetOutput("iptables-save")
    while cmd_result[0] == 0 and (rule_string in cmd_result[1]):
        waagent.Run("iptables -D %s" % rule_string)
        cmd_result = waagent.RunGetOutput("iptables-save")


def _insert_rule_if_not_exists(rule_string):
    match_string = '-A %s' % rule_string
    cmd_result = waagent.RunGetOutput("iptables-save")
    if cmd_result[0] == 0 and (rule_string not in cmd_result[1]):
        waagent.Run("iptables -I %s" % rule_string)

def check_and_repair_disk(hutil):
    public_settings = hutil.get_public_settings()
    if public_settings:
        check_disk = public_settings.get('check_disk')
        repair_disk = public_settings.get('repair_disk')
        disk_name = public_settings.get('disk_name')

        if check_disk and repair_disk:
            err_msg = ("check_disk and repair_disk was both specified."
                "Only one of them can be specified")
            hutil.error(err_msg)
            hutil.do_exit(1, 'Enable', 'error', '0', 'Enable failed.')

        if check_disk:
            outretcode = _fsck_check(hutil)
            hutil.log("Successfully checked disk")
            return outretcode

        if repair_disk:
            outdata = _fsck_repair(hutil, disk_name)
            hutil.log("Repaired and remounted disk")
            return outdata

def _fsck_check(hutil):
    try:
        retcode = waagent.Run("fsck -As -y")
        if retcode > 0:
            hutil.log(retcode)
            raise Exception("Disk check was not successful")
        else:
            return retcode
    except Exception as e:
        hutil.error("Failed to run disk check with error: {0}, {1}".format(
            str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Check', 'error', '0', 'Check failed.')


def _fsck_repair(hutil, disk_name):
    # first unmount disks and loop devices lazy + forced
    try:
        cmd_result = waagent.Run("umount -f /%s" % disk_name)
        if cmd_result!=0:
            # Fail fast
            hutil.log("Failed to unmount disk: %s" % disk_name)
            # run repair
            retcode = waagent.Run("fsck -AR -y")
            hutil.log("Ran fsck with return code: %d" % retcode)
        if retcode == 0:
            retcode,output = waagent.RunGetOutput("mount")
            hutil.log(output)
            return output
        else:
            raise Exception("Failed to mount disks")
    except Exception as e:
        hutil.error("{0}, {1}".format(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Repair','error','0', 'Repair failed.')

if __name__ == '__main__' :
    main()
