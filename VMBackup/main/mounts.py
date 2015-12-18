#!/usr/bin/env python
#
# VM Backup extension
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
# Requires Python 2.7+
#

from os.path import *

import re
import sys
import subprocess
import types

from StringIO import StringIO

class Error(Exception):
    pass

class Mount:
    def __init__(self, name, type, fstype, mount_point):
        self.name = name
        self.type = type
        self.fstype = fstype
        self.mount_point = mount_point

class Mounts:
    def __init__(self,logger):
        self.mounts = []
        self.logger = logger

        p = subprocess.Popen(['lsblk', '-l', '-n','-o','NAME,TYPE,FSTYPE,MOUNTPOINT'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out_lsblk_output, err = p.communicate()
        out_lsblk_output = str(out_lsblk_output)
        self.logger.log(msg="out_lsblk_output:\n" + str(out_lsblk_output),local=True)
        lines = out_lsblk_output.splitlines()
        line_number = len(lines)
        for i in range(0,line_number):
            item_value = lines[i].strip().split()
            print("item_value==" + str(item_value))
            name = item_value[0]
            type = item_value[1]
            fstype = ""
            mountpoint = ""
            if(len(item_value) > 2):
                fstype = item_value[2]
            if(len(item_value) > 3):
                mountpoint = item_value[3]
            mount = Mount(item_value[0], item_value[1], fstype, mountpoint)
            self.mounts.append(mount)
