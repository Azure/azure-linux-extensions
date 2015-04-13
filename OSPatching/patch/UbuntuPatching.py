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
        self.update_cmd = 'apt-get update'
        self.check_cmd = 'apt-get -qq -s upgrade'
        waagent.Run('grep "-security" /etc/apt/sources.list | sudo grep -v "#" > /etc/apt/security.sources.list')
        self.check_security_cmd = self.check_cmd + ' -o Dir::Etc::SourceList=/etc/apt/security.sources.list'
        self.download_cmd = 'apt-get -d -y install'
        self.patch_cmd = 'apt-get -y -q --force-yes install'
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

    def check(self, category):
        """
        Check valid upgrades,
        Return the package list to download & upgrade
        """
        if category == self.category_all:
            check_cmd = self.check_cmd
        elif category == self.category_required:
            check_cmd = self.check_security_cmd
        retcode, output = waagent.RunGetOutput(check_cmd)
        to_download = [line.split()[1] for line in output.split('\n') if line.startswith('Inst')]
        return retcode, to_download

    def download_package(self, package):
        return waagent.Run(self.download_cmd + ' ' + package)

    def patch_package(self, package):
        return waagent.Run(self.patch_cmd + ' ' + package)

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
