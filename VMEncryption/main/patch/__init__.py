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

from .UbuntuPatching import UbuntuPatching
from .debianPatching import debianPatching
from .redhatPatching import redhatPatching
from .centosPatching import centosPatching
from .SuSEPatching import SuSEPatching
from .oraclePatching import oraclePatching
from .marinerPatching import marinerPatching

try:
    import distro # python3.8+
except:
    pass

def get_linux_distribution():
    """Abstract platform.linux_distribution() call which is deprecated as of
       Python 3.5 and removed in Python 3.7"""

    try:
        osinfo = list(platform.linux_distribution(full_distribution_name=False))
    except AttributeError:
        osinfo = list(distro.linux_distribution(full_distribution_name=False))

    return osinfo

def DistInfo(fullname=0):
    if 'FreeBSD' in platform.system():
        release = re.sub('\-.*\Z', '', str(platform.release()))
        distinfo = ['FreeBSD', release]
        return distinfo

    if 'linux_distribution' in dir(platform):
        distinfo = list(get_linux_distribution())
        distinfo[0] = distinfo[0].strip()  # remove trailing whitespace in distro name
        if not distinfo[0]:
            distinfo = dist_info_SLES15()
        if not distinfo[0]:
            distinfo = dist_info_opensuse15()
        return distinfo
    else:
        return get_linux_distribution()

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
    Distro = Distro.replace('ubuntu','Ubuntu') # to upper if needed

    patching_class_name = Distro + 'Patching'

    if patching_class_name not in globals():
        logger.log('{0} is not a supported distribution.'.format(Distro))
        return None
    patchingInstance = globals()[patching_class_name](logger, dist_info)
    return patchingInstance
