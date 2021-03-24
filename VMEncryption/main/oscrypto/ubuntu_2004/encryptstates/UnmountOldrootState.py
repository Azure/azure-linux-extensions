#!/usr/bin/env python
#
# Copyright (C) Microsoft Corporation
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

import os
import re
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
        
        if self.command_executor.Execute('mountpoint /oldroot') != 0:
            return False
                
        return True

    def enter(self):
        if not self.should_enter():
            return

        self.context.logger.log("Entering unmount_oldroot state")
        
        self.command_executor.Execute('systemctl rescue', True)
        self.command_executor.Execute('systemctl start sshd.service', True)
        self.command_executor.Execute('systemctl start walinuxagent.service', True)
        
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(command_to_execute="systemctl list-units",
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)

        for line in proc_comm.stdout.split('\n'):
            if not "running" in line:
                continue

            if "walinuxagent.service" in line or "sshd.service" in line:
                continue

            match = re.search(r'\s(\S*?\.service)', line)
            if match:
                service = match.groups()[0]
                self.command_executor.Execute('systemctl restart {0}'.format(service))

        self.command_executor.Execute('swapoff -a', True)

        self.bek_util.umount_azure_passhprase(self.encryption_config, force=True)

        if os.path.exists("/oldroot/mnt"):
            self.command_executor.Execute('umount /oldroot/mnt')

        if os.path.exists("/oldroot/mnt/azure_bek_disk"):
            self.command_executor.Execute('umount /oldroot/mnt/azure_bek_disk')

        if os.path.exists("/mnt"):
            self.command_executor.Execute('umount -R /mnt')

        if os.path.exists("/mnt/azure_bek_disk"):
            self.command_executor.Execute('umount /mnt/azure_bek_disk')

        proc_comm = ProcessCommunicator()

        self.command_executor.Execute(command_to_execute="fuser -vm /oldroot",
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)

        self.context.logger.log("Processes using oldroot:\n{0}".format(proc_comm.stdout))

        procs_to_kill = [p for p in proc_comm.stdout.split() if p.isdigit()]
        procs_to_kill = reversed(sorted(procs_to_kill))

        for victim in procs_to_kill:
            proc_name = ""

            try:
                with open("/proc/{0}/cmdline".format(victim)) as f:
                    proc_name = f.read()
            except IOError as e:
                self.context.logger.log("Proc {0} is already dead".format(victim))

            self.context.logger.log("Killing process: {0} ({1})".format(proc_name, victim))

            if int(victim) == os.getpid():
                self.context.logger.log("Restarting WALA in 30 seconds before committing suicide")

                # Kill any other daemons that are blocked and would be executed after this process commits
                # suicide
                self.command_executor.ExecuteInBash('sleep 30 && pkill -f .*ForLinux.*handle.py.*daemon.* && systemctl start walinuxagent &', True)

            if int(victim) == 1:
                self.context.logger.log("Skipping init")
                continue

            self.command_executor.Execute('kill -9 {0}'.format(victim))

        self.command_executor.Execute('telinit u', True)

        sleep(3)

        self.command_executor.Execute('umount /oldroot', True)

        sleep(3)
        
        attempt = 1

        while True:
            if attempt > 10:
                raise Exception("Block device {0} did not appear in 10 restart attempts".format(self.rootfs_block_device))

            self.context.logger.log("Restarting systemd-udevd")
            self.command_executor.Execute('systemctl restart systemd-udevd')
            self.context.logger.log("Restarting systemd-timesyncd")
            self.command_executor.Execute('systemctl restart systemd-timesyncd')
            self.context.logger.log("Restarting systemd-networkd")
            self.command_executor.Execute('systemctl restart systemd-networkd')

            sleep(10)

            if self.command_executor.ExecuteInBash('[ -b {0} ]'.format(self.rootfs_block_device), False) == 0:
                break

            attempt += 1

        self.command_executor.Execute('e2fsck -yf {0}'.format(self.rootfs_block_device), True)

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit unmount_oldroot state")

        if os.path.exists('/oldroot/bin'):
            self.context.logger.log("/oldroot was not unmounted")
            return False

        return super(UnmountOldrootState, self).should_exit()
