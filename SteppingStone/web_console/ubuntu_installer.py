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
import string
import random

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util
from base_installer import BaseInstaller

class UbuntuInstaller(BaseInstaller):
    def __init__(self, hutil):
        super(UbuntuInstaller, self).__init__(hutil)
        self.update_cmd = 'apt-get update'
        self.install_cmd = 'apt-get -y -q --force-yes install'
        self.required_lib = ['build-essential', 'libcairo-dev', 'libpng-dev', 'libossp-uuid-dev']
        self.ssh_lib = ['libpango1.0-dev', 'libssh2-1', 'libssh2-1-dev', 'libssl-dev']
        self.rdp_lib = ['libfreerdp-dev']
        self.vnc_lib = ['libVNCServer-dev']
        self.telnet_lib = ['libtelnet-dev']
        self.other_lib = ['libpulse-dev', 'libvorbis', 'libogg-dev']

        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        self.vnc_user = 'dev'

    def install_guacamole_from_packages(self, category=[]):
        """
        By default, VNC support will be installed as a dependency of the guacamole package.
        if you want SSH or RDP support, you can set the parameter.
        Args:
            category - 'ssh', 'rdp'
        """
        self.hutil.log('Start to install guacamole from packages')
        waagent.Run('add-apt-repository -y ppa:guacamole/stable')
        retcode = waagent.Run(' '.join([self.install_cmd, 'guacamole-tomcat']))
        if retcode == 0:
            self.hutil.log('gucacmole-tomcat is installed')
        else:
            self.hutil.error('Failed to install guacamole-tomcat')
            sys.exit(1)
        #self.install_vnc()
        if 'ssh' in category:
            retcode_libssh = self.install_pkg('libguac-client-ssh0')
            if retcode_libssh != 0:
                self.hutil.log('SSH is not supported')
        if 'rdp' in category:
            retcode_xrdp = self.install_pkg('xrdp')
            retcode_librdp = self.install_pkg('libguac-client-rdp0')
            if retcode_xrdp != 0 or retcode_librdp != 0:
                self.hutil.log('RDP is not supported')
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

    def install_vnc(self):
        vnc_passwd = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        waagent.Run('su - ' + self.vnc_user)
        import getpass
        print getpass.getuser()
        

    def install_pkg(self, pkg):
        retcode = waagent.Run(' '.join([self.install_cmd, pkg]))
        if retcode == 0:
            self.hutil.log(pkg + ' is installed')
        else:
            self.hutil.error('Failed to install ' + pkg)
        return retcode
