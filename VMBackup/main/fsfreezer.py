#!/usr/bin/env python
#
# VM Backup extension
#
# Copyright 2014 Microsoft Corporation
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

import subprocess
from mounts import Mounts
import datetime
import threading
import os
import time
import sys
import signal

class FreezeError(object):
    def __init__(self):
        self.errorcode = None
        self.fstype = None
        self.path = None
    def __str__(self):
        return "errorcode:" + str(self.errorcode) + " fstype:" + str(self.fstype) + " path" + str(self.path)

class FreezeResult(object):
    def __init__(self):
        self.errors = []
    def __str__(self):
        error_str = ""
        for error in self.errors:
            error_str+=(str(error)) + "\n"
        return error_str

class FreezeHandler(object):
    def __init__(self,logger):
        # sig_handle valid values(0:nothing done,1: freezed successfully, 2:freeze failed)
        self.sig_handle = 0
        self.child= None
        self.logger=logger

    def sigusr1_handler(self,signal,frame):
        self.logger.log('freezed',False)
        self.sig_handle=1

    def sigchld_handler(self,signal,frame):
        self.logger.log('some child process terminated')
        if(self.child.poll() is not None):
            self.logger.log("binary child terminated",True)
            self.sig_handle=2

    def startproc(self,args):
        self.child = subprocess.Popen(args,stdout=subprocess.PIPE)
        for i in range(0,30):
            if(self.sig_handle==0):
                self.logger.log("inside while with sig_handle "+str(self.sig_handle))
                time.sleep(2)
            else:
                break;
        self.logger.log("Binary output for signal handled: "+str(self.sig_handle)+"  "+str(self.child.stdout))
        return self.sig_handle

    def signal_receiver(self):
        signal.signal(signal.SIGUSR1,self.sigusr1_handler)
        signal.signal(signal.SIGCHLD,self.sigchld_handler)

class FsFreezer:
    def __init__(self, patching, logger):
        """
        """
        self.patching = patching
        self.logger = logger
        self.mounts = Mounts(patching = self.patching, logger = self.logger)
        self.frozen_items = set()
        self.unfrozen_items = set()
        self.freeze_handler = FreezeHandler(self.logger)


    def should_skip(self, mount):
        if((mount.fstype == 'ext3' or mount.fstype == 'ext4' or mount.fstype == 'xfs' or mount.fstype == 'btrfs') and mount.type != 'loop'):
            return False
        else:
            return True
    
    def freeze_safe(self,timeout):
        self.root_seen = False
        error_msg=''
        freeze_result = FreezeResult()
        freezebin=os.path.join(os.getcwd(),os.path.dirname(__file__),"safefreeze/bin/safefreeze")
        args=[freezebin,str(timeout)]
        arg=[]
        for mount in self.mounts.mounts:
            if(mount.mount_point == '/'):
                self.root_seen = True
                self.root_mount = mount
            elif(mount.mount_point and not self.should_skip(mount)):
                arg.append(str(mount.mount_point))
        mount_set=set(arg)
        mount_list=list(mount_set)
        mount_list.sort(reverse=True)
        for mount_itr in mount_list:
            args.append(mount_itr)
        if(self.root_seen):
            args.append('/')
        self.logger.log(str(args))
        self.freeze_handler.signal_receiver()
        self.logger.log("proceeded for accepting signals")
        sig_handle=self.freeze_handler.startproc(args)
        if(sig_handle != 1):
            error_msg="freeze failed for some mount"
            freeze_result.errors.append(error_msg)
            self.logger.log(error_msg, True, 'Error')
        return freeze_result

    def thaw_safe(self):
        thaw_result = FreezeResult()
        if(self.freeze_handler.child.poll() is None):
            self.logger.log("child process still running")
            self.freeze_handler.child.send_signal(signal.SIGUSR1)
            while(self.freeze_handler.child.poll() is None):
                self.logger.log("child still running sigusr1 sent")
                time.sleep(1)
            if(self.freeze_handler.child.returncode!=0):
                error_msg = 'snapshot result inconsistent'
                thaw_result.errors.append(error_msg)
                self.logger.log(error_msg, True, 'Error')
        else:
            error_msg = 'snapshot result inconsistent'
            thaw_result.errors.append(error_msg)
            self.logger.log(error_msg, True, 'Error')
        return thaw_result

