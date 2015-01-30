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
#
# Requires Python 2.7+
#
import subprocess
from mounts import Mounts

class FreezeError(object):
    def __init__(self):
        self.errorcode = None
        self.fstype = None
        self.path = None

class FreezeResult(object):
    def __init__(self):
        self.errors = []
    def __str__(self):
        return 'errors' + str(self.errors)

class FsFreezer:
    def __init__(self, logger):
        """
        """
        self.mounts = Mounts('/','/etc/fstab')
        self.logger = logger

    def freeze(self, mount):
        """
        for xfs we should use the xfs_freeze, or we just use fsfreeze
        """
        freeze_error = FreezeError()
        path = mount.dir
        self.logger.log('freeze...' + path + ' type ' + mount.type)
        freeze_return_code = 0
        if(self.should_skip(mount)):
            self.logger.log('skip for devtmpfs and devpts '+str(mount.type))
        elif(mount.type == 'xfs'):
            freeze_return_code = subprocess.call(['xfs_freeze', '-u', path])
        else:
            freeze_return_code = subprocess.call(['fsfreeze', '-f', path])
        self.logger.log('freeze_result...' + str(freeze_return_code))
        freeze_error.errorcode = freeze_return_code
        if(freeze_return_code!=0):
            freeze_error.path=path
        return freeze_error

    def unfreeze(self, mount):
        """
        for xfs we should use the xfs_freeze -u, or we just use fsfreeze -u
        """
        freeze_error = FreezeError()
        path = mount.dir
        self.logger.log('unfreeze...' + path + ' type ' + mount.type)
        unfreeze_return_code = 0 
        if(self.should_skip(mount)):
            self.logger.log('skip for the type ' + str(mount.type))
        elif(mount.type == 'xfs'):
            unfreeze_return_code = subprocess.call(['xfs_freeze', '-u', path])
        else:
            unfreeze_return_code = subprocess.call(['fsfreeze', '-u', path])
        self.logger.log('unfreeze_result...' + str(unfreeze_return_code))
        freeze_error.errorcode = unfreeze_return_code
        if(unfreeze_return_code!=0):
            freeze_error.path=path
        return freeze_error

    def should_skip(self, mount):
        if(mount.type == 'ext3' or mount.type=='ext4' or mount.type=='xfs' or mount.type=='btrfs'):
            return False
        else:
            return True

    def freezeall(self):
            self.root_seen = False
            freeze_result = FreezeResult()
            for mount in self.mounts.mounts:
                if(mount.dir == '/'):
                    self.root_seen = True
                    self.root_mount = mount
                elif(mount.dir):
                    try:
                        freezeError = self.freeze(mount)
                        if(freezeError.errorcode != 0):
                            freeze_result.errors.append(freezeError)
                    except Exception, e:
                        freezeError = FreezeError()
                        freezeError.errorcode = -1
                        freezeError.path = mount.dir
                        freeze_result.errors.append(freezeError)
                        self.logger.log(str(e))

            if(self.root_seen):
                freezeError = self.freeze(self.root_mount)
                if(freezeError.errorcode != 0):
                    freeze_result.errors.append(freezeError)
            return freeze_result

    def unfreezeall(self):
            self.root_seen = False
            unfreeze_result = FreezeResult()
            for mount in self.mounts.mounts:
                if(mount.dir == '/'):
                    self.root_seen = True
                    self.root_mount = mount
                elif(mount.dir):
                    try:
                        freezeError = self.unfreeze(mount)
                        if(freezeError.errorcode != 0):
                            unfreeze_result.errors.append(freezeError)
                    except Exception,e:
                        freezeError = FreezeError()
                        freezeError.errorcode = -1
                        freezeError.path = mount.dir
                        unfreeze_result.errors.append(freezeError)
            if(self.root_seen):
                freezeError = self.unfreeze(self.root_mount)
                if(freezeError.errorcode != 0):
                    unfreeze_result.errors.append(freezeError)
            return unfreeze_result

