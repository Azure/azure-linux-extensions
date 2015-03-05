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
import subprocess
from AbstractPatching import AbstractPatching


class SuSEPatching(AbstractPatching):
    def __init__(self):
        super(SuSEPatching,self).__init__()

    def install_extras(self,paras):
        print("installing in suse")
        if(paras.command == "disk"):
            p = subprocess.Popen(["rescan-scsi-bus.sh"])
            common_extras = ['cryptsetup-bin','lsscsi']
            for extra in common_extras:
                print("installation for " + extra + 'result is ' + str(subprocess.call(['zypper', 'install','-l', extra])))

            if(paras.filesystem == "btrfs"):
                extras = ['btrfs-tools']
                for extra in extras:
                    print("installation for " + extra + 'result is ' + str(subprocess.call(['zypper', 'install','-l', extra])))
            pass

        elif(paras.command == "folder"):
            common_extras = ['ecryptfs-utils']
            for extra in common_extras:
                    print("installation for " + extra + 'result is ' + str(subprocess.call(['zypper', 'install','-l', extra])))