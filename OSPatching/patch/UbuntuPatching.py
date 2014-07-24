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

class UbuntuPatching(AbstractPatching):
    def __init__(self, hutil):
        super(UbuntuPatching,self).__init__(hutil)
        self.clean_cmd = 'apt-get clean'
        self.check_cmd = 'apt-get -s upgrade'
        self.download_cmd = 'apt-get -d -y install'
        self.patch_cmd = 'apt-get -y install'
        self.status_cmd = 'apt-cache show'

    def parse_settings(self, settings):
        super(UbuntuPatching,self).parse_settings(settings)
        if self.category == 'Important':
            waagent.Run('grep "-security" /etc/apt/sources.list | sudo grep -v "#" > /etc/apt/security.sources.list')
            self.download_cmd = self.download_cmd + ' -o Dir::Etc::SourceList=/etc/apt/security.sources.list'

    def check(self):
        """
        Check valid upgrades,
        Return the package list to download & upgrade
        """
        retcode,output = waagent.RunGetOutput(self.check_cmd)
        if retcode > 0:
            self.hutil.error("Failed to check valid upgrades")
        start = output.find('The following packages will be upgraded')
        if start == -1:
            self.hutil.log("No package to upgrade")
            sys.exit(0)
        start = output.find('\n', start)
        end = output.find('upgraded', start)
        output = re.split(r'\s+', output[start:end].strip())
        output.pop()
        self.to_download = output

    def clean(self):
        retcode,output = waagent.RunGetOutput(self.clean_cmd)
        if retcode > 0:
            self.hutil.error("Failed to erase downloaded archive files")

    def download(self):
        while True:
            pass
        self.check()
        self.clean()
        with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'w') as f:
            f.write('')
        for package_to_download in self.to_download:
            retcode = waagent.Run(self.download_cmd + ' ' + package_to_download)
            if retcode > 0:
                self.hutil.error("Failed to download the package: " + package_to_download)
                continue
            self.downloaded.append(package_to_download)
            with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'a') as f:
                 f.write(package_to_download + '\n')

    def reboot_if_required(self):
        reboot_required = '/var/run/reboot-required'
        if os.path.isfile(reboot_required):
            retcode = waagent.Run('reboot')
            if retcode > 0:
                self.hutil.error("Failed to reboot")

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
        # TODO: Report the detail status of patching
        # self.report()
        self.reboot_if_required()

    def patch_one_off(self):
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
        # TODO: Report the detail status of patching
        # self.report()
        self.reboot_if_required()

    def report(self):
        for package_patched in self.patched:
            retcode,output = waagent.RunGetOutput(self.status_cmd + ' ' + package_patched)
            output = output.split('\n\n')[0]
            self.hutil.log(output)

    def install(self):
        """
        Install for dependencies.
        """
        # /var/run/reboot-required is not created unless the update-notifier-common package is installed
        retcode = waagent.Run('apt-get -y install update-notifier-common')
        if retcode > 0:
            self.hutil.error("Failed to install update-notifier-common")
