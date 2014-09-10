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

class BaseInstaller(object):
    def __init__(self, hutil):
        self.hutil = hutil

        self.curdir = os.getcwd()
        self.ROOT_DIR = '/root/azuredata'
        if not os.path.isdir(self.ROOT_DIR):
            os.mkdir(self.ROOT_DIR)

        self.GUAC_VERSION = '0.9.2'
        self.GUAC_SERVER_NAME = 'guacamole-server'
        self.GUAC_CLIENT_NAME = 'guacamole-client'
        self.GUAC_CLIENT_WAR_NAME = 'guacamole.war'

        print "BaseInstaller"

    def install_guacamole(self, from_source=False):
        # TODO
        os.chdir(self.ROOT_DIR)
        if from_source:
            self.download_src()
            self.build_guacamole_server_from_source()
            self.build_guacamole_client_from_source()
        else:
            self.install_guacamole_from_packages()

    def download_src(self):
        src_uri = 'https://binxia.blob.core.windows.net/stepping-stones-services/'
        guac_server_src = self.GUAC_SERVER_NAME + '-' + self.GUAC_VERSION + '.tar.gz'
        guac_client_src = self.GUAC_CLIENT_NAME + '-' + self.GUAC_VERSION + '.tar.gz'
        guac_client_war = self.GUAC_CLIENT_WAR_NAME[:-4] + '-' + self.GUAC_VERSION + self.GUAC_CLIENT_WAR_NAME[-4:]
        
        self.hutil.log('Downloading guacamole source into ' + self.ROOT_DIR)
        if not os.path.isdir(self.GUAC_SERVER_NAME):
            waagent.Run(' '.join(['wget --no-check-certificate', src_uri + guac_server_src]))
            waagent.Run(' '.join(['tar zxf', guac_server_src]))
            waagent.Run(' '.join(['rm -f', guac_server_src]))
            waagent.Run(' '.join(['ln -s', self.GUAC_SERVER_NAME + '-' + self.GUAC_VERSION, self.GUAC_SERVER_NAME]))
        if not os.path.isdir(self.GUAC_CLIENT_NAME):
            waagent.Run(' '.join(['wget --no-check-certificate', src_uri + guac_client_src]))
            waagent.Run(' '.join(['tar zxf', guac_client_src]))
            waagent.Run(' '.join(['rm -f', guac_client_src]))
            waagent.Run(' '.join(['ln -s', self.GUAC_CLIENT_NAME + '-' + self.GUAC_VERSION, self.GUAC_CLIENT_NAME]))
        if not os.path.isfile(self.GUAC_CLIENT_WAR_NAME):
            waagent.Run(' '.join(['wget --no-check-certificate', src_uri + guac_client_war]))
            waagent.Run(' '.join(['mv', guac_client_war, self.GUAC_CLIENT_WAR_NAME]))
        self.hutil.log('Guacamole source has been downloaded into ' + self.ROOT_DIR)

    def build_guacamole_server_from_source(self):
        self.install_lib()
        os.chdir(os.path.join(self.ROOT_DIR, self.GUAC_SERVER_NAME))
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
        os.chdir(self.ROOT_DIR)

    def build_guacamole_client_from_source(self):
        self.install_tomcat()
        os.chdir(os.path.join(self.ROOT_DIR, self.GUAC_CLIENT_NAME))
        self.hutil.log('Start to build guacamole client')
        # TODO
        self.hutil.log('Building guacamole client: SUCCESS')
        os.chdir(self.ROOT_DIR)

    def install_guacamole_from_packages(self):
        pass

    def restart_guacamole_server(self):
        retcode = waagent.Run('service guacd restart')
        if retcode == 0:
            self.hutil.log('Restarting guacd: SUCCESS')
        else:
            self.hutil.error('Failed to restart guacamole server')
            sys.exit(1)
