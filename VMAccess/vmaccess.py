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
import re
import shutil
import sys
import tempfile
import time
import traceback

import Utils.handlerutil2 as handler_util
import Utils.logger as logger
import Utils.extensionutils as ext_utils
import Utils.distroutils as dist_utils
import Utils.constants as constants
import Utils.ovfutils as ovf_utils
import VMAccess.errorclarification as error_code

# Define global variables
ExtensionShortName = 'VMAccess'
BeginCertificateTag = '-----BEGIN CERTIFICATE-----'
EndCertificateTag = '-----END CERTIFICATE-----'
BeginSSHTag = '---- BEGIN SSH2 PUBLIC KEY ----'
OutputSplitter = ';'
SshdConfigPath = '/etc/ssh/sshd_config'
SshdConfigBackupPath = '/var/cache/vmaccess/backup'

# overwrite the default logger
logger.global_shared_context_logger = logger.Logger('/var/log/waagent.log', '/dev/stdout')

def get_os_name():
    if os.path.isfile(constants.os_release):
        return ext_utils.get_line_starting_with("NAME", constants.os_release)
    elif os.path.isfile(constants.system_release):
        return ext_utils.get_file_contents(constants.system_release)
    return None

def get_linux_agent_conf_filename(os_name):
    if os_name is not None:
        if re.search("coreos", os_name, re.IGNORECASE) or re.search("flatcar", os_name, re.IGNORECASE):
            return "/usr/share/oem/waagent.conf"
    return "/etc/waagent.conf"

class ConfigurationProvider(object):
    """
    Parse amd store key:values in waagent.conf
    """

    def __init__(self, wala_config_file):
        self.values = dict()
        if not os.path.isfile(wala_config_file):
            logger.warning("Missing configuration in {0}, setting default values for PasswordCryptId and PasswordCryptSaltLength".format(wala_config_file))
            self.values["Provisioning.PasswordCryptId"] = "6"
            self.values["Provisioning.PasswordCryptSaltLength"] = 10
            return
        try:
            for line in ext_utils.get_file_contents(wala_config_file).split('\n'):
                if not line.startswith("#") and "=" in line:
                    parts = line.split()[0].split('=')
                    value = parts[1].strip("\" ")
                    if value != "None":
                        self.values[parts[0]] = value
                    else:
                        self.values[parts[0]] = None
        # when get_file_contents returns none
        except AttributeError:
            logger.error("Unable to parse {0}".format(wala_config_file))
            raise
        return

    def get(self, key):
        return self.values.get(key)

    def yes(self, key):
        config_value = self.get(key)
        if config_value is not None and config_value.lower().startswith("y"):
            return True
        else:
            return False

    def no(self, key):
        config_value = self.get(key)
        if config_value is not None and config_value.lower().startswith("n"):
            return True
        else:
            return False


OSName = get_os_name()
Configuration = ConfigurationProvider(get_linux_agent_conf_filename(OSName))
MyDistro = dist_utils.get_my_distro(Configuration, OSName)


def main():
    logger.log("%s started to handle." % ExtensionShortName)

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
        logger.error(err_msg)


def install():
    hutil = handler_util.HandlerUtility()
    hutil.do_parse_context('Install')
    hutil.do_exit(0, 'Install', 'success', '0', 'Install Succeeded')


def enable():
    errorstatus = error_code.ErrorCode.SYSTEM_ERROR
    hutil = handler_util.HandlerUtility()
    hutil.do_parse_context('Enable')

    try:
        hutil.exit_if_enabled(remove_protected_settings=True)  # If no new seqNum received, exit.

        reset_ssh = None
        remove_user = None
        restore_backup_ssh = None
        protect_settings = hutil.get_protected_settings()
        if protect_settings:
            reset_ssh = protect_settings.get('reset_ssh', False)
            remove_user = protect_settings.get('remove_user')
            restore_backup_ssh = protect_settings.get('restore_backup_ssh', False)

        if remove_user and _is_sshd_config_modified(protect_settings):
            ext_utils.add_extension_event(name=hutil.get_name(),
                                          op=constants.WALAEventOperation.Enable,
                                          is_success=False,
                                          message="(03002)Argument error, conflicting operations")
            raise Exception("Cannot reset sshd_config and remove a user in one operation.")

        _forcibly_reset_chap(hutil)

        if reset_ssh or restore_backup_ssh:
            _open_ssh_port()
            hutil.log("Succeeded in check and open ssh port.")
            ext_utils.add_extension_event(name=hutil.get_name(), op="scenario", is_success=True, message="reset-ssh")
            _reset_sshd_config(hutil, restore_backup_ssh)
            hutil.log("Succeeded in {0} sshd_config.".format("resetting" if reset_ssh else "restoring"))

        if remove_user:
            ext_utils.add_extension_event(name=hutil.get_name(), op="scenario", is_success=True, message="remove-user")
            errorstatus,errormsg = _remove_user_account(remove_user, hutil)
            if errorstatus is not None:
                raise Exception(errormsg)

        output = _set_user_account_pub_key(protect_settings, hutil)

        if output is not None:
                errorstatus,errormsg = output[0], output[1]
                raise Exception(errormsg)
        
        if _is_sshd_config_modified(protect_settings):
            MyDistro.restart_ssh_service()

        errorstatus = check_and_repair_disk(hutil)
        if errorstatus is not None:
            if errorstatus == error_code.ErrorCode.CHECK_REPAIR_DISK_ERROR:
                hutil.do_exit(1, 'Enable', 'error', '0', 'Enable failed.', errorstatus.value)
            if errorstatus == error_code.ErrorCode.CHECK_DISK_ERROR:
                hutil.do_exit(1, 'Enable', 'error', '0', 'Check disk failed.', errorstatus.value)
            if errorstatus == error_code.ErrorCode.REPAIR_DISK_ERROR:
                hutil.do_exit(1, 'Enable', 'error', '0', 'Repair disk failed.', errorstatus.value)
            
        hutil.do_exit(0, 'Enable', 'success', '0', 'Enable succeeded.')
    except Exception as e:
        hutil.error(("Failed to enable the extension with error: {0}, "
                     "stack trace: {1}").format(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable', 'error', '0', "Enable failed: {0}".format(str(e)),errorstatus.value)


def _forcibly_reset_chap(hutil):
    name = "ChallengeResponseAuthentication"
    _backup_and_update_sshd_config(hutil, name, "no")
    MyDistro.restart_ssh_service()


def _is_sshd_config_modified(protected_settings):
    result = protected_settings.get('reset_ssh') or protected_settings.get('restore_backup_ssh') or protected_settings.get('password')
    return result is not None


def uninstall():
    hutil = handler_util.HandlerUtility()
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0, 'Uninstall', 'success', '0', 'Uninstall succeeded')


def disable():
    hutil = handler_util.HandlerUtility()
    hutil.do_parse_context('Disable')
    hutil.do_exit(0, 'Disable', 'success', '0', 'Disable Succeeded')


def update():
    hutil = handler_util.HandlerUtility()
    hutil.do_parse_context('Update')
    hutil.do_exit(0, 'Update', 'success', '0', 'Update Succeeded')


def _remove_user_account(user_name, hutil):
    hutil.log("Removing user account")

    try:
        sudoers = _get_other_sudoers(user_name)
        MyDistro.delete_account(user_name)
        _save_other_sudoers(sudoers)
    except Exception as e:
        ext_utils.add_extension_event(name=hutil.get_name(),
                                      op=constants.WALAEventOperation.Enable,
                                      is_success=False,
                                      message="(02102)Failed to remove user.")
        return error_code.ErrorCode.SYSTEM_ERROR, "Failed to remove user {0}".format(e)

    ext_utils.add_extension_event(name=hutil.get_name(),
                                  op=constants.WALAEventOperation.Enable,
                                  is_success=True,
                                  message="Successfully removed user")
    return None, "Successfully removed user {0}".format(user_name)


def _set_user_account_pub_key(protect_settings, hutil):
    ovf_env = None
    try:
        ovf_xml = ext_utils.get_file_contents('/var/lib/waagent/ovf-env.xml')
        if ovf_xml is not None:
            ovf_env = ovf_utils.OvfEnv.parse(ovf_xml, Configuration, False, False)
    except (EnvironmentError, ValueError, KeyError, AttributeError, TypeError):
        pass
    if ovf_env is None:
        # default ovf_env with empty data
        ovf_env = ovf_utils.OvfEnv()
        logger.log("could not load ovf-env.xml")

    # user name must be provided if set ssh key or password
    if not protect_settings or 'username' not in protect_settings:
        return

    user_name = protect_settings['username']
    user_pass = protect_settings.get('password')
    cert_txt = protect_settings.get('ssh_key')
    expiration = protect_settings.get('expiration')
    remove_prior_keys = protect_settings.get('remove_prior_keys')
    enable_passwordless_access = protect_settings.get('enable_passwordless_access', False)

    no_convert = False
    if not user_pass and not cert_txt and not ovf_env.SshPublicKeys:
        return error_code.ErrorCode.USER_PASSWORD_ERROR, "No password or ssh_key is specified."

    if user_pass is not None and len(user_pass) == 0:
        user_pass = None
        hutil.log("empty passwords are not allowed, ignoring password reset")

    # Reset user account and password, password could be empty
    sudoers = _get_other_sudoers(user_name)
    error_string = MyDistro.create_account(
        user_name, user_pass, expiration, None, enable_passwordless_access)
    _save_other_sudoers(sudoers)

    if error_string is not None:
        err_msg = "Failed to create the account or set the password"
        ext_utils.add_extension_event(name=hutil.get_name(),
                                      op=constants.WALAEventOperation.Enable,
                                      is_success=False,
                                      message="(02101)" + err_msg)
        return error_code.ErrorCode.SYSTEM_ERROR, err_msg + " with " + error_string
    hutil.log("Succeeded in creating the account or setting the password.")

    # Allow password authentication if user_pass is provided
    if user_pass is not None:
        ext_utils.add_extension_event(name=hutil.get_name(), op="scenario", is_success=True,
                                      message="create-user-with-password")
        _allow_password_auth(hutil)

    # Reset ssh key with the new public key passed in or reuse old public key.
    if cert_txt:
        # support for SSH2-compatible format for public keys in addition to OpenSSH-compatible format
        if cert_txt.strip().startswith(BeginSSHTag):
            ext_utils.set_file_contents("temp.pub", cert_txt.strip())
            retcode, output = ext_utils.run_command_get_output(['ssh-keygen', '-i', '-f', 'temp.pub'])
            if retcode > 0:
                raise Exception("Failed to convert SSH2 key to OpenSSH key.")
            hutil.log("Succeeded in converting SSH2 key to OpenSSH key.")
            cert_txt = output
            os.remove("temp.pub")

        if cert_txt.strip().lower().startswith("ssh-rsa") or cert_txt.strip().lower().startswith("ssh-ed25519"):
            no_convert = True
        try:
            pub_path = os.path.join('/home/', user_name, '.ssh',
                                    'authorized_keys')
            ovf_env.UserName = user_name
            if no_convert:
                if cert_txt:
                    pub_path = ovf_env.prepare_dir(pub_path, MyDistro)
                    final_cert_txt = cert_txt
                    if not cert_txt.endswith("\n"):
                        final_cert_txt = final_cert_txt + "\n"

                    if remove_prior_keys == True:
                        ext_utils.set_file_contents(pub_path, final_cert_txt)
                        hutil.log("Removed prior ssh keys and added new key for user %s" % user_name)
                    else:
                        ext_utils.append_file_contents(pub_path, final_cert_txt)
        
                    MyDistro.set_se_linux_context(
                        pub_path, 'unconfined_u:object_r:ssh_home_t:s0')
                    ext_utils.change_owner(pub_path, user_name)
                    ext_utils.add_extension_event(name=hutil.get_name(), op="scenario", is_success=True,
                                                  message="create-user")
                    hutil.log("Succeeded in resetting ssh_key.")
                else:
                    err_msg = "Failed to reset ssh key because the cert content is empty."
                    ext_utils.add_extension_event(name=hutil.get_name(),
                                                  op=constants.WALAEventOperation.Enable,
                                                  is_success=False,
                                                  message="(02100)" + err_msg)
            else:
                # do the certificate conversion
                # we support PKCS8 certificates besides ssh-rsa public keys
                _save_cert_str_as_file(cert_txt, 'temp.crt')
                pub_path = ovf_env.prepare_dir(pub_path, MyDistro)
                retcode = ext_utils.run_command_and_write_stdout_to_file(
                    [constants.Openssl, 'x509', '-in', 'temp.crt', '-noout', '-pubkey'], "temp.pub")
                if retcode > 0:
                    raise Exception("Failed to generate public key file.")

                MyDistro.ssh_deploy_public_key('temp.pub', pub_path)
                os.remove('temp.pub')
                os.remove('temp.crt')
                ext_utils.add_extension_event(name=hutil.get_name(), op="scenario", is_success=True,
                                              message="create-user")
                hutil.log("Succeeded in resetting ssh_key.")
        except Exception as e:
            hutil.log(str(e))
            ext_utils.add_extension_event(name=hutil.get_name(),
                                          op=constants.WALAEventOperation.Enable,
                                          is_success=False,
                                          message="(02100)Failed to reset ssh key.")
            return error_code.ErrorCode.SYSTEM_ERROR, e


def _get_other_sudoers(user_name):
    sudoers_file = '/etc/sudoers.d/waagent'
    if not os.path.isfile(sudoers_file):
        return None
    sudoers = ext_utils.get_file_contents(sudoers_file).split("\n")
    pattern = '^{0}\s'.format(user_name)
    sudoers = list(filter(lambda x: re.match(pattern, x) is None, sudoers))
    return sudoers


def _save_other_sudoers(sudoers):
    sudoers_file = '/etc/sudoers.d/waagent'
    if sudoers is None:
        return
    ext_utils.append_file_contents(sudoers_file, "\n".join(sudoers))
    os.chmod("/etc/sudoers.d/waagent", 0o440)


def _allow_password_auth(hutil):
    name = "PasswordAuthentication"
    _backup_and_update_sshd_config(hutil, name, "yes")

    cloudInitConfigPath = "/etc/ssh/sshd_config.d/50-cloud-init.conf"
    config = ext_utils.get_file_contents(cloudInitConfigPath)
    if config is not None:
        config = config.split("\n")
        _set_sshd_config(config, name, "yes")
        ext_utils.replace_file_with_contents_atomic(cloudInitConfigPath, "\n".join(config))


def _backup_and_update_sshd_config(hutil, attr_name, attr_value):
    config = ext_utils.get_file_contents(SshdConfigPath).split("\n")

    for i in range(0, len(config)):
        if config[i].startswith(attr_name) and attr_value in config[i].lower():
            hutil.log("%s already set to %s in sshd_config, skip update." % (attr_name, attr_value))
            return

    hutil.log("Setting %s to %s in sshd_config." % (attr_name, attr_value))
    
    _backup_sshd_config(hutil)
    _set_sshd_config(config, attr_name, attr_value)
    ext_utils.replace_file_with_contents_atomic(SshdConfigPath, "\n".join(config))


def _set_sshd_config(config, name, val):
    notfound = True
    i = None
    for i in range(0, len(config)):
        if config[i].startswith(name):
            config[i] = "{0} {1}".format(name, val)
            notfound = False
        elif config[i].startswith("Match"):
            # Match block must be put in the end of sshd config
            break
    if notfound:
        if i is None:
            i = 0
        config.insert(i, "{0} {1}".format(name, val))
    return config


def _get_default_ssh_config_filename():
    if OSName is not None:
        # the default ssh config files are present in
        # /var/lib/waagent/Microsoft.OSTCExtensions.VMAccessForLinux-<version>/resources/
        if re.search("centos", OSName, re.IGNORECASE):
            return "centos_default"
        if re.search("debian", OSName, re.IGNORECASE):
            return "debian_default"
        if re.search("fedora", OSName, re.IGNORECASE):
            return "fedora_default"
        if re.search("red\s?hat", OSName, re.IGNORECASE):
            return "redhat_default"
        if re.search("suse", OSName, re.IGNORECASE):
            return "SuSE_default"
        if re.search("ubuntu", OSName, re.IGNORECASE):
            return "ubuntu_default"
    return "default"


def _reset_sshd_config(hutil, restore_backup_ssh):
    ssh_default_config_filename = _get_default_ssh_config_filename()
    ssh_default_config_file_path = os.path.join(os.getcwd(), 'resources', ssh_default_config_filename)

    if not os.path.exists(ssh_default_config_file_path):
        ssh_default_config_file_path = os.path.join(os.getcwd(), 'resources', 'default')

    if restore_backup_ssh:
        if os.path.exists(SshdConfigBackupPath):
            ssh_default_config_file_path = SshdConfigBackupPath

    # handle CoreOS differently
    if isinstance(MyDistro, dist_utils.CoreOSDistro):
        # Parse sshd port from ssh_default_config_file_path
        sshd_port = 22
        regex = re.compile(r"^Port\s+(\d+)", re.VERBOSE)
        with open(ssh_default_config_file_path) as f:
            for line in f:
                match = regex.match(line)
                if match:
                    sshd_port = match.group(1)
                    break

        # Prepare cloud init config for coreos-cloudinit
        f = tempfile.NamedTemporaryFile(delete=False)
        f.close()
        cfg_tempfile = f.name
        cfg_content = "#cloud-config\n\n"

        # Overwrite /etc/ssh/sshd_config
        cfg_content += "write_files:\n"
        cfg_content += "  - path: {0}\n".format(SshdConfigPath)
        cfg_content += "    permissions: 0600\n"
        cfg_content += "    owner: root:root\n"
        cfg_content += "    content: |\n"
        for line in ext_utils.get_file_contents(ssh_default_config_file_path).split('\n'):
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

        ext_utils.set_file_contents(cfg_tempfile, cfg_content)

        ext_utils.run(['coreos-cloudinit', '-from-file', cfg_tempfile], chk_err=False)
        os.remove(cfg_tempfile)
    else:
        shutil.copyfile(ssh_default_config_file_path, SshdConfigPath)
        if ssh_default_config_file_path == SshdConfigBackupPath:
            hutil.log("sshd_config restored from backup, remove backup file.")
            # Remove backup config once sshd_config restored
            os.remove(ssh_default_config_file_path)
        MyDistro.restart_ssh_service()


def _backup_sshd_config(hutil):
    if os.path.exists(SshdConfigPath) and not os.path.exists(SshdConfigBackupPath):
        # Create VMAccess cache folder if doesn't exist
        if not os.path.exists(os.path.dirname(SshdConfigBackupPath)):
            os.makedirs(os.path.dirname(SshdConfigBackupPath))

        hutil.log("Create backup ssh config file")
        open(SshdConfigBackupPath, 'a').close()
        
        # When copying, make sure to preserve permissions and ownership.
        ownership = os.stat(SshdConfigPath)
        shutil.copy2(SshdConfigPath, SshdConfigBackupPath)
        os.chown(SshdConfigBackupPath, ownership.st_uid, ownership.st_gid)


def _save_cert_str_as_file(cert_txt, file_name):
    cert_start = cert_txt.find(BeginCertificateTag)
    if cert_start >= 0:
        cert_txt = cert_txt[cert_start + len(BeginCertificateTag):]
    cert_end = cert_txt.find(EndCertificateTag)
    if cert_end >= 0:
        cert_txt = cert_txt[:cert_end]
    cert_txt = cert_txt.strip()
    cert_txt = "{0}\n{1}\n{2}\n".format(BeginCertificateTag, cert_txt, EndCertificateTag)
    ext_utils.set_file_contents(file_name, cert_txt)


def _open_ssh_port():
    _del_rule_if_exists(['INPUT', '-p', 'tcp', '-m', 'tcp', '--dport', '22', '-j', 'DROP'])
    _del_rule_if_exists(['INPUT', '-p', 'tcp', '-m', 'tcp', '--dport', '22', '-j', 'REJECT'])
    _del_rule_if_exists(['INPUT', '-p', '-j', 'DROP'])
    _del_rule_if_exists(['INPUT', '-p', '-j', 'REJECT'])
    _insert_rule_if_not_exists(['INPUT', '-p', 'tcp', '-m', 'tcp', '--dport', '22', '-j', 'ACCEPT'])

    _del_rule_if_exists(['OUTPUT', '-p', 'tcp', '-m', 'tcp', '--sport', '22', '-j', 'DROP'])
    _del_rule_if_exists(['OUTPUT', '-p', 'tcp', '-m', 'tcp', '--sport', '22', '-j', 'REJECT'])
    _del_rule_if_exists(['OUTPUT', '-p', '-j', 'DROP'])
    _del_rule_if_exists(['OUTPUT', '-p', '-j', 'REJECT'])
    _insert_rule_if_not_exists(['OUTPUT', '-p', 'tcp', '-m', 'tcp', '--dport', '22', '-j', 'ACCEPT'])


def _del_rule_if_exists(rule_string):
    rule_string_for_cmp = " ".join(rule_string)
    cmd_result = ext_utils.run_command_get_output(['iptables-save'])
    while cmd_result[0] == 0 and (rule_string_for_cmp in cmd_result[1]):
        ext_utils.run(['iptables', '-D'] + rule_string)
        cmd_result = ext_utils.run_command_get_output(['iptables-save'])


def _insert_rule_if_not_exists(rule_string):
    rule_string_for_cmp = " ".join(rule_string)
    cmd_result = ext_utils.run_command_get_output(['iptables-save'])
    if cmd_result[0] == 0 and (rule_string_for_cmp not in cmd_result[1]):
        ext_utils.run_command_get_output(['iptables', '-I'] + rule_string)


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
            return error_code.ErrorCode.CHECK_REPAIR_DISK_ERROR

        if check_disk:
            ext_utils.add_extension_event(name=hutil.get_name(), op="scenario", is_success=True, message="check_disk")
            outretcode = _fsck_check(hutil)
            return outretcode

        if repair_disk:
            ext_utils.add_extension_event(name=hutil.get_name(), op="scenario", is_success=True, message="repair_disk")
            outdata = _fsck_repair(hutil, disk_name)
            return outdata


def _fsck_check(hutil):
    retcode = ext_utils.run(['fsck', '-As', '-y'])
    if retcode > 0:
        hutil.log(str(retcode))
        hutil.error("Failed to run disk check with error: {0}, {1}".format(
        str("Disk check was not successful"), traceback.format_exc()))
        return error_code.ErrorCode.CHECK_DISK_ERROR
    else:
        hutil.log("Successfully checked disk")
        return None



def _fsck_repair(hutil, disk_name):
    # first unmount disks and loop devices lazy + forced
    try:
        cmd_result = ext_utils.run(['umount', '-f', '/' + disk_name])
        if cmd_result != 0:
            # Fail fast
            hutil.log("Failed to unmount disk: %s" % disk_name)
            # run repair
            retcode = ext_utils.run(['fsck', '-AR', '-y'])
            hutil.log("Ran fsck with return code: %d" % retcode)
            if retcode == 0:
                retcode, output = ext_utils.run_command_get_output(["mount"])
                hutil.log(output)
                hutil.log("Repaired and remounted disk")
                return output
        else:
            raise Exception("Failed to mount disks")
    except Exception as e:
        hutil.error("{0}, {1}".format(str(e), traceback.format_exc()))
        return error_code.ErrorCode.REPAIR_DISK_ERROR

if __name__ == '__main__':
    main()
