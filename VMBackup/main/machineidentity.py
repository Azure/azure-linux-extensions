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

import os
import subprocess

class MachineIdentity:
    def __init__(self):
        self.store_identity_file = './machine_identity_FD76C85E-406F-4CFA-8EB0-CF18B123365C'
        self.machine_identity_file = '/var/machine_identity_FD76C85E-406F-4CFA-8EB0-CF18B123365C-origin'

    def current_identity(self):
        #/var/lib/dbus/machine-id
        identity = None
        if(os.path.exists(self.machine_identity_file)):
            file = open(self.machine_identity_file, 'r')
            identity = file.read()
            file.close()
        else:
            p = subprocess.Popen(['uuidgen'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            identity, err = p.communicate()
            file = open(self.machine_identity_file, 'w')
            file.write(identity);
            file.close()
        return identity

    def save_identity(self):
        file = open(self.store_identity_file,'w')
        machine_identity = self.current_identity()
        print(machine_identity)
        file.write(machine_identity)
        file.close()

    def stored_identity(self):
        identity_stored = None
        if(os.path.exists(self.store_identity_file)):
            file = open(self.store_identity_file,'r')
            identity_stored = file.read()
            file.close()
        return identity_stored

