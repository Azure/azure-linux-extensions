#!/usr/bin/env python
#
# VM Backup extension
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
# Requires Python 2.7+
#

import inspect
import os
import sys

scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
transitionsdir = os.path.abspath(os.path.join(scriptdir, '../../transitions'))
sys.path.append(transitionsdir)

from transitions import *

class Matter(object):
    pass

lump = Matter()

machine = Machine(model=lump, states=['solid', 'liquid', 'gas', 'plasma'], initial='solid')

class OSEncryption(object):
    def __init__(self, hutil, distro_patcher, logger, encryption_environment):
        super(OSEncryption, self).__init__()

        self.hutil = hutil
        self.distro_patcher = distro_patcher
        self.logger = logger
        self.encryption_environment = encryption_environment

    def start_encryption(self):
        self.logger.log("Encrypting OS drive, machine state: {0}".format(lump.state))
