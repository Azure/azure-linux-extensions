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
import traceback
from time import sleep

scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
maindir = os.path.abspath(os.path.join(scriptdir, '../'))
sys.path.append(maindir)
transitionsdir = os.path.abspath(os.path.join(scriptdir, '../../transitions'))
sys.path.append(transitionsdir)

from OSEncryptionState import *
from Common import *
from CommandExecutor import *
from DiskUtil import *

import logging

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

logging.getLogger(__name__).addHandler(NullHandler())
logging.NullHandler = NullHandler

from transitions import *

class OSEncryptionStateMachine(object):
    states = [
        State(name='uninitialized'),
        State(name='completed')
    ]

    transitions = [
        {
            'trigger': 'skip_encryption',
            'source': 'uninitialized',
            'dest': 'completed'
        }
    ]

    def on_enter_state(self):
        self.state_objs[self.state].enter()

    def should_exit_previous_state(self):
        # when this is called, self.state is still the "source" state in the transition
        return self.state_objs[self.state].should_exit()

    def __init__(self, hutil, distro_patcher, logger, encryption_environment):
        super(OSEncryptionStateMachine, self).__init__()

        self.hutil = hutil
        self.distro_patcher = distro_patcher
        self.logger = logger
        self.encryption_environment = encryption_environment
        self.command_executor = CommandExecutor(self.logger)

        self.context = OSEncryptionStateContext(hutil=self.hutil,
                                                distro_patcher=self.distro_patcher,
                                                logger=self.logger,
                                                encryption_environment=self.encryption_environment)
        
        self.state_machine = Machine(model=self,
                                     states=OSEncryptionStateMachine.states,
                                     transitions=OSEncryptionStateMachine.transitions,
                                     initial='uninitialized')

    def log_machine_state(self):
        self.logger.log("======= MACHINE STATE: {0} =======".format(self.state))

    def start_encryption(self):
        self.skip_encryption()
        self.log_machine_state()
