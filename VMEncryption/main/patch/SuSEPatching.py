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
from AbstractPatching import AbstractPatching


class SuSEPatching(AbstractPatching):
    def __init__(self):
        super(SuSEPatching,self).__init__()
        #self.clean_cmd = 'zypper clean'
        #self.check_cmd = 'zypper -q --gpg-auto-import-keys --non-interactive list-patches'
        #self.check_security_cmd = self.check_cmd + ' --category security'
        #self.download_cmd = 'zypper --non-interactive install -d --auto-agree-with-licenses -t patch '
        #self.patch_cmd = 'zypper --non-interactive install --auto-agree-with-licenses -t patch '
        #self.reboot_required = False
        #waagent.Run('zypper -q --gpg-auto-import-keys --non-interactive refresh', False)
    def install_extras(self):
        pass