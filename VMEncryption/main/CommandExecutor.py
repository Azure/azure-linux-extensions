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

import shlex
from threading import Timer
from subprocess import Popen, PIPE
import traceback

class ProcessCommunicator(object):
    def __init__(self):
        self.stdout = None
        self.stderr = None

class CommandExecutor(object):
    """description of class"""
    def __init__(self, logger):
        self.logger = logger

    def get_text(self, s):
        # decode data to str in python3, or leave as str in python2
        try:
            basestring
        except NameError:
            basestring = str
        if isinstance(s, basestring):
            return s
        else:
            return s.decode('utf-8')

    def Execute(self, command_to_execute, raise_exception_on_failure=False, communicator=None, input=None, suppress_logging=False, timeout=0):
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
                    # traceback format_exc converts exception to string 
                    self.logger.log("Process creation failed: " + traceback.format_exc())
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
            # for python2 and python3 compatibility, first decode 
            # std[out|err] bytes, converting from data to string
            communicator.stdout = self.get_text(stdout)
            communicator.stderr = self.get_text(stderr)

        if int(return_code) != 0:
            msg = "Command {0} failed with return code {1}".format(command_to_execute, return_code)
            # for python2 and python3 compatibility, first decode 
            # std[out|err] bytes, converting from data to string
            msg += "\nstdout:\n" + self.get_text(stdout)
            msg += "\nstderr:\n" + self.get_text(stderr)

            if not suppress_logging:
                self.logger.log(msg)

            if raise_exception_on_failure:
                raise Exception(msg)

        return return_code
    
    def ExecuteInBash(self, command_to_execute, raise_exception_on_failure=False, communicator=None, input=None, suppress_logging=False):
        command_to_execute = 'bash -c "{0}{1}"'.format('set -e; ' if raise_exception_on_failure else '',
                                                      command_to_execute)
        
        return self.Execute(command_to_execute, raise_exception_on_failure, communicator, input, suppress_logging)
