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

import os
import sys

from time import sleep
from OSEncryptionState import *

class UnmountOldrootState(OSEncryptionState):
    def __init__(self, context):
        super(UnmountOldrootState, self).__init__('UnmountOldrootState', context)

    def should_enter(self):
        self.context.logger.log("Verifying if machine should enter unmount_oldroot state")

        if not super(UnmountOldrootState, self).should_enter():
            return False
        
        self.context.logger.log("Performing enter checks for unmount_oldroot state")

        self.command_executor.ExecuteInBash('[ -e "/oldroot" ]', True)
                
        return True

    def enter(self):
        if not self.should_enter():
            return

        self.context.logger.log("Entering unmount_oldroot state")

        if os.path.exists("/oldroot/mnt/resource"):
            self.command_executor.Execute('swapoff -a', True)
            self.command_executor.Execute('umount /oldroot/mnt/resource')

        proc_comm = ProcessCommunicator()

        self.command_executor.Execute(command_to_execute="fuser -vm /oldroot",
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)

        self.context.logger.log("Processes using oldroot:\n{0}".format(proc_comm.stdout))

        procs_to_kill = filter(lambda p: p.isdigit(), proc_comm.stdout.split())
        procs_to_kill = reversed(sorted(procs_to_kill))

        for victim in procs_to_kill:
            if int(victim) == os.getpid():
                self.context.logger.log("Skipping suicide")
                continue
            self.command_executor.Execute('kill -9 {0}'.format(victim))

        self.command_executor.ExecuteInBash('mkdir -p /var/empty/sshd', True)
        self.command_executor.ExecuteInBash('/usr/sbin/sshd', True)

        self.command_executor.Execute('telinit u', True)

        sleep(3)

        self.command_executor.Execute('umount /oldroot', True)

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit unmount_oldroot state")

        if os.path.exists('/oldroot/bin'):
            self.context.logger.log("/oldroot was not unmounted")
            return False
        
        self.command_executor.Execute('xfs_repair /dev/sda2', True)

        return super(UnmountOldrootState, self).should_exit()
