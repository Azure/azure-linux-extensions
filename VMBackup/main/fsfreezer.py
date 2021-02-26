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
import traceback
import threading
import fcntl
from common import CommonVariables
from Utils.ResourceDiskUtil import ResourceDiskUtil

def thread_for_binary(self,args):
    self.logger.log("Thread for binary is called",True)
    time.sleep(3)
    self.logger.log("Waited in thread for 3 seconds",True)
    self.logger.log("****** 1. Starting Freeze Binary ",True)
    self.child = subprocess.Popen(args,stdout=subprocess.PIPE)
    self.logger.log("Binary subprocess Created",True)

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
    def __init__(self,logger,hutil):
        # sig_handle valid values(0:nothing done,1: freezed successfully, 2:freeze failed)
        self.sig_handle = 0
        self.child= None
        self.logger=logger
        self.hutil = hutil

    def sigusr1_handler(self,signal,frame):
        self.logger.log('freezed',False)
        self.logger.log("****** 4. Freeze Completed (Signal=1 received)",False)
        self.sig_handle=1

    def sigchld_handler(self,signal,frame):
        self.logger.log('some child process terminated')
        if(self.child is not None and self.child.poll() is not None):
            self.logger.log("binary child terminated",True)
            self.logger.log("****** 9. Binary Process completed (Signal=2 received)",True)
            self.sig_handle=2

    def reset_signals(self):
        self.sig_handle = 0
        self.child= None


    def startproc(self,args):
        binary_thread = threading.Thread(target=thread_for_binary, args=[self, args])
        binary_thread.start()

        SafeFreezeWaitInSecondsDefault = 66

        proc_sleep_time = self.hutil.get_intvalue_from_configfile('SafeFreezeWaitInSeconds',SafeFreezeWaitInSecondsDefault)
        
        for i in range(0,(int(proc_sleep_time/2))):
            if(self.sig_handle==0):
                self.logger.log("inside while with sig_handle "+str(self.sig_handle))
                time.sleep(2)
            else:
                break
        self.logger.log("Binary output for signal handled: "+str(self.sig_handle))
        return self.sig_handle

    def signal_receiver(self):
        signal.signal(signal.SIGUSR1,self.sigusr1_handler)
        signal.signal(signal.SIGCHLD,self.sigchld_handler)

class FsFreezer:
    def __init__(self, patching, logger, hutil):
        """
        """
        self.patching = patching
        self.logger = logger
        self.hutil = hutil
        try:
            self.mounts = Mounts(patching = self.patching, logger = self.logger)
        except Exception as e:
            errMsg='Failed to retrieve mount points, Exception %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg,True,'Warning')
            self.logger.log(str(e), True)
            self.mounts = None
        self.frozen_items = set()
        self.unfrozen_items = set()
        self.freeze_handler = FreezeHandler(self.logger, self.hutil)
        self.mount_open_failed = False
        self.resource_disk= ResourceDiskUtil(patching = patching, logger = logger)
        self.skip_freeze= True
        self.isAquireLockSucceeded = True
        self.getLockRetry = 0
        self.maxGetLockRetry = 5

    def should_skip(self, mount):
        resource_disk_mount_point= self.resource_disk.get_resource_disk_mount_point()
        if(resource_disk_mount_point is not None and mount.mount_point == resource_disk_mount_point):
            return True
        elif((mount.fstype == 'ext3' or mount.fstype == 'ext4' or mount.fstype == 'xfs' or mount.fstype == 'btrfs') and mount.type != 'loop' ):
            return False
        else:
            return True
    
    def freeze_safe(self,timeout):
        self.root_seen = False
        error_msg=''
        timedout = False
        self.skip_freeze = True 
        mounts_to_skip = None
        try:
            mounts_to_skip = self.hutil.get_strvalue_from_configfile('MountsToSkip','')
            self.logger.log("skipped mount :" + str(mounts_to_skip), True)
            mounts_list_to_skip = mounts_to_skip.split(',')
        except Exception as e:
            errMsg='Failed to read from config, Exception %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg,True,'Warning')
        try:
            freeze_result = FreezeResult()
            freezebin=os.path.join(os.getcwd(),os.path.dirname(__file__),"safefreeze/bin/safefreeze")
            args=[freezebin,str(timeout)]
            no_mount_found = True
            for mount in self.mounts.mounts:
                self.logger.log("fsfreeze mount :" + str(mount.mount_point), True)
                if(mount.mount_point == '/'):
                    self.root_seen = True
                    self.root_mount = mount
                elif(mount.mount_point not in mounts_list_to_skip and not self.should_skip(mount)):
                    if(self.skip_freeze == True):
                        self.skip_freeze = False
                    args.append(str(mount.mount_point))
            if(self.root_seen and not self.should_skip(self.root_mount)):
                if(self.skip_freeze == True):
                    self.skip_freeze = False
                args.append('/')
            self.logger.log("skip freeze is : " + str(self.skip_freeze), True)
            if(self.skip_freeze == True):
                return freeze_result,timedout
            self.logger.log("arg : " + str(args),True)
            self.freeze_handler.reset_signals()
            self.freeze_handler.signal_receiver()
            self.logger.log("proceeded for accepting signals", True)
            if(mounts_to_skip == '/'): #for continue logging to avoid out of memory issue
                self.logger.enforce_local_flag(True)
            else:
                self.logger.enforce_local_flag(False) 

            start_time = datetime.datetime.utcnow()

            while self.getLockRetry < self.maxGetLockRetry:
                try:
                    os.mkdir('/etc/azure/MicrosoftRecoverySvcsSafeFreezeLock')
                    file = open("/etc/azure/MicrosoftRecoverySvcsSafeFreezeLock/SafeFreezeLockFile","w")
                    self.logger.log("/etc/azure/MicrosoftRecoverySvcsSafeFreezeLock/SafeFreezeLockFile file opened Sucessfully",True)
                    try:
                        fcntl.lockf(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        self.logger.log("Aquiring lock succeeded",True)
                        self.isAquireLockSucceeded = True
                        break
                    except Exception as ex:
                        file.close()
                        raise ex
                except Exception as e:
                    self.logger.log("Failed to open file or aquire lock:  "+ str(e),True)
                    self.isAquireLockSucceeded = False
                    self.getLockRetry= getLockRetry + 1
                    time.sleep(1)
                    if(getLockRetry == maxGetLockRetry - 1):
                        time.sleep(30)
                self.logger.log("Retry to aquire lock count: "+ str(self.getLockRetry),True)

            end_time = datetime.datetime.utcnow()
            self.logger.log("Wait time to aquire lock "+ str(end_time - start_time),True)

            
            sig_handle = None
            if (self.isAquireLockSucceeded == True):
                sig_handle=self.freeze_handler.startproc(args)
                self.thaw_safe()
                try:
                    fcntl.lockf(file, fcntl.LOCK_UN)
                    file.close()
                except:
                    pass
                try:
                    os.remove("/etc/azure/filelock")
                except:
                    pass

            self.logger.log("freeze_safe after returning from startproc : sig_handle="+str(sig_handle))
            if(sig_handle != 1):
                if (self.freeze_handler.child is not None):
                    self.log_binary_output()
                if (sig_handle == 0):
                    timedout = True
                    error_msg="freeze timed-out"
                    freeze_result.errors.append(error_msg)
                    self.logger.log(error_msg, True, 'Error')
                elif (self.mount_open_failed == True):
                    error_msg=CommonVariables.unable_to_open_err_string
                    freeze_result.errors.append(error_msg)
                    self.logger.log(error_msg, True, 'Error')
                elif (self.isAquireLockSucceeded == False):
                    error_msg="Mount Points already freezed by some other processor"
                    freeze_result.errors.append(errMsg)
                    self.logger.log(errMsg,True,'Error')
                else:
                    error_msg="freeze failed for some mount"
                    freeze_result.errors.append(error_msg)
                    self.logger.log(error_msg, True, 'Error')
        except Exception as e:
            self.logger.enforce_local_flag(True)
            error_msg='freeze failed for some mount with exception, Exception %s, stack trace: %s' % (str(e), traceback.format_exc())
            freeze_result.errors.append(error_msg)
            self.logger.log(error_msg, True, 'Error')
        return freeze_result,timedout

    def thaw_safe(self):
        thaw_result = FreezeResult()
        unable_to_sleep = False
        if(self.skip_freeze == True):
            return thaw_result, unable_to_sleep
        if(self.freeze_handler.child is None):
            self.logger.log("child already completed", True)
            self.logger.log("****** 7. Error - Binary Process Already Completed", True)
            error_msg = 'snapshot result inconsistent'
            thaw_result.errors.append(error_msg)
        elif(self.freeze_handler.child.poll() is None):
            self.logger.log("child process still running")
            self.logger.log("****** 7. Sending Thaw Signal to Binary")
            self.freeze_handler.child.send_signal(signal.SIGUSR1)
            for i in range(0,30):
                if(self.freeze_handler.child.poll() is None):
                    self.logger.log("child still running sigusr1 sent")
                    time.sleep(1)
                else:
                    break
            self.logger.enforce_local_flag(True)
            self.log_binary_output()
            if(self.freeze_handler.child.returncode!=0):
                error_msg = 'snapshot result inconsistent as child returns with failure'
                thaw_result.errors.append(error_msg)
                self.logger.log(error_msg, True, 'Error')
        else:
            self.logger.log("Binary output after process end when no thaw sent: ", True)
            if(self.freeze_handler.child.returncode==2):
                error_msg = 'Unable to execute sleep'
                thaw_result.errors.append(error_msg)
                unable_to_sleep = True
            else:
                error_msg = 'snapshot result inconsistent'
                thaw_result.errors.append(error_msg)
            self.logger.enforce_local_flag(True)
            self.log_binary_output()
            self.logger.log(error_msg, True, 'Error')
        self.logger.enforce_local_flag(True)
        return thaw_result, unable_to_sleep

    def log_binary_output(self):
        self.logger.log("============== Binary output traces start ================= ", True)
        while True:
            line=self.freeze_handler.child.stdout.readline()
            if sys.version_info > (3,):
                line = str(line, encoding='utf-8', errors="backslashreplace")
            else:
                line = str(line)
            if("Failed to open:" in line):
                self.mount_open_failed = True
            if(line != ''):
                self.logger.log(line.rstrip(), True)
            else:
                break
        self.logger.log("============== Binary output traces end ================= ", True)

