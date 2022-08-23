#!/usr/bin/env python
#
# Azure Linux extension
# Distribution-specific actions
#
# Linux Azure Diagnostic Extension (Current version is specified in manifest.xml)
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import exceptions
import time
import subprocess
import re
from Utils.WAAgentUtil import waagent


class CommonActions:
    def __init__(self, logger):
        self.logger = logger

    def filterNonAsciiCharacters(self, output_msg):
        return output_msg.encode('utf-8').decode('ascii','ignore')
        
    def log_run_get_output(self, cmd, should_log=True):
        """
        Execute a command in a subshell
        :param str cmd: The command to be executed
        :param bool should_log: If true, log command execution
        :rtype: int, str
        :return: A tuple of (subshell exit code, contents of stdout)
        """
        if should_log:
            self.logger("RunCmd " + cmd)
        error, msg = waagent.RunGetOutput(cmd, chk_err=should_log)
        if should_log:
            self.logger("Return " + str(error) + ":" + msg)
        return int(error), self.filterNonAsciiCharacters(msg)

    def log_run_ignore_output(self, cmd, should_log=True):
        """
        Execute a command in a subshell
        :param str cmd: The command to be executed
        :param bool should_log: True if command execution should be logged. (False preserves privacy of parameters.)
        :rtype: int
        :return: The subshell exit code
        """
        error, msg = self.log_run_get_output(cmd, should_log)
        return int(error)

    def log_run_with_timeout(self, cmd, timeout=3600):
        """
        Execute a command in a subshell, killing the subshell if it runs too long
        :param str cmd: The command to be executed
        :param int timeout: The maximum elapsed time, in seconds, to wait for the subshell to return; default 360
        :rtype: int, str
        :return: (1, "Process timeout\n") if timeout, else (subshell exit code, contents of stdout)
        """
        self.logger("Run with timeout: " + cmd)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True,
                                   executable='/bin/bash')
        time.sleep(1)
        while process.poll() is None and timeout > 0:
            time.sleep(1)
            timeout -= 1
        if process.poll() is None:
            self.logger("Timeout while running:" + cmd)
            process.kill()
            return 1, "Process timeout\n"
        output, error = process.communicate()
        self.logger("Return " + str(error))
        return int(process.returncode), output

    def log_run_multiple_cmds(self, cmds, with_timeout, timeout=360):
        """
        Execute multiple commands in subshells, with optional timeout protection
        :param Iterable[str] cmds: An iterable of commands to be executed
        :param bool with_timeout: True if commands should be run with timeout
        :param int timeout: The timeout, in seconds; default 360. Ignored if with_timeout is False.
        :rtype: int, str
        :return: A tuple of (sum of status codes, concatenated stdout from commands)
        """
        errors = 0
        output = []
        for cmd in cmds:
            if with_timeout:
                err, msg = self.log_run_with_timeout(cmd, timeout)
            else:
                err, msg = self.log_run_get_output(cmd)
            errors += err
            output.append(msg)
        return errors, ''.join(output)

    def extract_om_path_and_version(self, results):
        """
        Get information about rsyslogd
        :param str results: Package information about omprog.so or version
        :rtype: str, str
        :return: (Path where rsyslogd output modules are installed, major version of rsyslogd)
        """
        match = re.search(r"(.+)omprog\.so", results)
        if not match:
            return None, ''
        path = match.group(1)
        match = re.search(r"Version\s*:\s*(\d+)\D", results)
        if not match:
            self.logger("rsyslog is present but version could not be determined")
            return None, ''
        version = match.group(1)
        return path, version

    def install_extra_packages(self, packages, with_timeout=False):
        """
        Ensure an arbitrary set of packages is installed
        :param list[str] packages: Iterable of package names
        :param bool with_timeout: true if package installations should be aborted if they take too long
        :rtype: int
        :return:
        """
        return 0, ''

    def install_required_packages(self):
        """
        Install packages required by this distro to meet the common bar required of all distros
        :rtype: int, str
        :return: (status, concatenated stdout from all package installs)
        """
        return 0, "no additional packages were needed"

    def is_package_handler(self, package_manager):
        """
        Checks if the distro's package manager matches the specified tool.
        :param str package_manager: The tool to be checked against the distro's native package manager
        :rtype: bool
        :return: True if the distro's native package manager is package_manager
        """
        return False

    def prepare_for_mdsd_install(self):
        return 0, ''

    def extend_environment(self, env):
        """
        Add required environment variables to process environment
        :param dict[str, str] env: Process environment
        """
        pass

    def use_systemd(self):
        """
        Determine if the distro uses systemd as its system management tool.
        :rtype: bool
        :return: True if the distro uses systemd as its system management tool.
        """
        return False

    def install_lad_mdsd(self):
        """
        Install the mdsd binary using the bundled .deb/.rpm packages.
        Should be overridden by each direct subclass for Debian/Redhat.
        Can't be called for this base class.
        :rtype: int, str
        :return: (status, concatenated stdout from the package install)
        """
        assert False, "Can't be called on the base class (CommonActions)!"

    def remove_lad_mdsd(self):
        """
        Remove the mdsd binary that was installed with the bundled .deb/.rpm packages.
        Should be overridden by each direct subclass for Debian/Redhat.
        Can't be called for this base class.
        :rtype: int, str
        :return: (status, concatenated stdout from the package remove)
        """
        assert False, "Can't be called on the base class (CommonActions)!"


class DebianActions(CommonActions):
    def __init__(self, logger):
        CommonActions.__init__(self, logger)

    def is_package_handler(self, package_manager):
        return package_manager == "dpkg"

    def install_extra_packages(self, packages, with_timeout=False):
        cmd = 'dpkg-query -l PACKAGE |grep ^ii; if [ ! $? == 0 ]; then apt-get update; apt-get install -y PACKAGE; fi'
        return self.log_run_multiple_cmds([cmd.replace("PACKAGE", p) for p in packages], with_timeout)

    def extend_environment(self, env):
        env.update({"SSL_CERT_DIR": "/usr/lib/ssl/certs", "SSL_CERT_FILE": "/usr/lib/ssl/cert.pem"})

    def install_lad_mdsd(self):
        return self.log_run_get_output('dpkg -i lad-mdsd-*.deb')

    def remove_lad_mdsd(self):
        return self.log_run_get_output('dpkg -P lad-mdsd')


class CredativActions(DebianActions):
    def __init__(self, logger):
        DebianActions.__init__(self, logger)

    def install_required_packages(self):
        # curl not installed by default on Credative Debian Linux, now required by omsagent
        return self.install_extra_packages(('curl',), True)


class Ubuntu1510OrHigherActions(DebianActions):
    def __init__(self, logger):
        DebianActions.__init__(self, logger)

    def install_extra_packages(self, packages, with_timeout=False):
        count = len(packages)
        if count == 0:
            return 0, ''
        package_list = str.join(' ', packages)
        cmd = '[ $(dpkg -l PACKAGES |grep ^ii |wc -l) -eq \'COUNT\' ] || apt-get install -y PACKAGES'
        cmd = cmd.replace('PACKAGES', package_list).replace('COUNT', str(count))
        if with_timeout:
            return self.log_run_with_timeout(cmd)
        else:
            return self.log_run_get_output(cmd)

    def use_systemd(self):
        return True


class RedhatActions(CommonActions):
    def __init__(self, logger):
        CommonActions.__init__(self, logger)

    def install_extra_packages(self, packages, with_timeout=False):
        install_cmd = 'rpm -q PACKAGE; if [ ! $? == 0 ]; then yum install -y PACKAGE; fi'
        return self.log_run_multiple_cmds([install_cmd.replace("PACKAGE", p) for p in packages], with_timeout)

    def install_required_packages(self):
        # policycoreutils-python missing on Oracle Linux (still needed to manipulate SELinux policy).
        # tar is really missing on Oracle Linux 7!
        return self.install_extra_packages(('policycoreutils-python', 'tar'), True)

    def is_package_handler(self, package_manager):
        return package_manager == "rpm"

    def extend_environment(self, env):
        env.update({"SSL_CERT_DIR": "/etc/pki/tls/certs", "SSL_CERT_FILE": "/etc/pki/tls/cert.pem"})

    def install_lad_mdsd(self):
        return self.log_run_get_output('rpm -i --force lad-mdsd-*.rpm')

    def remove_lad_mdsd(self):
        return self.log_run_get_output('rpm -e lad-mdsd')

class Redhat8Actions(RedhatActions):
    def __init__(self, logger):
        RedhatActions.__init__(self, logger)

    def install_required_packages(self):
        return self.install_extra_packages(('policycoreutils-python-utils', 'tar'), True)

class Suse11Actions(RedhatActions):
    def __init__(self, logger):
        RedhatActions.__init__(self, logger)
        self.certs_file = "/etc/ssl/certs/mdsd-ca-certs.pem"

    def install_extra_packages(self, packages, with_timeout=False):
        install_cmd = 'rpm -qi PACKAGE;  if [ ! $? == 0 ]; then zypper --non-interactive install PACKAGE;fi'
        return self.log_run_multiple_cmds([install_cmd.replace("PACKAGE", p) for p in packages], with_timeout)

    def install_required_packages(self):
        return 0, "no additional packages were needed"

    # For SUSE11, we need to create a CA certs file for our statically linked OpenSSL 1.0 libs
    def prepare_for_mdsd_install(self):
        commands = (
            r'cp /dev/null {0}'.format(self.certs_file),
            r'chown 0:0 {0}'.format(self.certs_file),
            r'chmod 0644 {0}'.format(self.certs_file),
            r"cat /etc/ssl/certs/????????.[0-9a-f] | sed '/^#/d' >> {0}".format(self.certs_file)
        )
        return self.log_run_multiple_cmds(commands, False)

    def extend_environment(self, env):
        env.update({"SSL_CERT_FILE": self.certs_file})


class Suse12Actions(RedhatActions):
    def __init__(self, logger):
        RedhatActions.__init__(self, logger)

    def install_extra_packages(self, packages, with_timeout=False):
        install_cmd = 'rpm -qi PACKAGE; if [ ! $? == 0 ]; then zypper --non-interactive install PACKAGE;fi'
        return self.log_run_multiple_cmds([install_cmd.replace("PACKAGE", p) for p in packages], with_timeout)

    def install_required_packages(self):
        return self.install_extra_packages(('libgthread-2_0-0', 'ca-certificates-mozilla', 'rsyslog'), True)

    def extend_environment(self, env):
        env.update({"SSL_CERT_DIR": "/var/lib/ca-certificates/openssl", "SSL_CERT_FILE": "/etc/ssl/cert.pem"})


class CentosActions(RedhatActions):
    def __init__(self, logger):
        RedhatActions.__init__(self, logger)

    def install_extra_packages(self, packages, with_timeout=False):
        install_cmd = 'rpm -qi PACKAGE; if [ ! $? == 0 ]; then yum install -y PACKAGE; fi'
        return self.log_run_multiple_cmds([install_cmd.replace("PACKAGE", p) for p in packages], with_timeout)

    def install_required_packages(self):
        # policycoreutils-python missing on CentOS (still needed to manipulate SELinux policy)
        return self.install_extra_packages(('policycoreutils-python',), True)


class Centos8Actions(RedhatActions):
    def __init__(self, logger):
        RedhatActions.__init__(self, logger)

    def install_required_packages(self):
        return self.install_extra_packages(('policycoreutils-python-utils', 'tar'), True)


DistroMap = {
    'debian': CredativActions,  # Credative Debian Linux took the 'debian' platform name with the curl deficiency,
                                # when all other Debian-based distros have curl, so is this strange mapping...
    'kali': DebianActions,
    'ubuntu': DebianActions,
    'ubuntu:16.04': Ubuntu1510OrHigherActions,
    'ubuntu:18.04': Ubuntu1510OrHigherActions,
    'redhat': RedhatActions,
    'redhat:8': Redhat8Actions,
    'centos': CentosActions,
    'centos:8':Centos8Actions,
    'oracle': RedhatActions,
    'suse:12': Suse12Actions,
    'suse': Suse12Actions,
    'sles:15': Suse12Actions,
    'opensuse:15':Suse12Actions,
    'almalinux':Redhat8Actions
}


def get_distro_actions(name, version, logger):
    name_and_version = name + ":" + version
    if name_and_version in DistroMap:
        return DistroMap[name_and_version](logger)
    else:
        major_version = version.split(".")[0]
        name_and_major_version = name + ":" + major_version
        if name_and_major_version in DistroMap:
            return DistroMap[name_and_major_version](logger)
        if name in DistroMap:
            return DistroMap[name](logger)
    raise exceptions.LookupError('{0} is not a supported distro'.format(name_and_version))
