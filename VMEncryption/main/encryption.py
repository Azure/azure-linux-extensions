#!/usr/bin/env python
#
# VM Encryption extension
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
#
# Requires Python 2.7+
#
import subprocess
import sys  
from common import CommonVariables
from subprocess import *  
from patch import *
from keymanager import *

class EncryptionError(object):
    def __init__(self):
        self.errorcode = None
        self.state=None
        self.code=None
        self.info=None

class Encryption(object):
    """
    description of class
    """
    def __init__(self, paras):
        self.paras = paras

    #def install_extras(self):
    #    global MyPatching
    #    MyPatching = GetMyPatching()
    #    if MyPatching == None:
    #        sys.exit(1)
    #    else:
    #        MyPatching.install_extras(self.paras)

    def encrypt(self):
        #self.install_extras()
        # keyManager = KeyManager(self.paras.keyaddess, self.paras.password);
        #print(self.paras.command)
        error = EncryptionError()

        if(self.paras.command == 'disk'):
            # handle the error cases
            commandToExecute = '/bin/bash -c "' + 'echo -n "' + self.paras.passphrase + '" | cryptsetup luksFormat ' + self.paras.path +'"'
            print(commandToExecute)
            proc = Popen(commandToExecute, shell=True)
            returnCode = proc.wait()
            if(returnCode!=0):
                error.errorcode=returnCode
                error.code=CommonVariables.luks_format_error
                error.info="path is "+str(self.paras.path)
                print('cryptsetup -y luksFormat returnCode is ' + str(returnCode))
                return error

            commandToExecute = '/bin/bash -c "' + 'echo -n "' + self.paras.passphrase + '" | cryptsetup luksOpen ' + self.paras.path + ' ' + self.paras.mountname +'"'
            print(commandToExecute)
            proc = Popen(commandToExecute, shell=True)
            returnCode = proc.wait()
            if(returnCode != 0):
                error.errorcode = returnCode
                error.code=CommonVariables.luks_open_error
                error.info="path is "+str(self.paras.path)+" mountname is "+str(self.paras.mountname)
                print('cryptsetup luksOpen returnCode is ' + str(returnCode))
                return error

            # we should specify the file system?
            # if self.paras.fstype is specified, then use it, if not, use ext4
            mkfs_command = ""
            if(self.paras.filesystem == "ext4"):
                mkfs_command = "mkfs.ext4"
            elif(self.paras.filesystem == "ext3"):
                mkfs_command = "mkfs.ext3"
            elif(self.paras.filesystem == "xfs"):
                mkfs_command = "mkfs.xfs"
            elif(self.paras.filesystem == "btrfs"):
                mkfs_command = "mkfs.btrfs"
                pass
            commandToExecute = '/bin/bash -c "' + mkfs_command + ' /dev/mapper/' + self.paras.mountname + ' <<< ' + self.paras.mountname + ' 2> /dev/null"'
            print(commandToExecute)
            proc = Popen(commandToExecute, shell=True)
            returnCode = proc.wait()
            if(returnCode!=0):
                error.errorcode=returnCode
                error.code=CommonVariables.mkfs_error
                error.info="commandToExecute is "+commandToExecute
                print('mkfs_command returnCode is ' + str(returnCode))
                return error

            commandToExecute = '/bin/bash -c "mkdir ' + (self.paras.mountpoint + self.paras.mountname) + ' 2> /dev/null"'
            print(commandToExecute)
            proc = Popen(commandToExecute, shell=True)
            returnCode = proc.wait()
            if(returnCode!=0):
                error.errorcode=returnCode
                error.code=CommonVariables.folder_conflict_error
                error.info="commandToExecute is "+commandToExecute
                print('mkdir returnCode is ' + str(returnCode))
                return error

            commandToExecute = '/bin/bash -c "mount /dev/mapper/' + self.paras.mountname + ' ' + (self.paras.mountpoint + self.paras.mountname) + ' 2> /dev/null"'
            print(commandToExecute)
            proc = Popen(commandToExecute, shell=True)
            returnCode = proc.wait()
            if(returnCode!=0):
                error.errorcode=returnCode
                error.code=CommonVariables.mount_error
                error.info="commandToExecute is "+commandToExecute
                print('mount returnCode is ' + str(returnCode))
                return error

        elif(self.paras.command == 'folder'):
            commandToExecute = 'ecryptfs-setup-private'
            proc = Popen(commandToExecute, shell=True)
            returnCode = proc.wait() 
            if(returnCode!=0):
                error.errorcode=returnCode
                print('returnCode is ' + str(returnCode))
                return error
        return error

