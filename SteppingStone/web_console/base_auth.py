#!/usr/bin/python
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
# Requires Python 2.4+

import os
import sys

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

from settings import *

class BaseAuth(object):
    def __init__(self):
        if not os.path.isdir(GUAC_CLASSPATH):
            os.mkdir(GUAC_CLASSPATH)
        self.add_lib_directory()

    def add_lib_directory(self):
        self.replace_conf(GUAC_PROPERTIES, ['lib-directory'], 'lib-directory: ' + GUAC_CLASSPATH)


    def replace_conf(self, file_name, old_lines, new_lines):
        lines = waagent.GetFileContents(file_name).split('\n')
        contents = ''
        for line in lines:
            if line.split(':')[0].strip() not in old_lines:
                contents += line + '\n'
        contents += new_lines + '\n'
        waagent.SetFileContents(file_name, contents)

    def install_extension(self):
        pass

    def configure(self):
        pass
