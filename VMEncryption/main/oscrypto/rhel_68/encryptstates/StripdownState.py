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

class StripdownState(OSEncryptionState):
    def __init__(self, context):
        super(StripdownState, self).__init__('StripdownState', context)

    def should_enter(self):
        self.context.logger.log("Verifying if machine should enter stripdown state")

        if not super(StripdownState, self).should_enter():
            return False
        
        self.context.logger.log("Performing enter checks for stripdown state")

        self.command_executor.Execute('rm -rf /tmp/tmproot', True)
        self.command_executor.ExecuteInBash('! [ -e "/oldroot" ]', True)

        return True

    def enter(self):
        if not self.should_enter():
            return

        self.context.logger.log("Entering stripdown state")

        self.command_executor.Execute('umount -a')
        self.command_executor.Execute('mkdir /tmp/tmproot', True)
        self.command_executor.Execute('mount -t tmpfs none /tmp/tmproot', True)
        self.command_executor.ExecuteInBash('for i in proc sys dev run usr var tmp root oldroot boot; do mkdir /tmp/tmproot/$i; done', True)
        self.command_executor.ExecuteInBash('for i in bin etc mnt sbin lib lib64 root; do cp -ax /$i /tmp/tmproot/; done', True)
        self.command_executor.ExecuteInBash('for i in bin sbin libexec lib lib64 share; do cp -ax /usr/$i /tmp/tmproot/usr/; done', True)
        self.command_executor.ExecuteInBash('for i in lib local lock opt run spool tmp; do cp -ax /var/$i /tmp/tmproot/var/; done', True)
        self.command_executor.ExecuteInBash('mkdir /tmp/tmproot/var/log', True)
        self.command_executor.ExecuteInBash('cp -ax /var/log/azure /tmp/tmproot/var/log/', True)
        self.command_executor.Execute('mount --make-rprivate /', True)
        self.command_executor.ExecuteInBash('[ -e "/tmp/tmproot/var/lib/azure_disk_encryption_config/azure_crypt_request_queue.ini" ]', True)
        self.command_executor.Execute('systemctl stop waagent', True)
        self.command_executor.Execute('pivot_root /tmp/tmproot /tmp/tmproot/oldroot', True)
        self.command_executor.ExecuteInBash('for i in dev proc sys run; do mount --move /oldroot/$i /$i; done', True)

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit stripdown state")

        if not os.path.exists(self.state_marker):
            self.context.logger.log("First call to stripdown state (pid={0}), restarting process".format(os.getpid()))

            # create the marker, but do not advance the state machine
            super(StripdownState, self).should_exit()

            # the restarted process shall see the marker and advance the state machine
            self.command_executor.ExecuteInBash('sleep 30 && systemctl start waagent &', True)

            self.context.hutil.do_exit(exit_code=0,
                                       operation='EnableEncryptionOSVolume',
                                       status=CommonVariables.extension_success_status,
                                       code=str(CommonVariables.success),
                                       message="Restarted extension from stripped down OS")
        else:
            self.context.logger.log("Second call to stripdown state (pid={0}), continuing process".format(os.getpid()))
            return True
