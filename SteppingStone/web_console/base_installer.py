#!/usr/bin/python
#
# AbstractPatching is the base patching class of all the linux distros
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

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

from settings import *
from no_auth import NoAuth

class BaseInstaller(object):
    def __init__(self, hutil):
        self.hutil = hutil

        self.curdir = os.getcwd()
        if not os.path.isdir(ROOT_DIR):
            os.mkdir(ROOT_DIR)


    def install_guacamole(self, from_source=False):
        # TODO
        os.chdir(ROOT_DIR)
        if from_source:
            self.download_src()
            self.build_guacamole_server_from_source()
            self.build_guacamole_client_from_source()
        else:
            self.install_guacamole_from_packages()

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
        retcode = install_pkg('tomcat7')
        if retcode != 0:
            sys.exit(1)
        os.chdir(os.path.join(ROOT_DIR, GUAC_CLIENT_NAME))
        self.hutil.log('Start to build guacamole client')
        # TODO
        self.hutil.log('Building guacamole client: SUCCESS')
        os.chdir(ROOT_DIR)

    def install_guacamole_from_packages(self):
        pass

    def restart_guacamole_server(self):
        retcode = waagent.Run('service guacd restart')
        if retcode == 0:
            self.hutil.log('Restarting guacd: SUCCESS')
        else:
            self.hutil.error('Failed to restart guacamole server')
            sys.exit(1)

    def configure_auth(self):
        auth_handler = NoAuth()
        auth_handler.install_extension()
        auth_handler.configure()
        self.hutil.log('Configure auth: SUCCESS')
        
