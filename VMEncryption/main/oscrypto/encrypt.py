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
maindir = os.path.abspath(os.path.join(scriptdir, '../'))
sys.path.append(maindir)
transitionsdir = os.path.abspath(os.path.join(scriptdir, '../../transitions'))
sys.path.append(transitionsdir)

from encryptstates import *
from Common import *
from transitions import *

class OSEncryption(object):
    states = [
        State(name='uninitialized'),
        State(name='prereq', on_enter='on_enter_state'),
        State(name='selinux', on_enter='on_enter_state'),
        State(name='stripdown', on_enter='on_enter_state'),
        State(name='unmount_oldroot', on_enter='on_enter_state'),
        State(name='completed'),
    ]

    transitions = [
        {
            'trigger': 'start_machine',
            'source': 'uninitialized',
            'dest': 'prereq'
        },
        {
            'trigger': 'perform_prereq',
            'source': 'prereq',
            'dest': 'selinux',
            'before': 'on_enter_state',
            'conditions': 'should_exit_state'
        },
        {
            'trigger': 'perform_selinux',
            'source': 'selinux',
            'dest': 'stripdown',
            'before': 'on_enter_state',
            'conditions': 'should_exit_state'
        },
        {
            'trigger': 'perform_stripdown',
            'source': 'stripdown',
            'dest': 'unmount_oldroot',
            'before': 'on_enter_state',
            'conditions': 'should_exit_state'
        },
        {
            'trigger': 'report_success',
            'source': 'unmount_oldroot',
            'dest': 'completed',
            'conditions': 'should_exit_state'
        },
    ]

    def on_enter_state(self):
        self.state_objs[self.state].enter()

    def should_exit_state(self):
        return self.state_objs[self.state].should_exit()

    def __init__(self, hutil, distro_patcher, logger, encryption_environment):
        super(OSEncryption, self).__init__()

        self.hutil = hutil
        self.distro_patcher = distro_patcher
        self.logger = logger
        self.encryption_environment = encryption_environment

        context = OSEncryptionStateContext(hutil=self.hutil,
                                           distro_patcher=self.distro_patcher,
                                           logger=self.logger,
                                           encryption_environment=self.encryption_environment);

        self.state_objs = {
            'prereq': PrereqState(context),
            'selinux': SelinuxState(context),
            'stripdown': StripdownState(context),
            'unmount_oldroot': UnmountOldrootState(context),
        }

        self.state_machine = Machine(model=self,
                                     states=OSEncryption.states,
                                     transitions=OSEncryption.transitions,
                                     initial='uninitialized')

    def log_machine_state(self):
        self.logger.log("======= MACHINE STATE: {0} =======".format(self.state))

    def start_encryption(self):
        self.log_machine_state()
        self.start_machine()
        
        self.log_machine_state()
        self.perform_prereq()
        
        self.log_machine_state()
        self.perform_selinux()
        
        self.log_machine_state()
        self.perform_stripdown()
        
        self.log_machine_state()
        self.report_success()
