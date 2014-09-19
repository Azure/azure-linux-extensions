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

import platform

from Utils.WAAgentUtil import waagent
from ubuntu_installer import UbuntuInstaller

def get_installer():
    """
    Returns:
        distro-based installer object.
    """
    if 'Linux' in platform.system():
        distro = waagent.DistInfo()[0]
    else: # I know this is not Linux!
        if 'FreeBSD' in platform.system():
            distro = platform.system()
    distro = distro.strip('"').strip().capitalize()
    installer_name = distro + 'Installer'
    if not globals().has_key(installer_name):
        return None
    return globals()[installer_name]()

