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
maindir = os.path.abspath(os.path.join(scriptdir, '../../'))
sys.path.append(maindir)
sixdir = os.path.abspath(os.path.join(scriptdir, '../../six'))
sys.path.append(sixdir)
transitionsdir = os.path.abspath(os.path.join(scriptdir, '../../transitions'))
sys.path.append(transitionsdir)
from oscrypto import *
from .encryptstates import *
from Common import *
from CommandExecutor import *
from DiskUtil import *
from transitions import *

class Mariner10EncryptionStateMachine(OSEncryptionStateMachine):
    states = [
        State(name='uninitialized'),
        State(name='prereq', on_enter='on_enter_state'),
        State(name='selinux', on_enter='on_enter_state'),
        State(name='stripdown', on_enter='on_enter_state'),
        State(name='unmount_oldroot', on_enter='on_enter_state'),
        State(name='encrypt_block_device', on_enter='on_enter_state'),
        State(name='patch_boot_system', on_enter='on_enter_state'),
        State(name='completed'),
    ]

    transitions = [
        {
            'trigger': 'skip_encryption',
            'source': 'uninitialized',
            'dest': 'completed'
        },
        {
            'trigger': 'enter_prereq',
            'source': 'uninitialized',
            'dest': 'prereq'
        },
        {
            'trigger': 'enter_selinux',
            'source': 'prereq',
            'dest': 'selinux',
            'before': 'on_enter_state',
            'conditions': 'should_exit_previous_state'
        },
        {
            'trigger': 'enter_stripdown',
            'source': 'selinux',
            'dest': 'stripdown',
            'before': 'on_enter_state',
            'conditions': 'should_exit_previous_state'
        },
        {
            'trigger': 'enter_unmount_oldroot',
            'source': 'stripdown',
            'dest': 'unmount_oldroot',
            'before': 'on_enter_state',
            'conditions': 'should_exit_previous_state'
        },
        {
            'trigger': 'retry_unmount_oldroot',
            'source': 'unmount_oldroot',
            'dest': 'unmount_oldroot',
            'before': 'on_enter_state'
        },
        {
            'trigger': 'enter_encrypt_block_device',
            'source': 'unmount_oldroot',
            'dest': 'encrypt_block_device',
            'before': 'on_enter_state',
            'conditions': 'should_exit_previous_state'
        },
        {
            'trigger': 'enter_patch_boot_system',
            'source': 'encrypt_block_device',
            'dest': 'patch_boot_system',
            'before': 'on_enter_state',
            'conditions': 'should_exit_previous_state'
        },
        {
            'trigger': 'stop_machine',
            'source': 'patch_boot_system',
            'dest': 'completed',
            'conditions': 'should_exit_previous_state'
        },
    ]

    def on_enter_state(self):
        super(Mariner10EncryptionStateMachine, self).on_enter_state()

    def should_exit_previous_state(self):
        # when this is called, self.state is still the "source" state in the transition
        return super(Mariner10EncryptionStateMachine, self).should_exit_previous_state()

    def __init__(self, hutil, distro_patcher, logger, encryption_environment):
        super(Mariner10EncryptionStateMachine, self).__init__(hutil, distro_patcher, logger, encryption_environment)

        self.state_objs = {
            'prereq': PrereqState(self.context),
            'selinux': SelinuxState(self.context),
            'stripdown': StripdownState(self.context),
            'unmount_oldroot': UnmountOldrootState(self.context),
            'encrypt_block_device': EncryptBlockDeviceState(self.context),
            'patch_boot_system': PatchBootSystemState(self.context),
        }

        self.state_machine = Machine(model=self,
                                     states=Mariner10EncryptionStateMachine.states,
                                     transitions=Mariner10EncryptionStateMachine.transitions,
                                     initial='uninitialized')

    def start_encryption(self):
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(command_to_execute="mount",
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)
        if '/dev/mapper/osencrypt' in proc_comm.stdout:
            self.logger.log("OS volume is already encrypted")

            self.skip_encryption()
            self.log_machine_state()

            return

        self.log_machine_state()

        self.enter_prereq()
        self.log_machine_state()

        self.enter_selinux()
        self.log_machine_state()

        self.enter_stripdown()
        self.log_machine_state()
        
        oldroot_unmounted_successfully = False
        attempt = 1

        while not oldroot_unmounted_successfully:
            self.logger.log("Attempt #{0} to unmount /oldroot".format(attempt))

            try:
                if attempt == 1:
                    self.enter_unmount_oldroot()
                elif attempt > 10:
                    raise Exception("Could not unmount /oldroot in 10 attempts")
                else:
                    self.retry_unmount_oldroot()

                self.log_machine_state()
            except Exception as e:
                message = "Attempt #{0} to unmount /oldroot failed with error: {1}, stack trace: {2}".format(attempt,
                                                                                                             e,
                                                                                                             traceback.format_exc())
                self.logger.log(msg=message)
                self.hutil.do_status_report(operation='EnableEncryptionOSVolume',
                                            status=CommonVariables.extension_error_status,
                                            status_code=str(CommonVariables.unmount_oldroot_error),
                                            message=message)

                sleep(10)
                if attempt > 10:
                    raise Exception(message)
            else:
                oldroot_unmounted_successfully = True
            finally:
                attempt += 1
        
        self.enter_encrypt_block_device()
        self.log_machine_state()

        self.enter_patch_boot_system()
        self.log_machine_state()
        
        self.stop_machine()
        self.log_machine_state()

        self._reboot()