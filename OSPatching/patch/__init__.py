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
import re
import platform

from UbuntuPatching import UbuntuPatching
from redhatPatching import redhatPatching
from centosPatching import centosPatching
from OraclePatching import OraclePatching
from SuSEPatching import SuSEPatching

# Define the function in case waagent(<2.0.4) doesn't have DistInfo()
def DistInfo(fullname=0):
    if 'FreeBSD' in platform.system():
        release = re.sub('\-.*\Z', '', str(platform.release()))
        distinfo = ['FreeBSD', release]
        return distinfo
    if os.path.isfile('/etc/oracle-release'):
        release = re.sub('\-.*\Z', '', str(platform.release()))
        distinfo = ['Oracle', release]
        return distinfo
    if 'linux_distribution' in dir(platform):
        distinfo = list(platform.linux_distribution(\
                        full_distribution_name=fullname))
        # remove trailing whitespace in distro name
        distinfo[0] = distinfo[0].strip()
        return distinfo
    else:
        return platform.dist()

def GetMyPatching(hutil, patching_class_name=''):
    """
    Return MyPatching object.
    NOTE: Logging is not initialized at this point.
    """
    if patching_class_name == '':
        if 'Linux' in platform.system():
            Distro = DistInfo()[0]
        else: # I know this is not Linux!
            if 'FreeBSD' in platform.system():
                Distro = platform.system()
        Distro = Distro.strip('"')
        Distro = Distro.strip(' ')
        patching_class_name = Distro + 'Patching'
    else:
        Distro = patching_class_name
    if not globals().has_key(patching_class_name):
        hutil.log_and_syslog(Distro + ' is not a supported distribution.')
        return None
    return globals()[patching_class_name](hutil)
