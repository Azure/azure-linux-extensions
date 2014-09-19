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

class UbuntuInstaller(BaseInstaller):
    def __init__(self):
        super(UbuntuInstaller, self).__init__()

        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        self.update_cmd = 'apt-get update'
        self.install_cmd = 'apt-get -y -q --force-yes install'

        self.required_lib = ['build-essential', 'libcairo-dev', 'libpng-dev', 'libossp-uuid-dev']
        self.ssh_lib = ['libpango1.0-dev', 'libssh2-1', 'libssh2-1-dev', 'libssl-dev']
        self.rdp_lib = ['libfreerdp-dev']
        self.vnc_lib = ['libVNCServer-dev']
        self.telnet_lib = ['libtelnet-dev']
        self.other_lib = ['libpulse-dev', 'libvorbis', 'libogg-dev']
        self.ssh_libguac = ['libguac-client-ssh0']
        self.rdp_libguac = ['libguac-client-rdp0']

    def install_pkg(self, pkg):
        return waagent.Run(' '.join([self.install_cmd, pkg]))

    def stop_shellinabox(self):
        return waagent.Run('service shellinabox stop')
