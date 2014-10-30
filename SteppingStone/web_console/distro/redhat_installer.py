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

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util
from base_installer import BaseInstaller

class RedhatInstaller(BaseInstaller):
    def __init__(self):
        super(RedhatInstaller, self).__init__()

        self.install_cmd = 'yum -q -y install'

    def install_shellinabox(self):
        if waagent.Run('which shellinaboxd', False):
            self.install_pkg('openssl')
            self.install_pkg('shellinabox')

    def install_pkg(self, pkg):
        return waagent.Run(' '.join([self.install_cmd, pkg]))

    def stop_shellinabox(self):
        return waagent.Run('service shellinaboxd stop')

