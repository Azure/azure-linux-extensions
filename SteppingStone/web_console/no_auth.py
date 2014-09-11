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
import shutil

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

from settings import *
from base_auth import BaseAuth

class NoAuth(BaseAuth):
    def __init__(self):
        super(NoAuth, self).__init__()

    def install_extension(self):
        extension = EXTENSION_NOAUTH_WITH_VERSION + '.tar.gz'
        if not os.path.isdir(EXTENSION_NOAUTH):
            waagent.Run(' '.join(['wget --no-check-certificate', SRC_URI + extension]))
            waagent.Run(' '.join(['tar zxf', extension]))
            waagent.Run(' '.join(['rm -f', extension]))
            waagent.Run(' '.join(['ln -s', EXTENSION_NOAUTH_WITH_VERSION, EXTENSION_NOAUTH]))

    def configure(self):
        self.replace_conf(GUAC_PROPERTIES, ['auth-provider', 'basic-user-mapping'], NOAUTH_CONF)
        shutil.copy(os.path.join(EXTENSION_NOAUTH, 'lib/' + EXTENSION_NOAUTH_WITH_VERSION + '.jar'), GUAC_CLASSPATH)
        waagent.SetFileContents(os.path.join(GUAC_CONF_DIR, NOAUTH_CONF_FILE), NOAUTH_CONF_FILE_CONTENTS)
        waagent.Run('service guacd restart')
        waagent.Run('service tomcat6 restart')
