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
# {"command":"disk","path":"/dev/xvdc","filesystem":"ext4","mountpoint":"/mnt/xvdc","password":"password1"}
# {"command":"folder","path":"/home/andy/Private","password":"password1"}
class ParameterParser(object):
    #def start_element(self, name, attrs):
    #    print 'Start element:', name, attrs
    #    if(name.lower()=='blob'):
    #        self.blobs.append(attrs['address'])
    #def end_element(self, name):
    #    print 'End element:', name
    #def char_data(self, data):
    #    print 'Character data:', repr(data)

    def __init__(self, protected_settings, public_settings):
        """
        TODO: we should validate the parameter first
        """
        self.command = protected_settings.get('command')
        self.path = protected_settings.get('path')
        self.password = protected_settings.get('password')
        self.filesystem = protected_settings.get('filesystem')
        self.mountpoint = protected_settings.get('mountpoint')