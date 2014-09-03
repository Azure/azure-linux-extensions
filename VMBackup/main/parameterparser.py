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

class ParameterParser(object):
    def start_element(self, name, attrs):
        print 'Start element:', name, attrs
        if(name.lower()=='blob'):
            self.blobs.append(attrs['address'])
    def end_element(self, name):
        print 'End element:', name
    def char_data(self, data):
        print 'Character data:', repr(data)

    def __init__(self, protected_settings, public_settings):
        """
        TODO: we should validate the parameter first
        """
        self.blobs = []
        self.logsBlobUri = protected_settings.get('LogsBlobUri')
        self.serObjStrInput = protected_settings.get('SerObjStrInput')
        
        self.commandToExecute = public_settings.get('CommandToExecute')
        p = xml.parsers.expat.ParserCreate()
        p.StartElementHandler = self.start_element
        p.EndElementHandler = self.end_element
        p.CharacterDataHandler = self.char_data
        p.Parse(self.serObjStrInput)
