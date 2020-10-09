#!/usr/bin/env python
#
# VM Backup extension
#
# Copyright 2020 Microsoft Corporation
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
maindir = os.path.abspath(os.path.join(scriptdir, '../../'))
sys.path.append(maindir)
transitionsdir = os.path.abspath(os.path.join(scriptdir, '../../transitions'))
sys.path.append(transitionsdir)

from oscrypto import OSEncryptionStateMachine
from .encryptstates import PrereqState, PatchBootSystemState, ResumeEncryptionState
from CommandExecutor import ProcessCommunicator
from transitions import State, Machine


class RHEL81EncryptionStateMachine(OSEncryptionStateMachine):
    states = [
        State(name='uninitialized'),
        State(name='prereq', on_enter='on_enter_state'),
        State(name='patch_boot_system', on_enter='on_enter_state'),
        State(name='resume_encryption', on_enter='on_enter_state'),
        State(name='completed')
    ]

    transitions = [
        {
            'trigger': 'skip_to_resume_encryption',
            'source': 'uninitialized',
            'dest': 'resume_encryption'
        },
        {
            'trigger': 'enter_prereq',
            'source': 'uninitialized',
            'dest': 'prereq'
        },
        {
            'trigger': 'enter_patch_boot_system',
            'source': 'prereq',
            'dest': 'patch_boot_system',
            'before': 'on_enter_state',
            'conditions': 'should_exit_previous_state'
        },
        {
            'trigger': 'enter_resume_encryption',
            'source': 'patch_boot_system',
            'dest': 'resume_encryption',
            'before': 'on_enter_state',
            'conditions': 'should_exit_previous_state'
        },
        {
            'trigger': 'stop_machine',
            'source': 'resume_encryption',
            'dest': 'completed',
            'conditions': 'should_exit_previous_state'
        },
    ]

    def on_enter_state(self):
        super(RHEL81EncryptionStateMachine, self).on_enter_state()

    def should_exit_previous_state(self):
        # when this is called, self.state is still the "source" state in the transition
        return super(RHEL81EncryptionStateMachine, self).should_exit_previous_state()

    def __init__(self, hutil, distro_patcher, logger, encryption_environment):
        super(RHEL81EncryptionStateMachine, self).__init__(hutil, distro_patcher, logger, encryption_environment)

        self.state_objs = {
            'prereq': PrereqState(self.context),
            'patch_boot_system': PatchBootSystemState(self.context),
            'resume_encryption': ResumeEncryptionState(self.context),
        }

        self.state_machine = Machine(model=self,
                                     states=RHEL81EncryptionStateMachine.states,
                                     transitions=RHEL81EncryptionStateMachine.transitions,
                                     initial='uninitialized')

    def start_encryption(self):
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(command_to_execute="mount",
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)
        if '/dev/mapper/osencrypt' in proc_comm.stdout:
            self.logger.log("OS volume is already mounted from /dev/mapper/osencrypt")

            self.skip_to_resume_encryption()
            self.log_machine_state()

            self.stop_machine()
            self.log_machine_state()

            return

        self.log_machine_state()

        self.enter_prereq()
        self.log_machine_state()

        self.enter_patch_boot_system()
        self.log_machine_state()

        self.enter_resume_encryption()
        self.log_machine_state()

        self.stop_machine()
        self.log_machine_state()
