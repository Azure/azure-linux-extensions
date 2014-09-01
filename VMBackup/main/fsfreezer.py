#!/usr/bin/env python

#-------------------------------------------------------------------------
# Copyright (c) Microsoft.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#--------------------------------------------------------------------------
import subprocess
from mounts import Mounts
class FsFreezer:
    def __init__(self):
        """
        """
        self.mounts = Mounts()

    def freeze(self, path):
        print('freeze...' + path);
        freeze_result = subprocess.call(['fsfreeze', '-f', path])
        print('freeze_result...' + str(freeze_result));

    def unfreeze(self, path):
        print('unfreeze...' + path);
        unfreeze_result = subprocess.call(['fsfreeze', '-u', path])
        print('unfreeze_result...' +  str(unfreeze_result))

    def freezeall(self):
            self.root_seen = False            
            for mount in self.mounts.mounts:
                if(mount.dir!='/'):
                    self.root_seen = True
                elif(mount.dir and mount.dir.startswith('/dev') and mount.type != 'iso9660' and mount.type != 'vfat'):
                    try:
                        self.freeze(mount.dir)
                    except Exception, e:
                        pass

            if(self.root_seen):
                self.freeze('/')

    def unfreezeall(self):
            self.root_seen = False
            
            for mount in self.mounts.mounts:
                if(mount.dir!='/'):
                    self.root_seen = True
                elif(mount.dir and mount.dir.startswith('/dev') and mount.type != 'iso9660' and mount.type != 'vfat'):
                    try:
                        self.unfreeze(mount.dir)
                    except Exception,e:
                        pass
            if(self.root_seen):
                self.unfreeze('/')

