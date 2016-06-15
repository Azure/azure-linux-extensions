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
import datetime
import threading

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

class FsFreezer:
    def __init__(self, patching, logger):
        """
        """
        self.patching = patching
        self.logger = logger
        self.mounts = Mounts(patching = self.patching, logger = self.logger)
        self.frozen_items = set()
        self.unfrozen_items = set()

    def freeze(self, mount):
        """
        for xfs we should use the xfs_freeze, or we just use fsfreeze
        """
        global unfreeze_done
        freeze_error = FreezeError()
        path = mount.mount_point
        freeze_return_code = 0
        if not unfreeze_done:
            if(path in self.frozen_items):
                self.logger.log("skipping the mount point because we already freezed it")
            else:
                self.logger.log('freeze...')
                if(self.should_skip(mount)):
                    self.logger.log('skip for the unknown file systems')
                else:
                    before_freeze = datetime.datetime.utcnow()
                    self.frozen_items.add(path)
                    freeze_return_code = subprocess.call(['fsfreeze', '-f', path])
                    after_freeze=datetime.datetime.utcnow()
                    time_taken=after_freeze-before_freeze
                    self.logger.log('time taken for freeze :' + str(time_taken))
                self.logger.log('freeze_result...' + str(freeze_return_code))
            freeze_error.errorcode = freeze_return_code

        if(freeze_return_code != 0):
            freeze_error.path = path
        return freeze_error

    def unfreeze(self, mount):
        """
        for xfs we should use the xfs_freeze -u, or we just use fsfreeze -u
        """
        freeze_error = FreezeError()
        path = mount.mount_point
        self.logger.log('unfreeze...')
        unfreeze_return_code = 0 
        if(self.should_skip(mount)):
            self.logger.log('skip for the type ')
        else:
            if(not path in self.unfrozen_items):
                freeze_return_code = 0
                self.unfrozen_items.add(path)
                unfreeze_return_code = subprocess.call(['fsfreeze', '-u', path])
            else:
                self.logger.log('the item is already unfreezed, so skip it')
        self.logger.log('unfreeze_result...' + str(unfreeze_return_code))
        freeze_error.errorcode = unfreeze_return_code
        if(unfreeze_return_code != 0):
            freeze_error.path = path
        return freeze_error

    def should_skip(self, mount):
        if((mount.fstype == 'ext3' or mount.fstype == 'ext4' or mount.fstype == 'xfs' or mount.fstype == 'btrfs') and mount.type != 'loop'):
            return False
        else:
            return True

    def freezeall(self):
        global unfreeze_done
        unfreeze_done= False
        self.root_seen = False
        freeze_result = FreezeResult()
        for mount in self.mounts.mounts:
            if(mount.mount_point == '/'):
                self.root_seen = True
                self.root_mount = mount
            elif(mount.mount_point):
                try:
                    freezeError = self.freeze(mount)
                    if(freezeError.errorcode != 0):
                        freeze_result.errors.append(freezeError)
                except Exception, e:
                    freezeError = FreezeError()
                    freezeError.errorcode = -1
                    freezeError.path = mount.mount_point
                    freeze_result.errors.append(freezeError)
                    self.logger.log(str(e))

        if(self.root_seen):
            freezeError = self.freeze(self.root_mount)
            if(freezeError.errorcode != 0):
                freeze_result.errors.append(freezeError)
        return freeze_result

    def unfreezeall(self):
        global unfreeze_done
        self.root_seen = False
        unfreeze_result = FreezeResult()
        try:
            commandToExecute="kill $(ps aux | grep \'fsfreeze\' | awk \'{print $2}\')"
            subprocess.call(commandToExecute,shell=True)
        except Exception,e:
            self.logger.log('killing fsfreeze running process failed')
        unfreeze_done= True
        for mount in self.mounts.mounts:
            if(mount.mount_point == '/'):
                self.root_seen = True
                self.root_mount = mount
            elif(mount.mount_point):
                try:
                    freezeError = self.unfreeze(mount)
                    if(freezeError.errorcode != 0):
                        unfreeze_result.errors.append(freezeError)
                except Exception,e:
                    freezeError = FreezeError()
                    freezeError.errorcode = -1
                    freezeError.path = mount.mount_point
                    unfreeze_result.errors.append(freezeError)
        if(self.root_seen):
            freezeError = self.unfreeze(self.root_mount)
            if(freezeError.errorcode != 0):
                unfreeze_result.errors.append(freezeError)
        return unfreeze_result
