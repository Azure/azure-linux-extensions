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
import sys
import shutil

from Utils.WAAgentUtil import waagent
from AbstractPatching import AbstractPatching


class SuSEPatching(AbstractPatching):
    def __init__(self, hutil):
        super(SuSEPatching,self).__init__(hutil)
        self.patched_pkgs = None
        self.cache_dir = os.path.join(os.path.dirname(sys.argv[0]), 'packages')
        if not os.path.isdir(self.cache_dir):
            os.mkdir(self.cache_dir)
        self.clean_cmd = 'zypper clean'
        self.check_cmd = 'zypper -q --gpg-auto-import-keys --non-interactive list-patches'
        self.check_security_cmd = self.check_cmd + ' --category security'
        self.download_cmd = 'zypper --non-interactive --pkg-cache-dir ' + self.cache_dir + ' install -d --auto-agree-with-licenses -t patch '
        self.patch_cmd = 'zypper --non-interactive --pkg-cache-dir ' + self.cache_dir + ' install --auto-agree-with-licenses -t patch '
        self.pkg_query_cmd = 'rpm -qlp'
        waagent.Run('zypper -q --gpg-auto-import-keys --non-interactive refresh', False)
    
    def check(self, category):
        """
        Check valid upgrades,
        Return the package list to upgrade
        """
        if category == self.category_all:
            check_cmd = self.check_cmd
        elif category == self.category_required:
            check_cmd = self.check_security_cmd
        retcode, output = waagent.RunGetOutput(check_cmd)
        output_lines = output.split('\n')
        patch_list = []
        name_position = 1
        for line in output_lines:
            properties = [elem.strip() for elem in line.split('|')]
            if len(properties) > 1:
                if 'Name' in properties:
                    name_position = properties.index('Name')
                elif not properties[name_position] in self.to_patch:
                    patch_list.append(properties[name_position])
        return retcode, patch_list

    def download_package(self, package):
        retcode = waagent.Run(self.download_cmd + package, False)
        if 0 < retcode and retcode < 100:
            return 1
        else:
            return 0

    def patch_package(self, package):
        if self.patched_pkgs == None:
            self.patched_pkgs = list()
            for root,dirs,files in os.walk(self.cache_dir):
                for filename in files:
                    if filename.endswith('rpm'):
                        shutil.copy(os.path.join(root, filename), "/tmp/")
                        self.patched_pkgs.append("/tmp/"+filename)
        retcode = waagent.Run(self.patch_cmd + package, False)
        if 0 < retcode and retcode < 100:
            return 1
        else:
            if retcode == 102:
                self.reboot_required = True
            return 0

    def check_reboot(self):
        pass

    def get_pkg_patched(self):
        return self.patched_pkgs
