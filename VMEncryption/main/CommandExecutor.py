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

import os
import os.path
import shlex
import sys

from subprocess import *
from threading import Timer

class ProcessCommunicator(object):
    def __init__(self):
        self.stdout = None
        self.stderr = None

class CommandExecutor(object):
    """description of class"""
    def __init__(self, logger):
        self.logger = logger

    def Execute(self, command_to_execute, raise_exception_on_failure=False, communicator=None, input=None, suppress_logging=False, timeout=0):
        if type(command_to_execute) == unicode:
            command_to_execute = command_to_execute.encode('ascii', 'ignore')

        if not suppress_logging:
            self.logger.log("Executing: {0}".format(command_to_execute))
        args = shlex.split(command_to_execute)
        proc = None
        timer = None
        return_code = None

        try:
            proc = Popen(args, stdout=PIPE, stderr=PIPE, stdin=PIPE, close_fds=True)
        except Exception as e:
            if raise_exception_on_failure:
                raise
            else:
                if not suppress_logging:
                    self.logger.log("Process creation failed: " + str(e))
                return -1

        def timeout_process():
            proc.kill()
            self.logger.log("Command {0} didn't finish in {1} seconds. Timing it out".format(command_to_execute, timeout))

        try:
            if timeout>0:
                timer = Timer(timeout, timeout_process)
                timer.start()
            stdout, stderr = proc.communicate(input=input)
        finally:
            if timer is not None:
                timer.cancel()
            return_code = proc.returncode

        if isinstance(communicator, ProcessCommunicator):
            communicator.stdout, communicator.stderr = stdout, stderr

        if int(return_code) != 0:
            msg = "Command {0} failed with return code {1}".format(command_to_execute, return_code)
            msg += "\nstdout:\n" + stdout
            msg += "\nstderr:\n" + stderr

            if not suppress_logging:
                self.logger.log(msg)

            if raise_exception_on_failure:
                raise Exception(msg)

        return return_code
    
    def ExecuteInBash(self, command_to_execute, raise_exception_on_failure=False, communicator=None, input=None, suppress_logging=False):
        command_to_execute = 'bash -c "{0}{1}"'.format('set -e; ' if raise_exception_on_failure else '',
                                                      command_to_execute)
        
        return self.Execute(command_to_execute, raise_exception_on_failure, communicator, input, suppress_logging)
