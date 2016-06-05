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
#
# Requires Python 2.7+
#

import subprocess
import os
import os.path
import shlex
import sys
from subprocess import *

class CommandExecutor(object):
    """description of class"""
    def __init__(self, logger):
        self.logger = logger

    def Execute(self, command_to_execute, raise_exception_on_failure=False):
        self.logger.log("Executing: {0}".format(command_to_execute))
        args = shlex.split(command_to_execute)
        proc = Popen(args)
        return_code = proc.wait()

        if raise_exception_on_failure and int(return_code) != 0:
            raise Exception("Command {0} failed with return code {1}".format(command_to_execute,
                                                                             return_code))

        return return_code
    
    def ExecuteInBash(self, command_to_execute, raise_exception_on_failure=False):
        command_to_execute = 'bash -c "{0}{1}"'.format('set -e; ' if raise_exception_on_failure else '',
                                                      command_to_execute)
        
        return self.Execute(command_to_execute, raise_exception_on_failure)
