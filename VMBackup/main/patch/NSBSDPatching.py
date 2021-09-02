#!/usr/bin/python
#
# Copyright 2015 Microsoft Corporation
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
import base64
import re
import json
import platform
import shutil
import time
import traceback
import datetime
import subprocess
from patch.AbstractPatching import AbstractPatching
from common import *


class NSBSDPatching(AbstractPatching):

    resolver = None

    def __init__(self,logger,distro_info):
        super(NSBSDPatching,self).__init__(distro_info)
        self.logger = logger
        self.usr_flag = 0
        self.mount_path = '/sbin/mount'

        try:
            import dns.resolver
        except ImportError:
            raise Exception("Python DNS resolver not available. Cannot proceed!")
        self.resolver = dns.resolver.Resolver()
        servers = []
        getconf_cmd = "/usr/Firewall/sbin/getconf /usr/Firewall/ConfigFiles/dns Servers | tail -n +2"
        getconf_p = subprocess.Popen(getconf_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        output, _ = getconf_p.communicate()
        output = str(output)

        for server in output.split("\n"):
            if server == '':
                break
            server = server[:-1] # remove last '='
            grep_cmd = "/usr/bin/grep '{}' /etc/hosts".format(server) + " | awk '{print $1}'"
            grep_p = subprocess.Popen(grep_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            ip, _ = grep_p.communicate()
            ip = str(ip).rstrip()
            servers.append(ip)
        self.resolver.nameservers = servers
        dns.resolver.override_system_resolver(self.resolver)

    def install_extras(self):
        pass
