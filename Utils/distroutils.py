import os
import sys
import pwd
import random
import crypt
import string
import Utils.constants as constants
import Utils.extensionutils as ext_utils
import Utils.openssutils as openssl_utils
from Utils.logger import default_logger as logger


config = ext_utils.ConfigurationProvider(None)


class AbstractDistro(object):
    """
    AbstractDistro defines a skeleton neccesary for a concrete Distro class.

    Generic methods and attributes are kept here, distribution specific attributes
    and behavior are to be placed in the concrete child named distroDistro, where
    distro is the string returned by calling python platform.linux_distribution()[0].
    So for CentOS the derived class is called 'centosDistro'.
    """

    def __init__(self):
        """
        Generic Attributes go here.  These are based on 'majority rules'.
        This __init__() may be called or overriden by the child.
        """
        self.agent_service_name = os.path.basename(sys.argv[0])
        self.selinux = None
        self.service_cmd = '/usr/sbin/service'
        self.ssh_service_restart_option = 'restart'
        self.ssh_service_name = 'ssh'
        self.ssh_config_file = '/etc/ssh/sshd_config'
        self.hostname_file_path = '/etc/hostname'
        self.dhcp_client_name = 'dhclient'
        self.requiredDeps = ['route', 'shutdown', 'ssh-keygen', 'useradd', 'usermod',
                             'openssl', 'sfdisk', 'fdisk', 'mkfs',
                             'sed', 'grep', 'sudo', 'parted']
        self.init_script_file = '/etc/init.d/waagent'
        self.agent_package_name = 'WALinuxAgent'
        self.fileBlackList = ["/root/.bash_history", "/var/log/waagent.log", '/etc/resolv.conf']
        self.agent_files_to_uninstall = ["/etc/waagent.conf", "/etc/logrotate.d/waagent"]
        self.grubKernelBootOptionsFile = '/etc/default/grub'
        self.grubKernelBootOptionsLine = 'GRUB_CMDLINE_LINUX_DEFAULT='
        self.getpidcmd = 'pidof'
        self.mount_dvd_cmd = 'mount'
        self.sudoers_dir_base = '/etc'
        self.waagent_conf_file = constants.WaagentConf
        self.shadow_file_mode = 0o600
        self.shadow_file_path = "/etc/shadow"
        self.dhcp_enabled = False

    def is_se_linux_system(self):
        """
        Checks and sets self.selinux = True if SELinux is available on system.
        """
        if self.selinux is None:
            if ext_utils.run(['which', 'getenforce'], chk_err=False):
                self.selinux = False
            else:
                self.selinux = True
        return self.selinux

    def get_home(self):
        """
        Attempt to guess the $HOME location.
        Return the path string.
        """
        home = None
        try:
            home = ext_utils.get_line_starting_with("HOME", "/etc/default/useradd").split('=')[1].strip()
        except:
            pass
        if (home is None) or (not home.startswith("/")):
            home = "/home"
        return home

    def set_selinux_context(self, path, cn):
        """
        Calls shell 'chcon' with 'path' and 'cn' context.
        Returns exit result.
        """
        if self.is_se_linux_system():
            return ext_utils.run(['chcon', 'cn', 'path'])

    def restart_ssh_service(self):
        """
        Service call to re(start) the SSH service
        """
        ssh_restart_cmd = [self.service_cmd, self.ssh_service_name, self.ssh_service_restart_option]
        ret_code = ext_utils.run(ssh_restart_cmd)
        if ret_code > 0:
            logger.error("Failed to restart SSH service with return code:" + str(ret_code))
        return ret_code

    def ssh_deploy_public_key(self, fprint, path):
        """
        Generic sshDeployPublicKey - over-ridden in some concrete Distro classes due to minor differences in openssl packages deployed
        """
        error = 0
        ssh_pub_key = openssl_utils.openssl_publickey_to_ssh(fprint)
        if ssh_pub_key is not None:
            ext_utils.append_file_contents(path, ssh_pub_key)
        else:
            logger.error("Failed: " + fprint + ".crt -> " + path)
            error = 1
        return error

    def change_password(self, user, password):
        logger.log("Change user password")
        crypt_id = config.get("Provisioning.PasswordCryptId")
        if crypt_id is None:
            crypt_id = "6"

        salt_len = config.get("Provisioning.PasswordCryptSaltLength")
        try:
            salt_len = int(salt_len)
            if salt_len < 0 or salt_len > 10:
                salt_len = 10
        except (ValueError, TypeError):
            salt_len = 10

        return self.chpasswd(user, password, crypt_id=crypt_id,
                             salt_len=salt_len)

    def chpasswd(self, username, password, crypt_id=6, salt_len=10):
        passwd_hash = self.gen_password_hash(password, crypt_id, salt_len)
        cmd = ['usermod', '-p', passwd_hash, username]
        ret, output = ext_utils.run_command_get_output(cmd, log_cmd=False)
        if ret != 0:
            return "Failed to set password for {0}: {1}".format(username, output)

    def gen_password_hash(self, password, crypt_id, salt_len):
        collection = string.ascii_letters + string.digits
        salt = ''.join(random.choice(collection) for _ in range(salt_len))
        salt = "${0}${1}".format(crypt_id, salt)
        return crypt.crypt(password, salt)


    def create_account(self, user, password, expiration, thumbprint):
        """
        Create a user account, with 'user', 'password', 'expiration', ssh keys
        and sudo permissions.
        Returns None if successful, error string on failure.
        """
        user_entry = None
        try:
            user_entry = pwd.getpwnam(user)
        except:
            pass
        uid_min = None
        try:
            uid_min = int(ext_utils.get_line_starting_with("UID_MIN", "/etc/login.defs").split()[1])
        except:
            pass
        if uid_min is None:
            uid_min = 100
        if user_entry is not None and user_entry[2] < uid_min:
            logger.error("CreateAccount: " + user + " is a system user. Will not set password.")
            return "Failed to set password for system user: " + user + " (0x06)."
        if user_entry is None:
            command = ['useradd', '-m', user]
            if expiration is not None:
                command += ['-e', expiration.split('.')[0]]
            if ext_utils.run(command):
                logger.error("Failed to create user account: " + user)
                return "Failed to create user account: " + user + " (0x07)."
        else:
            logger.log("CreateAccount: " + user + " already exists. Will update password.")
        if password is not None:
            self.change_password(user, password)
        try:
            # for older distros create sudoers.d
            if not os.path.isdir('/etc/sudoers.d/'):
                # create the /etc/sudoers.d/ directory
                os.mkdir('/etc/sudoers.d/')
                # add the include of sudoers.d to the /etc/sudoers
                ext_utils.set_file_contents('/etc/sudoers', ext_utils.get_file_contents('/etc/sudoers') + '\n#includedir /etc/sudoers.d\n')
            if password is None:
                ext_utils.set_file_contents("/etc/sudoers.d/waagent", user + " ALL = (ALL) NOPASSWD: ALL\n")
            else:
                ext_utils.set_file_contents("/etc/sudoers.d/waagent", user + " ALL = (ALL) ALL\n")
            os.chmod("/etc/sudoers.d/waagent", 0o440)
        except:
            logger.error("CreateAccount: Failed to configure sudo access for user.")
            return "Failed to configure sudo privileges (0x08)."
        home = self.get_home()
        if thumbprint is not None:
            ssh_dir = home + "/" + user + "/.ssh"
            ext_utils.create_dir(ssh_dir, user, 0o700)
            pub = ssh_dir + "/id_rsa.pub"
            prv = ssh_dir + "/id_rsa"
            ext_utils.run_command_and_write_stdout_to_file(['ssh-keygen', '-y', '-f', thumbprint + '.prv'], pub)
            for f in [pub, prv]:
                os.chmod(f, 0o600)
                ext_utils.change_owner(f, user)
            ext_utils.set_file_contents(ssh_dir + "/authorized_keys", ext_utils.get_file_contents(pub))
            ext_utils.change_owner(ssh_dir + "/authorized_keys", user)
        logger.log("Created user account: " + user)
        return None

    def delete_account(self, user):
        """
            Delete the 'user'.
            Clear utmp first, to avoid error.
            Removes the /etc/sudoers.d/waagent file.
            """
        user_entry = None
        try:
            user_entry = pwd.getpwnam(user)
        except:
            pass
        if user_entry is None:
            logger.error("DeleteAccount: " + user + " not found.")
            return
        uid_min = None
        try:
            uid_min = int(ext_utils.get_line_starting_with("UID_MIN", "/etc/login.defs").split()[1])
        except:
            pass
        if uid_min is None:
            uid_min = 100
        if user_entry[2] < uid_min:
            logger.error("DeleteAccount: " + user + " is a system user. Will not delete account.")
            return
        ext_utils.run(['rm', '-f', '/var/run/utmp'])  # Delete utmp to prevent error if we are the 'user' deleted
        ext_utils.run(['userdel', '-f', '-r', user])
        try:
            os.remove("/etc/sudoers.d/waagent")
        except IOError:
            pass
        return
