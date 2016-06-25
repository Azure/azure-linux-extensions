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

import re

from Utils.WAAgentUtil import waagent
from AbstractPatching import AbstractPatching


class redhatPatching(AbstractPatching):
    def __init__(self, hutil):
        super(redhatPatching,self).__init__(hutil)
        self.cron_restart_cmd = 'service crond restart'
        self.check_cmd = 'yum -q check-update'
        self.check_security_cmd = 'yum -q --security check-update'
        self.clean_cmd = 'yum clean packages'
        self.download_cmd = 'yum -q -y --downloadonly update'
        self.patch_cmd = 'yum -y update'
        self.status_cmd = 'yum -q info'
        self.pkg_query_cmd = 'repoquery -l'
        self.cache_dir = '/var/cache/yum/'

    def install(self):
        """
        Install for dependencies.
        """
        # For yum --downloadonly option
        waagent.Run('yum -y install yum-downloadonly', False)

        # For yum --security option
        retcode = waagent.Run('yum -y install yum-plugin-security')
        if retcode > 0:
            self.hutil.error("Failed to install yum-plugin-security")

        # For package-cleanup, needs-restarting, repoquery
        retcode = waagent.Run('yum -y install yum-utils')
        if retcode > 0:
            self.hutil.error("Failed to install yum-utils")

        # For lsof
        retcode = waagent.Run('yum -y install lsof')
        if retcode > 0:
            self.hutil.error("Failed to install lsof")

        # Install missing dependencies
        missing_dependency_list = self.check_missing_dependencies()
        for pkg in missing_dependency_list:
            retcode = waagent.Run('yum -y install ' + pkg)
            if retcode > 0:
                self.hutil.error("Failed to install missing dependency: " + pkg)

    def check(self, category):
        """
        Check valid upgrades,
        Return the package list to download & upgrade
        """
        if category == self.category_all:
            check_cmd = self.check_cmd
        elif category == self.category_required:
            check_cmd = self.check_security_cmd
        to_download = []
        retcode,output = waagent.RunGetOutput(check_cmd, chk_err=False)
        if retcode == 0:
            return 0, to_download
        elif retcode == 100:
            lines = output.strip().split('\n')
            for line in lines:
                line = re.split(r'\s+', line.strip())
                if len(line) != 3:
                    break
                to_download.append(line[0])
            return 0, to_download
        elif retcode == 1:
            return 1, to_download

    def download_package(self, package):
        retcode = waagent.Run(self.download_cmd + ' ' + package, chk_err=False)
        # Yum exit code is not 0 even if succeed, so check if the package rpm exsits to verify that downloading succeeds.
        return self.check_download(package)

    def patch_package(self, package):
        return waagent.Run(self.patch_cmd + ' ' + package)

    def check_reboot(self):
        retcode,last_kernel = waagent.RunGetOutput("rpm -q --last kernel")
        last_kernel = last_kernel.split()[0][7:]
        retcode,current_kernel = waagent.RunGetOutput('uname -r')
        current_kernel = current_kernel.strip()
        self.reboot_required = (last_kernel != current_kernel)

    def report(self):
        """
        TODO: Report the detail status of patching
        """
        for package_patched in self.patched:
            self.info_pkg(package_patched)

    def info_pkg(self, pkg_name):
        """
        Return details about a package        
        """
        retcode,output = waagent.RunGetOutput(self.status_cmd + ' ' + pkg_name)
        if retcode != 0:
            self.hutil.error(output)
            return None
        installed_pkg_info_list = output.rpartition('Available Packages')[0].strip().split('\n')
        available_pkg_info_list = output.rpartition('Available Packages')[-1].strip().split('\n')
        pkg_info = dict()
        pkg_info['installed'] = dict()
        pkg_info['available'] = dict()
        for item in installed_pkg_info_list:
            if item.startswith('Name'):
                pkg_info['installed']['name'] = item.split(':')[-1].strip()
            elif item.startswith('Arch'):
                pkg_info['installed']['arch'] = item.split(':')[-1].strip()
            elif item.startswith('Version'):
                pkg_info['installed']['version'] = item.split(':')[-1].strip()
            elif item.startswith('Release'):
                pkg_info['installed']['release'] = item.split(':')[-1].strip()
        for item in available_pkg_info_list:
            if item.startswith('Name'):
                pkg_info['available']['name'] = item.split(':')[-1].strip()
            elif item.startswith('Arch'):
                pkg_info['available']['arch'] = item.split(':')[-1].strip()
            elif item.startswith('Version'):
                pkg_info['available']['version'] = item.split(':')[-1].strip()
            elif item.startswith('Release'):
                pkg_info['available']['release'] = item.split(':')[-1].strip()
        return pkg_info

    def check_download(self, pkg_name):
        pkg_info = self.info_pkg(pkg_name)
        name = pkg_info['available']['name']
        arch = pkg_info['available']['arch']
        version = pkg_info['available']['version']
        release = pkg_info['available']['release']
        package = '.'.join(['-'.join([name, version, release]), arch, 'rpm'])
        retcode,output = waagent.RunGetOutput('cd ' + self.cache_dir + ';find . -name "'+ package + '"')
        if retcode != 0:
            self.hutil.error("Unable to check whether the downloading secceeds")
        else:
            if output == '':
                return 1
            else:
                return 0

    def check_missing_dependencies(self):
        retcode, output = waagent.RunGetOutput('package-cleanup --problems', chk_err=False)
        missing_dependency_list = []
        for line in output.split('\n'):
            if 'requires' not in line:
                continue
            words = line.split()
            missing_dependency = words[words.index('requires') + 1]
            if missing_dependency not in missing_dependency_list:
                missing_dependency_list.append(missing_dependency)
        return missing_dependency_list
