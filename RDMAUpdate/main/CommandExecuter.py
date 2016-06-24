#!/usr/bin/env python
#
# VMEncryption extension
#
# Copyright 2015 Microsoft Corporation
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

import subprocess
import os
import os.path
import shlex
import sys
from subprocess import *

class CommandExecuter(object):
    """description of class"""
    def __init__(self, logger):
        self.logger = logger

    def Execute(self, command_to_execute):
        self.logger.log("Executing:" + command_to_execute)
        args = shlex.split(command_to_execute)
        proc = Popen(args)
        returnCode = proc.wait()
        return returnCode

    def RunGetOutput(self, command_to_execute):
        try:
            output=subprocess.check_output(command_to_execute,stderr=subprocess.STDOUT,shell=True)
            return 0,output.decode('latin-1')
        except subprocess.CalledProcessError as e :
            self.logger.log('CalledProcessError.  Error Code is ' + str(e.returncode)  )
            self.logger.log('CalledProcessError.  Command string was ' + e.cmd  )
            self.logger.log('CalledProcessError.  Command result was ' + (e.output[:-1]).decode('latin-1'))
            return e.returncode,e.output.decode('latin-1')
