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
#
# Requires Python 2.4+


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
import datetime

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util
from AbstractPatching import AbstractPatching


class redhatPatching(AbstractPatching):
    def __init__(self, hutil):
        super(redhatPatching,self).__init__(hutil)
        self.cron_restart_cmd = 'service crond restart'
        self.check_cmd = 'yum -q check-update'
        self.clean_cmd = 'yum clean packages'
        self.download_cmd = 'yum -q -y --downloadonly update'
        self.patch_cmd = 'yum -y update'
        self.status_cmd = 'yum -q info'
        self.cache_dir = '/var/cache/yum/'

    def parse_settings(self, settings):
        """
        Category is specific in each distro.
        TODO:
            Refactor this method if more category is added.
        """
        super(redhatPatching,self).parse_settings(settings)
        if self.category == 'Important':
            self.check_cmd = 'yum -q --security check-update'

    def check(self):
        """
        Check valid upgrades,
        Return the package list to download & upgrade
        """
        retcode,output = waagent.RunGetOutput(self.check_cmd, chk_err=False)
        if retcode == 0:
            self.to_download = []
            self.hutil.log("No packages are available for update.")
        elif retcode == 100:
            lines = output.strip().split('\n')
            for line in lines:
                line = re.split(r'\s+', line.strip())
                if len(line) != 3:
                    break
                self.to_download.append(line[0])
            self.hutil.log("There are packages available for an update.")
            self.hutil.log("There are " + str(len(self.to_download)) + " packages to upgrade.")
        elif retcode == 1:
            self.hutil.error("Failed to check updates with error: " + output)

    def download(self):
        """
        Check any update.
        Download new updates.
        """
        self.check()
        with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'w') as f:
            f.write('')
        for pkg_name in self.to_download:
            retcode = waagent.Run(self.download_cmd + ' ' + pkg_name, chk_err=False)
            # Yum exit code is not 0 even if succeed, so check if the package rpm exsits to verify that downloading succeeds.
            if not self.check_download(pkg_name):
                self.hutil.error("Failed to download the package: " + pkg_name)
                continue
            self.downloaded.append(pkg_name)
            self.hutil.log("Package " + pkg_name + " is downloaded.")
            with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'a') as f:
                f.write(pkg_name + '\n')

    def install(self):
        """
        Install for dependencies.
        """
        # For yum --downloadonly option
        retcode = waagent.Run('yum -y install yum-downloadonly')
        if retcode > 0:
            self.hutil.error("Failed to install yum-downloadonly")

        # For yum --security option
        retcode = waagent.Run('yum -y install yum-plugin-security')
        if retcode > 0:
            self.hutil.error("Failed to install yum-plugin-security")

    def patch(self):
        """
        Check if downloading process exceeds. If yes, kill it. 
        Patch the downloaded package.
        The cache will be deleted automatically after installation.
        If the last patch installing time exceeds, it won't be killed. Just log.
        Reboot if the installed patch requires.
        """
        self.kill_exceeded_download()
        start_patch_time = time.time()
        try:
            with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'r') as f:
                self.to_patch = [package_downloaded.strip() for package_downloaded in f.readlines()]
        except IOError, e:
            self.hutil.error("Failed to open package.downloaded with error: %s, \
                             stack trace: %s" %(str(e), traceback.format_exc()))
            self.to_patch = []
        for package_to_patch in self.to_patch:
            retcode = waagent.Run(self.patch_cmd + ' ' + package_to_patch)
            if retcode > 0:
                self.hutil.error("Failed to patch the package:" + package_to_patch)
            else:
                self.patched.append(package_to_patch)
                self.hutil.log("Package " + package_to_patch + " is patched.")
            current_patch_time = time.time()
            if current_patch_time - start_patch_time > self.install_duration:
                self.hutil.log("Patching time exceeded. The pending package will be \
                                patched in the next cycle")
                break
        with open(os.path.join(waagent.LibDir, 'package.patched'), 'w') as f:
            for package_patched in self.patched:
                f.write(package_patched + '\n')
        #self.report()
        self.reboot_if_required()

    def patch_one_off(self):
        """
        Called when startTime is empty string, which means a on-demand patch.
        """
        self.hutil.log("Going to patch one-off")
        start_patch_time = time.time()
        self.check()
        self.to_patch = self.to_download
        for package_to_patch in self.to_patch:
            retcode = waagent.Run(self.patch_cmd + ' ' + package_to_patch)
            if retcode > 0:
                self.hutil.error("Failed to patch the package:" + package_to_patch)
            else:
                self.downloaded.append(package_to_patch)
                self.patched.append(package_to_patch)
                self.hutil.log("Package " + package_to_patch + " is patched.")
            current_patch_time = time.time()
            if current_patch_time - start_patch_time > self.install_duration:
                self.hutil.log("Patching time exceeded. The pending package will be \
                                patched in the next cycle")
                break
        with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'w') as f:
            for package_downloaded in self.downloaded:
                f.write(package_downloaded + '\n')
        with open(os.path.join(waagent.LibDir, 'package.patched'), 'w') as f:
            for package_patched in self.patched:
                f.write(package_patched + '\n')
        # self.report()
        self.reboot_if_required()

    def reboot_if_required(self):
        """
        A reboot should be only necessary when kernel has been upgraded.
        TODO:
            Set reboot an option ???
        """
        retcode,last_kernel = waagent.RunGetOutput("rpm -q --last kernel | perl -pe 's/^kernel-(\S+).*/$1/' | head -1")
        retcode,current_kernel = waagent.RunGetOutput('uname -r')
        if last_kernel != current_kernel:
            self.hutil.log("System going to reboot...")
            retcode = waagent.Run('reboot')
            if retcode > 0:
                self.hutil.error("Failed to reboot")

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
                return False
            else:
                return True
