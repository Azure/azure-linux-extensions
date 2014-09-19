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
# Requires Python 2.6+


import os
import sys
import json

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

from settings import *
from distro import *

from shellinabox_handler import ShellinaboxHandler
from guacamole_handler import GuacamoleHandler

class WebConsoleHandler(object):
    def __init__(self, hutil):
        self.WEB_CONSOLE_TOOL_SUPPORT = ['shellinabox', 'guacamole']
        if not os.path.isdir(ROOT_DIR):
            os.mkdir(ROOT_DIR)

        self.hutil = hutil
        self.installer = get_installer()

        self.current_config_list = list()
        self.web_console_tool = None
        self.is_stepping_stone = None
        self.tool_handler = None

    def parse_settings(self, settings):
        web_console_tool = settings.get('webConsoleTool')
        self.web_console_tool = web_console_tool if web_console_tool in self.WEB_CONSOLE_TOOL_SUPPORT else 'shellinabox'
        self.current_config_list.append('webConsoleTool=' + self.web_console_tool)
        self.tool_handler = globals()[self.web_console_tool.capitalize() + 'Handler'](self.hutil)

        self.is_stepping_stone = settings.get('isSteppingStone', False) 
        if type(self.is_stepping_stone) is str:
            if self.is_stepping_stone in ['True', 'true']:
                self.is_stepping_stone = True
            else:
                self.is_stepping_stone = False
        self.current_config_list.append('isSteppingStone=' + str(self.is_stepping_stone))

        if not self.is_stepping_stone:
            self.disable_ssl = settings.get('disableSSL', False)
            if type(self.disable_ssl) is str:
                if self.disable_ssl in ["True", 'true']:
                    self.disable_ssl = True
                else:
                    self.disable_ssl = False
            self.current_config_list.append('disableSSL=' + str(self.disable_ssl))

            self.port = settings.get('port', 4200)
            if type(self.port) is str:
                self.port = int(self.port)
            if self.port <= 1024:
                self.port = 4200
            self.current_config_list.append('port=' + str(self.port))
        else:
            self.connections = settings.get('connections', list())
            self.current_config_list.append(str(len(self.connections)) + ' connections: ' + json.dumps(self.connections))
        
        self.hutil.log(','.join(self.current_config_list))

    def install(self):
        self.tool_handler.install()

    def enable(self):
        if self.web_console_tool == 'guacamole':
            return
        if not self.is_stepping_stone:
            self.tool_handler.enable_local(self.disable_ssl, self.port)
        else:
            self.tool_handler.enable_stepping_stone(self.connections)

    def get_web_console_uri(self):
        return self.tool_handler.get_web_console_uri()
