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
import re
import platform
import traceback

from patch.UbuntuPatching import UbuntuPatching
from patch.debianPatching import debianPatching
from patch.redhatPatching import redhatPatching
from patch.centosPatching import centosPatching
from patch.SuSEPatching import SuSEPatching
from patch.oraclePatching import oraclePatching
from patch.KaliPatching import KaliPatching
from patch.DefaultPatching import DefaultPatching
from patch.FreeBSDPatching import FreeBSDPatching
from patch.NSBSDPatching import NSBSDPatching

# Define the function in case waagent(<2.0.4) doesn't have DistInfo()
def DistInfo():
    try:
        if 'FreeBSD' in platform.system():
            release = re.sub('\-.*\Z', '', str(platform.release()))
            distinfo = ['FreeBSD', release]
            return distinfo
        if 'NS-BSD' in platform.system():
            release = re.sub('\-.*\Z', '', str(platform.release()))
            distinfo = ['NS-BSD', release]
            return distinfo
        if 'linux_distribution' in dir(platform):
            distinfo = list(platform.linux_distribution(full_distribution_name=0))
            # remove trailing whitespace in distro name
            if(distinfo[0] == ''):
                osfile= open("/etc/os-release", "r")
                for line in osfile:
                    lists=str(line).split("=")
                    if(lists[0]== "NAME"):
                        distname = lists[1].split("\"")
                        distinfo[0] = distname[1]
                        if(distinfo[0].lower() == "sles"):
                            distinfo[0] = "SuSE"
                osfile.close()
            distinfo[0] = distinfo[0].strip()
            return distinfo
        if 'Linux' in platform.system():
            if "ubuntu" in platform.version().lower():
                distinfo[0] = "Ubuntu"
            elif 'suse' in platform.version().lower():
                distinfo[0] = "SuSE"
            elif 'centos' in platform.version().lower():
                distinfo[0] = "centos"
            elif 'debian' in platform.version().lower():
                distinfo[0] = "debian"
            elif 'oracle' in platform.version().lower():
                distinfo[0] = "oracle"
            elif 'redhat' in platform.version().lower() or 'rhel' in platform.version().lower():
                distinfo[0] = "redhat"
            elif 'kali' in platform.version().lower():
                distinfo[0] = "Kali"
            else:
                distinfo[0] = "Default"
            return distinfo
        else:
            return platform.dist()
    except Exception as e:
        errMsg = 'Failed to retrieve the distinfo with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
        logger.log(errMsg)
        distinfo = ['Abstract','1.0']
        return distinfo

def GetMyPatching(logger):
    """
    Return MyPatching object.
    NOTE: Logging is not initialized at this point.
    """
    dist_info = DistInfo()
    if 'Linux' in platform.system():
        Distro = dist_info[0]
    else: # I know this is not Linux!
        if 'FreeBSD' in platform.system():
            Distro = platform.system()
        if 'NS-BSD' in platform.system():
            Distro = platform.system()
            Distro = Distro.replace("-", "")
    Distro = Distro.strip('"')
    Distro = Distro.strip(' ')
    orig_distro = Distro
    patching_class_name = Distro + 'Patching'
    if patching_class_name not in globals():
        if ('SuSE'.lower() in Distro.lower()):
            Distro = 'SuSE'
        elif ('Ubuntu'.lower() in Distro.lower()):
            Distro = 'Ubuntu'
        elif ('centos'.lower() in Distro.lower() or 'big-ip'.lower() in Distro.lower()):
            Distro = 'centos'
        elif ('debian'.lower() in Distro.lower()):
            Distro = 'debian'
        elif ('oracle'.lower() in Distro.lower()):
            Distro = 'oracle'
        elif ('redhat'.lower() in Distro.lower()):
            Distro = 'redhat'
        elif ("Kali".lower() in Distro.lower()):
            Distro = 'Kali'
        elif ('FreeBSD'.lower() in  Distro.lower() or 'gaia'.lower() in Distro.lower() or 'panos'.lower() in Distro.lower()):
            Distro = 'FreeBSD'
        else:
            Distro = 'Default'
        patching_class_name = Distro + 'Patching'
    patchingInstance = globals()[patching_class_name](logger,dist_info)
    return patchingInstance, patching_class_name, orig_distro
