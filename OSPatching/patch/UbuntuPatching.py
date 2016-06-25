#!/usr/bin/python
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
import logging

from Utils.WAAgentUtil import waagent
from AbstractPatching import AbstractPatching

class UbuntuPatching(AbstractPatching):
    def __init__(self, hutil):
        super(UbuntuPatching,self).__init__(hutil)
        self.update_cmd = 'apt-get update'
        self.check_cmd = 'apt-get -qq -s upgrade'
        self.check_cmd_distupgrade = 'apt-get -qq -s dist-upgrade'
        self.check_security_suffix = ' -o Dir::Etc::SourceList=/etc/apt/security.sources.list'
        waagent.Run('grep "-security" /etc/apt/sources.list | sudo grep -v "#" > /etc/apt/security.sources.list')
        self.download_cmd = 'apt-get -d -y install'
        self.patch_cmd = 'apt-get -y -q --force-yes -o Dpkg::Options::="--force-confdef" install'
        self.fix_cmd = 'dpkg --configure -a --force-confdef'
        self.status_cmd = 'apt-cache show'
        self.pkg_query_cmd = 'dpkg-query -L'
        # Avoid a config prompt
        os.environ['DEBIAN_FRONTEND']='noninteractive'

    def install(self):
        """
        Install for dependencies.
        """
        # Update source.list
        waagent.Run(self.update_cmd, False)
        # /var/run/reboot-required is not created unless the update-notifier-common package is installed
        retcode = waagent.Run('apt-get -y install update-notifier-common')
        if retcode > 0:
            self.hutil.error("Failed to install update-notifier-common")

    def try_package_with_autofix(self, cmd):
        retcode, output = waagent.RunGetOutput(cmd)
        if retcode == 0:
            return retcode, output
        # An error occurred while running the command. Try to recover.
        # Unfortunately apt-get returns code 100 regardless of the error encountered, 
        # so we can't smartly detect the cause of failure
        self.log_and_syslog(logging.WARNING, "Error running command ({0}). Will try to correct package state ({1}). Error was {2}".format(cmd, self.fix_cmd, output))
        retcode, output = waagent.RunGetOutput(self.fix_cmd)
        if retcode != 0:
            self.log_and_syslog(logging.WARNING, "Error correcting package state ({0}). Error was {1}".format(self.fix_cmd, output))
        retcode, output = waagent.RunGetOutput(cmd)
        if retcode != 0:
            self.log_and_syslog(logging.WARNING, "Unable to run ({0}) on second attempt. Giving up. Error was {1}".format(cmd, output))
        return retcode, output

    def check(self, category):
        """
        Check valid upgrades,
        Return the package list to download & upgrade
        """
        # Perform upgrade or dist-upgrade as appropriate
        if self.dist_upgrade_all:
            self.log_and_syslog(logging.INFO, "Performing dist-upgrade for ALL packages")
            check_cmd = self.check_cmd_distupgrade
        else:
            check_cmd = self.check_cmd
        
        # If upgrading only required/security patches, append the command suffix
        # Otherwise, assume all packages will be upgraded
        if category == self.category_required:
            check_cmd = check_cmd + self.check_security_suffix
        retcode, output = self.try_package_with_autofix(check_cmd)
        
        to_download = [line.split()[1] for line in output.split('\n') if line.startswith('Inst')]

        # Azure repo assumes upgrade may have dependency changes
        if retcode != 0:
            self.log_and_syslog(logging.WARNING, "Failed to get list of upgradeable packages")
        elif self.is_string_none_or_empty(self.dist_upgrade_list):
            self.log_and_syslog(logging.INFO, "Dist upgrade list not specified, will perform normal patch")
        elif not os.path.isfile(self.dist_upgrade_list):
            self.log_and_syslog(logging.WARNING, "Dist upgrade list was specified but file [{0}] does not exist".format(self.dist_upgrade_list))
        else:
            self.log_and_syslog(logging.INFO, "Running dist-upgrade using {0}".format(self.dist_upgrade_list))
            self.check_azure_cmd = 'apt-get -qq -s dist-upgrade -o Dir::Etc::SourceList={0}'.format(self.dist_upgrade_list)
            retcode, azoutput = self.try_package_with_autofix(self.check_azure_cmd)
            azure_to_download = [line.split()[1] for line in azoutput.split('\n') if line.startswith('Inst')]
            to_download += list(set(azure_to_download) - set(to_download))

        return retcode, to_download
        
    def download_package(self, package):
        return waagent.Run(self.download_cmd + ' ' + package)

    def patch_package(self, package):
        retcode, output = self.try_package_with_autofix(self.patch_cmd + ' ' + package)
        return retcode

    def check_reboot(self):
        self.reboot_required = os.path.isfile('/var/run/reboot-required')

    def get_pkg_needs_restart(self):
        fd = '/var/run/reboot-required.pkgs'
        if not os.path.isfile(fd):
            return []
        return waagent.GetFileContents(fd).split('\n')

    def report(self):
        """
        TODO: Report the detail status of patching
        """
        for package_patched in self.patched:
            retcode,output = waagent.RunGetOutput(self.status_cmd + ' ' + package_patched)
            output = output.split('\n\n')[0]
            self.hutil.log(output)

