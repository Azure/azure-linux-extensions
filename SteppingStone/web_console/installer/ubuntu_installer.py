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
from base_installer import BaseInstaller

class UbuntuInstaller(BaseInstaller):
    def __init__(self, hutil):
        super(UbuntuInstaller, self).__init__(hutil)
        self.update_cmd = 'apt-get update'
        self.install_cmd = 'apt-get -y install'
        self.required_lib = ['build-essential', 'libcairo-dev', 'libpng-dev', 'libossp-uuid-dev']
        self.ssh_lib = ['libpango1.0-dev', 'libssh2-1', 'libssh2-1-dev', 'libssl-dev']
        self.rdp_lib = ['libfreerdp-dev']
        self.vnc_lib = ['libVNCServer-dev']
        self.telnet_lib = ['libtelnet-dev']
        self.other_lib = ['libpulse-dev', 'libvorbis', 'libogg-dev']

        print 'UbuntuInstaller'

    def install_guacamole_from_packages(self):
        # TODO
        self.hutil.log('Start to install guacamole from packages')
        waagent.Run('add-apt-repository -y ppa:guacamole/stable')
        retcode = waagent.Run(' '.join([self.install_cmd, 'guacamole-tomcat']))
        if retcode == 0:
            self.hutil.log('gucacmole-tomcat is installed')
        else:
            self.hutil.error('Failed to install guacamole-tomcat')
            sys.exit(1)                
        
        self.hutil.log('Installing guacamole: SUCCESS')

    def install_lib(self, category=['ssh']):
        """Install libraries in order to build guacamole-server.
        Args:
            category - 'telnet', 'ssh', 'vnc', 'rdp', 'all'
        """
        # Update source.list
        waagent.Run(self.update_cmd, False)

        lib_list = self.required_lib
        if 'all' in category:
            lib_list.extend(self.telnet_lib)
            lib_list.extend(self.ssh_lib)
            lib_list.extend(self.vnc_lib)
            lib_list.extend(self.rdp_lib)
            lib_list.extend(self.other_lib)
        else:
            if 'telnet' in category:
                lib_list.extend(self.telnet_lib)
            if 'ssh' in category:
                lib_list.extend(self.ssh_lib)
            if 'vnc' in category:
                lib_list.extend(self.vnc_lib)
            if 'rdp' in category:
                lib_list.extend(self.rdp_lib)
        for lib_name in lib_list:
            retcode = waagent.Run(' '.join([self.install_cmd, lib_name]))
            if retcode == 0:
                self.hutil.log('Installed library: ' + lib_name)
            else:
                self.hutil.error('Failed to install ' + lib_name)
                if lib_name in self.required_lib:
                    self.hutil.error('Can not build guacamole without the library' + lib_name)
                    sys.exit(1)
        self.hutil.log('Succeed in installing libraries to support ' + ' '.join(category))

    def install_tomcat(self):
        retcode = waagent.Run(' '.join([self.install_cmd, 'tomcat7']))
        if retcode == 0:
            self.hutil.log('Tomcat7 is installed')
        else:
            self.hutil.error('Failed to install tomcat7')
            sys.exit(1)                
