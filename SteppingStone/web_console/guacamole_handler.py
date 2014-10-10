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
import socket

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

from settings import *
from distro import *
from no_auth import NoAuth

class GuacamoleHandler(object):
    def __init__(self, hutil):
        self.PROTOCOL_SUPPORT = ['SSH', 'VNC', 'RDP']

        self.hutil = hutil
        self.installer = get_installer()

        self.curdir = os.getcwd()
        if not os.path.isdir(ROOT_DIR):
            os.mkdir(ROOT_DIR)

    def get_web_console_uri(self, protocol='SSH'):
        host_name = socket.getfqdn(socket.gethostname())
        dns_name = host_name + AZURE_VM_DOMAIN
        web_console_uri = dns_name + ':8080/guacamole/client.xhtml?id=c%2FWEB%20' + protocol.upper()
        return web_console_uri

    def install(self, from_source=False):
        # TODO
        os.chdir(ROOT_DIR)
        if from_source:
            self.download_src()
            self.build_guacamole_server_from_source()
            self.build_guacamole_client_from_source()
        else:
            self.install_guacamole_from_packages(['ssh'])

    def enable(self):
        # TODO
        pass

    def install_guacamole_from_packages(self, category=[]):
        """
        By default, VNC support will be installed as a dependency of the guacamole package.
        if you want SSH or RDP support, you can set the parameter.
        Args:
            category - 'ssh', 'rdp'
        """
        self.hutil.log('Start to install guacamole from packages')
        waagent.Run('add-apt-repository -y ppa:guacamole/stable')
        retcode = self.installer.install_pkg('guacamole-tomcat')
        if retcode == 0:
            self.hutil.log('gucacmole-tomcat is installed')
        else:
            self.hutil.error('Failed to install guacamole-tomcat')
            sys.exit(1)
        #self.install_vnc()
        if 'ssh' in category:
            retcode_libssh = self.installer.install_pkg('libguac-client-ssh0')
            if retcode_libssh != 0:
                self.hutil.log('SSH is not supported')
        if 'rdp' in category:
            retcode_xrdp = self.installer.install_pkg('xrdp')
            retcode_librdp = self.installer.install_pkg('libguac-client-rdp0')
            if retcode_xrdp != 0 or retcode_librdp != 0:
                self.hutil.log('RDP is not supported')
        self.hutil.log('Installing guacamole: SUCCESS')

    def configure_auth(self):
        auth_handler = NoAuth()
        auth_handler.install_extension()
        auth_handler.configure()
        self.hutil.log('Configure auth: SUCCESS')

    # Install from source
    def download_src(self):
        guac_server_src = GUAC_SERVER_NAME + '-' + GUAC_VERSION + '.tar.gz'
        guac_client_src = GUAC_CLIENT_NAME + '-' + GUAC_VERSION + '.tar.gz'
        guac_client_war = GUAC_CLIENT_WAR_NAME[:-4] + '-' + GUAC_VERSION + GUAC_CLIENT_WAR_NAME[-4:]
        
        self.hutil.log('Downloading guacamole source into ' + ROOT_DIR)
        if not os.path.isdir(GUAC_SERVER_NAME):
            waagent.Run(' '.join(['wget --no-check-certificate', SRC_URI + guac_server_src]))
            waagent.Run(' '.join(['tar zxf', guac_server_src]))
            waagent.Run(' '.join(['rm -f', guac_server_src]))
            waagent.Run(' '.join(['ln -s', GUAC_SERVER_NAME + '-' + GUAC_VERSION, GUAC_SERVER_NAME]))
        if not os.path.isdir(GUAC_CLIENT_NAME):
            waagent.Run(' '.join(['wget --no-check-certificate', src_uri + guac_client_src]))
            waagent.Run(' '.join(['tar zxf', guac_client_src]))
            waagent.Run(' '.join(['rm -f', guac_client_src]))
            waagent.Run(' '.join(['ln -s', GUAC_CLIENT_NAME + '-' + GUAC_VERSION, GUAC_CLIENT_NAME]))
        if not os.path.isfile(GUAC_CLIENT_WAR_NAME):
            waagent.Run(' '.join(['wget --no-check-certificate', src_uri + guac_client_war]))
            waagent.Run(' '.join(['mv', guac_client_war, GUAC_CLIENT_WAR_NAME]))
        self.hutil.log('Guacamole source has been downloaded into ' + ROOT_DIR)

    def build_guacamole_server_from_source(self):
        self.install_lib()
        os.chdir(os.path.join(ROOT_DIR, GUAC_SERVER_NAME))
        self.hutil.log('Start to build guacamole server from source')
        retcode = waagent.Run('./configure --with-init-dir=/etc/init.d')
        if retcode != 0:
            self.hutil.error('Failed to configure guacamole')
            sys.exit(1)
        retcode = waagent.Run('make; make install; ldconfig')
        if retcode != 0:
            self.hutil.error('Failed to build guacamole')
            sys.exit(1)
        self.hutil.log('Building guacamole server: SUCCESS')
        self.restart_guacamole_server()
        os.chdir(ROOT_DIR)

    def build_guacamole_client_from_source(self):
        retcode = self.installer.install_pkg('tomcat7')
        if retcode != 0:
            sys.exit(1)
        os.chdir(os.path.join(ROOT_DIR, GUAC_CLIENT_NAME))
        self.hutil.log('Start to build guacamole client')
        # TODO
        self.hutil.log('Building guacamole client: SUCCESS')
        os.chdir(ROOT_DIR)

    def restart_guacamole_server(self):
        retcode = waagent.Run('service guacd restart')
        if retcode == 0:
            self.hutil.log('Restarting guacd: SUCCESS')
        else:
            self.hutil.error('Failed to restart guacamole server')
            sys.exit(1)

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
            retcode = self.install.install_pkg(lib_name)
            if retcode == 0:
                self.hutil.log('Installed library: ' + lib_name)
            else:
                self.hutil.error('Failed to install ' + lib_name)
                if lib_name in self.required_lib:
                    self.hutil.error('Can not build guacamole without the library' + lib_name)
                    sys.exit(1)
        self.hutil.log('Succeed in installing libraries to support ' + ' '.join(category))
