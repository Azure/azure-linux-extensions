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


class redhatPatching(AbstractPatching):
    def __init__(self):
        super(redhatPatching,self).__init__()
        #self.cron_restart_cmd = 'service crond restart'
        #self.check_cmd = 'yum -q check-update'
        #self.check_security_cmd = 'yum -q --security check-update'
        #self.clean_cmd = 'yum clean packages'
        #self.download_cmd = 'yum -q -y --downloadonly update'
        #self.patch_cmd = 'yum -y update'
        #self.status_cmd = 'yum -q info'
        #self.cache_dir = '/var/cache/yum/'
    def install_extras(self,paras):
        pass
    #def prepare(self):
    #    return super(redhatPatching, self).prepare()