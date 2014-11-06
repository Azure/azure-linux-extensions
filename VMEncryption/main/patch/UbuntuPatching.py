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

from AbstractPatching import AbstractPatching
import subprocess

class UbuntuPatching(AbstractPatching):
    def __init__(self):
        super(UbuntuPatching,self).__init__()
        #self.update_cmd = 'apt-get update'
        #self.check_cmd = 'apt-get -qq -s upgrade'
        #waagent.Run('grep "-security" /etc/apt/sources.list | sudo grep -v "#" > /etc/apt/security.sources.list')
        #self.check_security_cmd = self.check_cmd + ' -o Dir::Etc::SourceList=/etc/apt/security.sources.list'
        #self.download_cmd = 'apt-get -d -y install'
        #self.patch_cmd = 'apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install'
        #self.status_cmd = 'apt-cache show'
        ## Avoid a config prompt
        #waagent.Run("DEBIAN_FRONTEND=noninteractive", False)
    def install_extras(self):
        print("installing in ubuntu")
        for extra in self.extras:
            print("installation for "+extra +'result is '+str(subprocess.call(['apt-get', 'install','-y', extra])))