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

import sys
import time
sys.path.append('../patch')
from AbstractPatching import AbstractPatching

class FakePatching(AbstractPatching):
    def __init__(self, hutil=None):
        super(FakePatching,self).__init__(hutil)
        self.gap_between_stage = 20
        self.download_duration = 3600
        self.security_download_list = ['a', 'b', 'c', 'd', 'e']
        self.all_download_list = ['1', '2', '3', '4', 'a', 'b', 'c', 'd', 'e']

    def install(self):
        """
        Install for dependencies.
        """
        pass

    def check(self, category):
        """
        Check valid upgrades,
        Return the package list to download & upgrade
        """
        if category == 'Important':
            return 0, self.security_download_list
        else:
            return 0, self.all_download_list

    def download_package(self, package):
        time.sleep(11)
        return 0

    def patch_package(self, package):
        return 0

    def check_reboot(self):
        return False
