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


class SuSEPatching(AbstractPatching):
    def __init__(self, hutil):
        super(SuSEPatching,self).__init__(hutil)
        self.clean_cmd = 'zypper clean'
        self.check_cmd = 'zypper --non-interactive list-patches'
        self.download_cmd = 'zypper --non-interactive install -d --auto-agree-with-licenses -t patch '
        self.patch_cmd = 'zypper --non-interactive install --auto-agree-with-licenses -t patch '
    
    def parse_settings(self, settings):
        super(SuSEPatching, self).parse_settings(settings)
        if self.category == 'Important':
            self.check_cmd = self.check_cmd + ' --category security'
    
    def clean(self):
        """
        Clean local caches in /var/cache/zypp/packages.
        """
        retcode, output = waagent.RunGetOutput(self.clean_cmd)
        if retcode > 0:
            self.hutil.error("Failed to erase downloaded archive files")

    def check(self):
        """
        Check valid upgrades,
        Return the package list to upgrade
        """
        waagent.Run('zypper --non-interactive refresh', False)
        retcode, output = waagent.RunGetOutput(self.check_cmd)
        if retcode > 0:
            self.hutil.error("Faild to check valid upgrades")
        output_lines = output.split('\n')
        self.to_download = []
        name_position = 1
        for line in output_lines:
            properties = [elem.strip() for elem in line.split('|')]
            if len(properties) > 1:
                if 'Name' in properties:
                    name_position = properties.index('Name')
                elif not properties[name_position] in self.to_patch:
                    self.to_download.append(properties[name_position])
        if len(self.to_download) == 0:
            self.hutil.log("No package to upgrade")
            sys.exit(0)

    def download(self):
        #self.clean()
        self.check()
        self.downloaded = []
        with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'w') as f:
             f.write('')
        for package_to_download in self.to_download:
            retcode, output = waagent.RunGetOutput(self.download_cmd + package_to_download, False)
            self.downloaded.append(package_to_download)
            with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'a') as f:
                f.write(package_to_download + '\n')

    def patch(self):
        self.kill_exceeded_download()
        self.reboot_required = False
        start_patch_time = time.time()
        try:
            with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'r') as f:
                self.to_patch = [package_downloaded.strip() for package_downloaded in f.readlines()]
        except IOError, e:
            self.hutil.error("Failed to open package.downloaded with error: %s, \
                             stack trace: %s" %(str(e), traceback.format_exc()))
            self.to_patch = []
        for package_to_patch in self.to_patch:
            retcode, output = waagent.RunGetOutput(self.patch_cmd + package_to_patch, False)
            if output.find('Reboot as soon as possible.') != -1:
                self.reboot_required = True
            self.patched.append(package_to_patch)
            current_patch_time = time.time()
            if current_patch_time - start_patch_time > self.install_duration:
                self.hutil.log("Patching time exceeded. The pending package will be \
                                patch in the next cycle")
                break
        with open(os.path.join(waagent.LibDir, 'package.patched'), 'w') as f:
            for package_patched in self.patched:
                self.to_patch.remove(package_patched)
                f.write(package_patched + '\n')
        self.reboot_if_required()

    def patch_one_off(self):
        self.reboot_required = False
        start_patch_time = time.time()
        self.check()
        self.to_patch = self.to_download
        for package_to_patch in self.to_patch:
            retcode, output = waagent.RunGetOutput(self.patch_cmd + package_to_patch, False)
            if output.find('Reboot as soon as possible.') != -1:
                self.reboot_required = True
            self.patched.append(package_to_patch)
            current_patch_time = time.time()
            if current_patch_time - start_patch_time > self.install_duration:
                self.hutil.log("Patching time exceeded. The pending package will be \
                                patch in the next cycle")
                break
        with open(os.path.join(waagent.LibDir, 'package.patched'), 'w') as f:
            for package_patched in self.patched:
                self.to_patch.remove(package_patched)
                f.write(package_patched + '\n')
        self.reboot_if_required()

    def reboot_if_required(self):
        if self.reboot_required:
            retcode = waagent.Run('reboot')
            if retcode > 0:
                self.hutil.error("Failed to reboot")
