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
from snapshotter import Snapshotter
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
        # fd valid values(0:nothing done,1: freezed successfully, 2:freeze failed)
        self.fd = 0
        self.child= None
        self.logger=logger

    def signal_handler(self,signal, frame):
        self.logger.log('freezed',False)
        self.fd=1

    def signhandler(self,signal, frame):
        self.logger.log('some child process terminated')
        if(self.child.poll() is not None):
            self.logger.log("child terminated",True)
            self.fd=2
        '''while(self.child.poll() is None and tim<100):
            tim=tim+1
            time.sleep(1)
        self.logger.log("child terminate timed out")
        self.fd=2'''

    def startproc(self,args):
        self.child = subprocess.Popen(args, stdout=subprocess.PIPE)
        while(self.fd==0):
            self.logger.log("inside while with fd "+str(self.fd))
            time.sleep(3)
        self.logger.log("Binary output for signal handled: "+str(self.fd)+"  "+str(self.child.stdout))
        return self.fd

    def signal_receiver(self):
        signal.signal(signal.SIGUSR1, self.signal_handler)
        signal.signal(signal.SIGCHLD, self.signhandler)

class FsFreezer:
    def __init__(self, patching, logger):
        """
        """
        self.patching = patching
        self.logger = logger
        self.mounts = Mounts(patching = self.patching, logger = self.logger)
        self.frozen_items = set()
        self.unfrozen_items = set()


    def should_skip(self, mount):
        if((mount.fstype == 'ext3' or mount.fstype == 'ext4' or mount.fstype == 'xfs' or mount.fstype == 'btrfs') and mount.type != 'loop'):
            return False
        else:
            return True
    
    def freeze_and_snapshot(self,timeout,para_parser):
        self.root_seen = False
        error_msg=''
        freeze_result = FreezeResult()
        freezebin=os.path.join(os.getcwd(),os.path.dirname(__file__),"freezetest.o")
        args=[freezebin,str(timeout)]
        arg=[]
        for mount in self.mounts.mounts:
            if(mount.mount_point == '/'):
                self.root_seen = True
                self.root_mount = mount
            elif(mount.mount_point and not self.should_skip(mount)):
                arg.append(str(mount.mount_point))
        setarg=set(arg)
        arg_list=list(setarg)
        arg_list.sort(reverse=True)
        for argi in arg_list:
            args.append(argi)
        if(self.root_seen):
            args.append('/')
        self.logger.log(str(args))
        freeze_handler=FreezeHandler(self.logger)
        freeze_handler.signal_receiver()
        self.logger.log("proceeded for accepting signals")
        fd=freeze_handler.startproc(args)
        if(fd==1):
            snap_shotter = Snapshotter(self.logger) 
            snapshot_result = snap_shotter.snapshotall(para_parser) 
            self.logger.log('T:S snapshotall ends...') 
            if(snapshot_result is not None and len(snapshot_result.errors) > 0): 
                freeze_result=snapshot_result
                self.logger.log("Snapshot failed")
            else: 
                self.logger.log("snapshot done")
                if(freeze_handler.child.poll() is None):
                    self.logger.log("child process still running")
                    freeze_handler.child.send_signal(signal.SIGUSR1)
                    while(freeze_handler.child.poll() is None):
                        self.logger.log("child still running sigusr1 sent")
                        time.sleep(1)
                    if(freeze_handler.child.returncode!=0):
                        error_msg = 'snapshot result inconsistent'
                        freeze_result.errors.append(error_msg)
                        self.logger.log(error_msg, False, 'Error')
                else:
                    error_msg = 'snapshot result inconsistent'
                    freeze_result.errors.append(error_msg)
                    self.logger.log(error_msg, False, 'Error')
        else:
            error_msg = 'failed to freeze '
            freeze_result.errors.append(error_msg)
            self.logger.log(error_msg, False, 'Error')
            if(freeze_handler.child.poll() is None):
                self.logger.log("how is child alive")
            self.logger.log(freeze_handler.child.returncode)
        return freeze_result

