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
        self.install_cmd = 'apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install'
        # Avoid a config prompt
        waagent.Run('DEBIAN_FRONTEND=noninteractive', False)
        print 'UbuntuInstaller'

    def install(self, lib_list):
        """Install libraries in order to build guacamole-server.
        Args:
            lib_list: a list of libraries to install.
        Returns:
            0 - Success.
            1 - Failure.
        Raises:
            None.
        """
        # Update source.list
        waagent.Run(self.update_cmd, False)

        for lib_name in lib_list:
            retcode = waagent.Run([self.install_cmd, lib_name])
            if retcode > 0:
                self.hutil.error('Failed to install ' + lib_name)
        print 'Succeed in installing lib'
