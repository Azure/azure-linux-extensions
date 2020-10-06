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

from UbuntuPatching import UbuntuPatching
from debianPatching import debianPatching
from redhatPatching import redhatPatching
from centosPatching import centosPatching
from SuSEPatching import SuSEPatching
from oraclePatching import oraclePatching


def _suse_parse_os_release_file():
    """
    Useful for SUSE15 distro that uses "/etc/os-release" file and when
    the Python "platform" packages fails to return the proper distro
    identification.
    The Python "platform" package has been deprecated in future python 3.7+ releases.
    A generic solution for all distributions will need to be implemented
    at that time.
    """
    try:
        with open("/etc/os-release") as f:
            os_release = {}
            for line in f:
                k,v = line.rstrip().split("=")
                os_release[k] = v.strip('" ')

        if os_release['NAME'].lower() == 'sles':
            return ['SuSE', os_release['VERSION'], '']

    except:
        # ignore all errors and return empty list
        return ['','','']


# Define the function in case waagent(<2.0.4) doesn't have DistInfo()
def DistInfo():
    if 'FreeBSD' in platform.system():
        release = re.sub('\-.*\Z', '', str(platform.release()))
        distinfo = ['FreeBSD', release]
        return distinfo
    if 'linux_distribution' in dir(platform):
        distinfo = list(platform.linux_distribution(full_distribution_name=0))
        # remove trailing whitespace in distro name
        distinfo[0] = distinfo[0].strip()
        if distinfo[0] == '':
            # Unable to resolve the distro name using the python "platform" package...
            # this might be a SLES15+ image which uses a "/etc/os-release"
            # file instead.
            # The Python "platform" package has been deprecated in future python 3.7+ releases.
            # A generic solution for all distributions will need to be implemented
            # at that time.
            distinfo = _suse_parse_os_release_file()
            if distinfo[0].lower() == 'suse':
                distinfo[0] = 'SuSE'

        return distinfo
    else:
        return platform.dist()

def GetDistroPatcher(logger):
    """
    Return DistroPatcher object.
    NOTE: Logging is not initialized at this point.
    """
    dist_info = DistInfo()
    if 'Linux' in platform.system():
        Distro = dist_info[0]
    else: # I know this is not Linux!
        if 'FreeBSD' in platform.system():
            Distro = platform.system()
    Distro = Distro.strip('"')
    Distro = Distro.strip(' ')
    patching_class_name = Distro + 'Patching'

    if not globals().has_key(patching_class_name):
        logger.log('{0} is not a supported distribution.'.format(Distro))
        return None
    patchingInstance = globals()[patching_class_name](logger, dist_info)
    return patchingInstance