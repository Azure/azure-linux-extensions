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

    def enter(self):
        if not self.should_enter():
            return

        self.context.logger.log("Entering unmount_oldroot state")

        self.unmount_var()

        self.command_executor.ExecuteInBash('mkdir -p /var/empty/sshd', True)
        self.command_executor.ExecuteInBash('systemctl restart sshd.service')
        self.command_executor.ExecuteInBash('dhclient')
        
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(command_to_execute="systemctl list-units",
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)

        for line in proc_comm.stdout.split('\n'):
            if not "running" in line:
                continue

            if "waagent.service" in line or "sshd.service" in line or "journald.service" in line:
                continue

            match = re.search(r'\s(\S*?\.service)', line)
            if match:
                service = match.groups()[0]
                self.command_executor.Execute('systemctl restart {0}'.format(service))

        self.command_executor.Execute('swapoff -a', True)

        if os.path.exists("/oldroot/mnt/resource"):
            self.command_executor.Execute('umount /oldroot/mnt/resource')

        sleep(3)
        
        self.unmount('/oldroot/opt')
        self.unmount('/oldroot/var')
        self.unmount('/oldroot/usr')
        self.unmount('/oldroot')

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

        self.unmount_var()

        sleep(3)

        self.command_executor.Execute('vgcfgbackup -f /volumes.lvm rootvg', True)
        self.command_executor.Execute('sed -i.bak \'s/sda2/mapper\/osencrypt/g\' /volumes.lvm', True)
        self.command_executor.Execute('lvremove -f rootvg', True)
        self.command_executor.Execute('vgremove rootvg', True)

    def unmount_var(self):
        unmounted = False

        while not unmounted:
            self.command_executor.Execute('systemctl stop NetworkManager')
            self.command_executor.Execute('systemctl stop rsyslog')
            self.command_executor.Execute('systemctl stop systemd-udevd')
            self.command_executor.Execute('systemctl stop systemd-journald')
            self.command_executor.Execute('systemctl stop systemd-hostnamed')
            self.command_executor.Execute('systemctl stop atd')
            self.command_executor.Execute('systemctl stop postfix')
            self.unmount('/var')

            sleep(3)

            if self.command_executor.Execute('mountpoint /var'):
                unmounted = True

    def unmount(self, mountpoint, call_unmount_var=True):
        if mountpoint != '/var':
            self.unmount_var()

        if self.command_executor.Execute("mountpoint " + mountpoint):
            return

        proc_comm = ProcessCommunicator()

        self.command_executor.Execute(command_to_execute="fuser -vm " + mountpoint,
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)

        self.context.logger.log("Processes using {0}:\n{1}".format(mountpoint, proc_comm.stdout))

        procs_to_kill = filter(lambda p: p.isdigit(), proc_comm.stdout.split())
        procs_to_kill = reversed(sorted(procs_to_kill))

        for victim in procs_to_kill:
            if int(victim) == os.getpid():
                self.context.logger.log("Restarting WALA before committing suicide")
                self.context.logger.log("Current executable path: " + sys.executable)
                self.context.logger.log("Current executable arguments: " + " ".join(sys.argv))

                # Kill any other daemons that are blocked and would be executed after this process commits
                # suicide
                self.command_executor.Execute('systemctl restart atd')

                os.chdir('/')
                with open("/delete-lock.sh", "w") as f:
                    f.write("rm -f /var/lib/azure_disk_encryption_config/daemon_lock_file.lck\n")

                self.command_executor.Execute('at -f /delete-lock.sh now + 1 minutes', True)
                self.command_executor.Execute('at -f /restart-wala.sh now + 2 minutes', True)
                self.command_executor.ExecuteInBash('pkill -f .*ForLinux.*handle.py.*daemon.*', True)

            if int(victim) == 1:
                self.context.logger.log("Skipping init")
                continue

            self.command_executor.Execute('kill -9 {0}'.format(victim))

        self.command_executor.Execute('telinit u', True)

        sleep(10)

        if self.command_executor.Execute('mountpoint /var') == 0:
            self.command_executor.Execute('umount /var', True)

        sleep(3)

        self.command_executor.Execute('umount ' + mountpoint, True)

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit unmount_oldroot state")

        if os.path.exists('/oldroot/bin'):
            self.context.logger.log("/oldroot was not unmounted")
            return False

        return super(UnmountOldrootState, self).should_exit()
