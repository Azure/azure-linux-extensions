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
        retcode,output = waagent.RunGetOutput('cd '+self.cache_dir+';find . -name "updates"')
        self.download_dir = os.path.join(self.cache_dir, output.strip('.\n/') + '/packages')

    def parse_settings(self, settings):
        super(redhatPatching,self).parse_settings(settings)
        if self.category == 'Important':
            self.download_cmd = 'yum -q -y --downloadonly --security update'

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
            output = re.split(r'\s+', output.strip())
            self.to_download = zip(output[0::3], output[1::3])
            self.hutil.log("There are packages available for an update.")
        elif retcode == 1:
            self.hutil.error("Failed to check updates with error: " + output)

    def download(self):
        self.check()
        with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'w') as f:
            f.write('')
        for (pkg_name, pkg_version) in self.to_download:
            retcode = waagent.Run(self.download_cmd + ' ' + pkg_name, chk_err=False)
            # Yum exit code is not 0 even if succeed, so check if the package rpm exsits to verify that downloading succeeds.
            package = pkg_name.rpartition('.')[0] + '-' + pkg_version + '.' +  pkg_name.rpartition('.')[2] + '.rpm'
            if not os.path.isfile(os.path.join(self.download_dir, package)):
                self.hutil.error("Failed to download the package: " + pkg_name)
                continue
            self.downloaded.append(pkg_name)
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

    def reboot_if_required(self):
        """
        A reboot should be only necessary when kernel has been upgraded.
        """
        retcode,last_kernel = waagent.RunGetOutput("rpm -q --last kernel | perl -pe 's/^kernel-(\S+).*/$1/' | head -1")
        retcode,current_kernel = waagent.RunGetOutput('uname -r')
        if last_kernel != current_kernel:
            retcode = waagent.Run('reboot')
            if retcode > 0:
                self.hutil.error("Failed to reboot")

    def report(self):
        for package_patched in self.patched:
            retcode,output = waagent.RunGetOutput(self.status_cmd + ' ' + package_patched)
            self.hutil.log(output)
