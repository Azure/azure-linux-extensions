#!/usr/bin/env python
#
#CustomScript extension
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
import xml.parsers.expat
from Utils import HandlerUtil
from common import CommonVariables


# parameter format should be like this:
# {"command":"disk","path":"/dev/xvdc","filesystem":"ext4","mountname":"mountname","mountpoint":"/mnt/","password":"password1","passphrase":"User@123"}
# {"command":"folder","path":"/home/andy/Private","password":"password1"}
class ParameterParser(object):

    def __init__(self, protected_settings, public_settings):
        """
        TODO: we should validate the parameter first
        """
        self.command = protected_settings.get('command')
        self.path = protected_settings.get('path')
        self.filesystem = protected_settings.get('filesystem')
        self.mountname = protected_settings.get('mountname')
        self.mountpoint = protected_settings.get('mountpoint')
        #password is the password of the pfx file.
        self.password = protected_settings.get('password')
        self.passphrase=protected_settings.get('passphrase')
        self.keyaddess = protected_settings.get('key_address')

    def validate(self):
        # 0 means ok
        # 1 means 
        return 0;