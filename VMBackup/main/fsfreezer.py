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
    self.errors = []
    def __init__(self):
        pass

class FsFreezer:
    def __init__(self, logger):
        """
        """
        self.mounts = Mounts()
        self.logger = logger

    def freeze(self, mount):
        """
        for xfs we should use the xfs_freeze
        """
        path = mount.dir
        self.logger.log('freeze...' + path + ' type ' + mount.type)
        freeze_return_code = 0
        if(mount.type == 'xfs'):
            freeze_return_code = subprocess.call(['xfs_freeze', '-u', path])
        else:
            freeze_return_code = subprocess.call(['fsfreeze', '-f', path])
        self.logger.log('freeze_result...' + str(freeze_return_code))
        return freeze_return_code

    def unfreeze(self, mount):
        """
        for xfs we should use the xfs_freeze -u 
        """
        path = mount.dir
        self.logger.log('unfreeze...' + path + ' type ' + mount.type)
        unfreeze_return_code = 0 
        if(mount.type == 'xfs'):
            unfreeze_return_code = subprocess.call(['xfs_freeze', '-u', path])
        else:
            unfreeze_return_code = subprocess.call(['fsfreeze', '-u', path])
        self.logger.log('unfreeze_result...' + str(unfreeze_return_code))
        return unfreeze_return_code

    def freezeall(self):
            self.root_seen = False
            freezeResult = FreezeResult()
            for mount in self.mounts.mounts:
                if(mount.dir == '/'):
                    self.root_seen = True
                    self.root_mount = mount
                elif(mount.dir and mount.dir.startswith('/dev') and mount.type != 'iso9660' and mount.type != 'vfat'):
                    try:
                        freeze_return_code = self.freeze(mount)
                        if(freeze_return_code != 0):
                            freezeError = FreezeError()
                            freezeError.errorcode = freeze_return_code
                            freezeError.path = mount.dir
                            freezeResult.errors.append(freezeError)
                    except Exception, e:
                        freezeError = FreezeError()
                        freezeError.errorcode = -1
                        freezeError.path = mount.dir
                        freezeResult.errors.append(freezeError)
                        self.logger.log(str(e))

            if(self.root_seen):
                freeze_return_code = self.freeze(self.root_mount)
                if(freeze_return_code != 0):
                    freezeError = FreezeError()
                    freezeError.errorcode = freeze_return_code
                    freezeError.path = mount.dir
                    freezeResult.errors.append(freezeError)

    def unfreezeall(self):
            self.root_seen = False
            unfreezeResult = FreezeResult()
            for mount in self.mounts.mounts:
                if(mount.dir == '/'):
                    self.root_seen = True
                    self.root_mount = mount
                elif(mount.dir and mount.dir.startswith('/dev') and mount.type != 'iso9660' and mount.type != 'vfat'):
                    try:
                        unfreeze_return_code = self.unfreeze(mount)
                        if(unfreeze_return_code != 0):
                            unfreezeError = FreezeError()
                            unfreezeError.errorcode = unfreeze_return_code
                            unfreezeError.path = mount.dir
                            unfreezeResult.errors.append(unfreezeError)
                    except Exception,e:
                        unfreezeError = FreezeError()
                        unfreezeError.errorcode = -1
                        unfreezeError.path = mount.dir
                        unfreezeResult.errors.append(unfreezeError)
                        self.logger.log(str(e))
            if(self.root_seen):
                unfreeze_return_code = self.unfreeze(self.root_mount)
                if(unfreeze_return_code != 0):
                    unfreezeError = FreezeError()
                    unfreezeError.errorcode = unfreeze_return_code
                    unfreezeError.path = mount.dir
                    unfreezeResult.errors.append(unfreezeError)

