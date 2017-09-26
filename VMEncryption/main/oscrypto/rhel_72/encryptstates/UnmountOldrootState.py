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


    def restart_all_services(self):
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(command_to_execute="systemctl list-units",
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)

        for line in proc_comm.stdout.split('\n'):
            if not "running" in line:
                continue

            if "waagent.service" in line or "sshd.service" in line:
                continue

            match = re.search(r'\s(\S*?\.service)', line)
            if match:
                service = match.groups()[0]
                self.command_executor.Execute('systemctl restart {0}'.format(service))


    def enter(self):
        if not self.should_enter():
            return

        self.context.logger.log("Entering unmount_oldroot state")

        self.command_executor.ExecuteInBash('mkdir -p /var/empty/sshd', True)
        self.command_executor.ExecuteInBash('systemctl restart sshd.service')
        self.command_executor.ExecuteInBash('dhclient')

        self.restart_systemd_services()

        self.command_executor.Execute('swapoff -a', True)

        if os.path.exists("/oldroot/mnt/resource"):
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
                self.context.logger.log("Restarting WALA in 30 seconds before committing suicide")
                
                # This is a workaround for the bug on CentOS/RHEL 7.2 where systemd-udevd
                # needs to be restarted and the drive mounted/unmounted.
                # Otherwise the dir becomes inaccessible, fuse says: Transport endpoint is not connected

                self.command_executor.Execute('systemctl restart systemd-udevd', True)
                self.bek_util.umount_azure_passhprase(self.encryption_config, force=True)
                self.command_executor.Execute('systemctl restart systemd-udevd', True)

                self.bek_util.get_bek_passphrase_file(self.encryption_config)
                self.bek_util.umount_azure_passhprase(self.encryption_config, force=True)
                self.command_executor.Execute('systemctl restart systemd-udevd', True)

                self.command_executor.ExecuteInBash('sleep 30 && systemctl start waagent &', True)

            if int(victim) == 1:
                self.context.logger.log("Skipping init")
                continue

            self.command_executor.Execute('kill -9 {0}'.format(victim))

        # Re-execute systemd, get pid 1 to use the new root
        self.command_executor.Execute('telinit u', True)

        sleep(3)

        self.command_executor.Execute('umount /oldroot', True)

        self.restart_systemd_services()
        proc_comm = ProcessCommunicator()
        self.command_executor.ExecuteInBash(
                command_to_execute="grep {0} /proc/*/task/*/mountinfo".format(self.rootfs_block_device),
                raise_exception_on_failure=True,
                communicator=proc_comm)

        procs_to_kill = filter(lambda path: path.startswith('/proc/'), proc_comm.stdout.split())
        procs_to_kill = map(lambda path: int(path.split('/')[2]), procs_to_kill)
        procs_to_kill = reversed(sorted(procs_to_kill))
        self.context.logger.log("Processes with tasks using {0}:\n{1}".format(self.rootfs_block_device, procs_to_kill))

        for victim in procs_to_kill:
            if int(victim) == os.getpid():
                self.context.logger.log("Apparently this extension holding on to {0}. "
                        "This is not expected...".format(self.rootfs_block_device))
                continue

            if int(victim) == 1:
                self.context.logger.log("Skipping init")
                continue

            self.command_executor.Execute('kill -9 {0}'.format(victim))

        sleep(3)

        attempt = 1

        while True:
            if attempt > 10:
                raise Exception("Block device {0} did not appear in 10 restart attempts".format(self.rootfs_block_device))

            self.context.logger.log("Attempt #{0} for restarting systemd-udevd".format(attempt))
            self.command_executor.Execute('systemctl restart systemd-udevd')

            sleep(10)

            if self.command_executor.ExecuteInBash('[ -b {0} ]'.format(self.rootfs_block_device), False) == 0:
                break

            attempt += 1

        sleep(3)

        self.command_executor.Execute('xfs_repair {0}'.format(self.rootfs_block_device), True)


    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit unmount_oldroot state")

        if os.path.exists('/oldroot/bin'):
            self.context.logger.log("/oldroot was not unmounted")
            return False

        return super(UnmountOldrootState, self).should_exit()
