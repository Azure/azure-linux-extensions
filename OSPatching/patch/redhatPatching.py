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
        self.check_security_cmd = 'yum -q --security check-update'
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

    def check(self, category):
        """
        Check valid upgrades,
        Return the package list to download & upgrade
        """
        self.hutil.log("Start to check patches (Category:" + category + ")")
        if category == self.category_all:
            check_cmd = self.check_cmd
        elif category == self.category_required:
            check_cmd = self.check_security_cmd
        to_download = []
        retcode,output = waagent.RunGetOutput(check_cmd, chk_err=False)
        if retcode == 0:
            self.hutil.log("No packages are available for update.")
            return to_download
        elif retcode == 100:
            lines = output.strip().split('\n')
            for line in lines:
                line = re.split(r'\s+', line.strip())
                if len(line) != 3:
                    break
                to_download.append(line[0])
            self.hutil.log("There are " + str(len(to_download)) + " packages to upgrade.")
            return to_download
        elif retcode == 1:
            self.hutil.error("Failed to check updates with error: " + output)
            sys.exit(1)

    def download(self):
        """
        Check any update.
        Download new updates.
        """
        if self.exists_stop_flag():
            self.hutil.log("Downloading patches is stopped/canceled")
            return
        waagent.SetFileContents(self.package_downloaded_path, '')
        waagent.SetFileContents(self.package_patched_path, '')
        # Installing security patches is mandatory
        self._download(self.category_required)
        if self.category == self.category_all:
            self._download(self.category_all)

    def _download(self, category):
        self.hutil.log("Start to check&download patches (Category:" + category + ")")
        pkg_to_download = self.check(category)
        for pkg_name in pkg_to_download:
            if pkg_name in self.downloaded:
                continue
            retcode = waagent.Run(self.download_cmd + ' ' + pkg_name, chk_err=False)
            # Yum exit code is not 0 even if succeed, so check if the package rpm exsits to verify that downloading succeeds.
            if not self.check_download(pkg_name):
                self.hutil.error("Failed to download the package: " + pkg_name)
                continue
            self.downloaded.append(pkg_name)
            self.hutil.log("Package " + pkg_name + " is downloaded.")
            waagent.AppendFileContents(self.package_downloaded_path, pkg_name + ' ' + category + '\n')

    def patch(self):
        """
        Check if downloading process exceeds. If yes, kill it. 
        Patch the downloaded package.
        The cache will be deleted automatically after installation.
        If the last patch installing time exceeds, it won't be killed. Just log.
        Reboot if the installed patch requires.
        """
        self.kill_exceeded_download()
        global start_patch_time
        start_patch_time = time.time()
        patchlist = get_pkg_to_patch(self.category_required)
        self._patch(self.category_required, patchlist)
        if not self.exists_stop_flag():
            self.hutil.log("Going to sleep for " + str(self.gap_between_stage) + "s")
            time.sleep(self.gap_between_stage)
            patchlist = get_pkg_to_patch(self.category_all)
            self._patch(self.category_all, patchlist)
        else:
            self.hutil.log("Installing patches (Category:" + self.category_all + ") is stopped/canceled")
        self.delete_stop_flag()
        #self.report()
        self.reboot_if_required()

    def _patch(self, category, patchlist):
        if self.exists_stop_flag():
            self.hutil.log("Installing patches (Category:" + category + ") is stopped/canceled")
            return
        if patchlist:
            self.hutil.log("Start to install patches (Category:" + category + ")")
        for package_to_patch in patchlist:
            current_patch_time = time.time()
            if current_patch_time - start_patch_time > self.install_duration:
                self.hutil.log("Patching time exceeded. The pending package will be \
                                patched in the next cycle")
                break
            retcode = waagent.Run(self.patch_cmd + ' ' + package_to_patch)
            if retcode > 0:
                self.hutil.error("Failed to patch the package:" + package_to_patch)
            else:
                self.patched.append(package_to_patch)
                self.hutil.log("Package " + package_to_patch + " is patched.")
                waagent.AppendFileContents(self.package_patched_path, package_to_patch + ' ' + category + '\n')

    def patch_one_off(self):
        """
        Called when startTime is empty string, which means a on-demand patch.
        """
        global start_patch_time
        start_patch_time = time.time()
        self.hutil.log("Going to patch one-off")
        waagent.SetFileContents(self.package_downloaded_path, '')
        waagent.SetFileContents(self.package_patched_path, '')
        patchlist = self.check(self.category_required)
        self._patch(self.category_required, patchlist)
        if not self.exists_stop_flag():
            self.hutil.log("Going to sleep for " + str(self.gap_between_stage) + "s")
            time.sleep(self.gap_between_stage)
            patchlist = self.check(self.category_all)
            self._patch(self.category_all, patchlist)
        else:
            self.hutil.log("Installing patches (Category:" + self.category_all + ") is stopped/canceled")
        shutil.copy2(self.package_patched_path, self.package_downloaded_path)
        self.delete_stop_flag()
        #self.report()
        self.reboot_if_required()

    def reboot_if_required(self):
        """
        In auto mode, a reboot should be only necessary when kernel has been upgraded.
        """
        if self.reboot_after_patch == 'NotRequired':
            return
        if self.reboot_after_patch == 'Required':
            self.hutil.log("System going to reboot...")
            retcode = waagent.Run('reboot')
            if retcode > 0:
                self.hutil.error("Failed to reboot")
        elif self.reboot_after_patch == 'Auto':
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

    def get_pkg_to_patch(self, category):
        patchlist = [line.split()[0] for line in waagent.GetFileContents(self.package_downloaded_path).split('\n') if line.endswith(category)]
        return patchlist
