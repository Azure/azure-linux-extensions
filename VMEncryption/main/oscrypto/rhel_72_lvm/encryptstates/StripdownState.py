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

from OSEncryptionState import *
from time import sleep

class StripdownState(OSEncryptionState):
    def __init__(self, context):
        super(StripdownState, self).__init__('StripdownState', context)

    def should_enter(self):
        self.context.logger.log("Verifying if machine should enter stripdown state")

        if not super(StripdownState, self).should_enter():
            return False
        
        self.context.logger.log("Performing enter checks for stripdown state")

        self.command_executor.Execute('rm -rf /usr/tmproot', True)
        self.command_executor.ExecuteInBash('! [ -e "/oldroot" ]', True)

        return True

    def enter(self):
        if not self.should_enter():
            return

        self.context.logger.log("Entering stripdown state")
        
        self.command_executor.Execute('swapoff -a')
        self.command_executor.Execute('umount -a')
        self.command_executor.Execute('mkdir /usr/tmproot', True)
        self.command_executor.Execute('mount -t tmpfs none /usr/tmproot', True)
        self.command_executor.ExecuteInBash('for i in proc sys dev run usr var tmp root oldroot boot; do mkdir /usr/tmproot/$i; done', True)
        self.command_executor.ExecuteInBash('for i in bin etc mnt sbin lib lib64 root; do cp -ax /$i /usr/tmproot/; done', True)
        self.command_executor.ExecuteInBash('for i in bin sbin libexec lib lib64 share; do cp -ax /usr/$i /usr/tmproot/usr/; done', True)
        self.command_executor.ExecuteInBash('for i in lib local lock opt run spool tmp; do cp -ax /var/$i /usr/tmproot/var/; done', True)
        self.command_executor.ExecuteInBash('mkdir /usr/tmproot/var/log', True)
        self.command_executor.ExecuteInBash('cp -ax /var/log/azure /usr/tmproot/var/log/', True)
        self.command_executor.Execute('mount --make-rprivate /', True)
        self.command_executor.ExecuteInBash('[ -e "/usr/tmproot/var/lib/azure_disk_encryption_config/azure_crypt_request_queue.ini" ]', True)
        self.command_executor.Execute('systemctl stop waagent', True)
        self.command_executor.Execute('pivot_root /usr/tmproot /usr/tmproot/oldroot', True)
        self.command_executor.ExecuteInBash('for i in dev proc sys run; do mount --move /oldroot/$i /$i; done', True)

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit stripdown state")

        if not os.path.exists(self.state_marker):
            self.context.logger.log("First call to stripdown state (pid={0}), restarting process".format(os.getpid()))

            # create the marker, but do not advance the state machine
            super(StripdownState, self).should_exit()

            self.command_executor.ExecuteInBash('rm -f /run/systemd/generator/*.mount', True)
            self.command_executor.ExecuteInBash('rm -f /run/systemd/generator/local-fs.target.requires/*.mount', True)
            self.command_executor.Execute("sed -i.bak '/rootvg/d' /etc/fstab", True)

            self.command_executor.Execute('telinit u', True)

            sleep(10)

            if self.command_executor.Execute('mountpoint /var') == 0:
                self.command_executor.Execute('umount /var', True)

            # the restarted process shall see the marker and advance the state machine
            self.command_executor.Execute('systemctl restart atd', True)

            os.chdir('/')
            with open("/restart-wala.sh", "w") as f:
                f.write("systemctl restart waagent\n")
            self.command_executor.Execute('at -f /restart-wala.sh now + 1 minutes', True)

            self.context.hutil.do_exit(exit_code=0,
                                       operation='EnableEncryptionOSVolume',
                                       status=CommonVariables.extension_success_status,
                                       code=str(CommonVariables.success),
                                       message="Restarted extension from stripped down OS")
        else:
            self.context.logger.log("Second call to stripdown state (pid={0}), continuing process".format(os.getpid()))
            return True
