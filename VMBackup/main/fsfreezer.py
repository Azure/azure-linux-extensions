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
from main.mounts import Mounts
class FsFreezer:
    def __init__(self):
        """
        """

    def freeze(self, path):
        #print('freeze...' + path);
        subprocess.call(['fsfreeze', '-f', path])

    def unfreeze(self, path):
        #print('unfreeze...' + path);
        subprocess.call(['fsfreeze', '-u', path])

    def freezeall(self):
            self.root_seen = False
            mounts = Mounts()
            for mount in mounts.mounts:
                #print(mount.device + ' ' + mount.type + ' ' + mount.dir + ' ' + mount.opts + ' '+ str(mount.dir.startswith('/dev')))
                if(mount.dir!='/'):
                    self.root_seen = True
                elif(mount.dir and mount.dir.startswith('/dev') and mount.type != 'iso9660' and mount.type != 'vfat'):
                    self.freeze(mount.dir)

            if(self.root_seen):
                self.freeze('/')

    def unfreezeall(self):
            self.root_seen = False
            mounts = Mounts()
            for mount in mounts.mounts:
                #print(mount.device + ' ' + mount.type + ' ' + mount.dir + ' ' + mount.opts)
                if(mount.dir!='/'):
                    self.root_seen = True
                elif(mount.dir and mount.dir.startswith('/dev') and mount.type != 'iso9660' and mount.type != 'vfat'):
                    self.unfreeze(mount.dir)

            if(self.root_seen):
                self.unfreeze('/')

