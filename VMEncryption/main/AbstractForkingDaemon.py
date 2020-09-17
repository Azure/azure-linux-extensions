#!/usr/bin/env python
#
# VMEncryption extension
#
# Copyright 2019 Microsoft Corporation
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

class AbstractForkingDaemon(object):
    def __init__(self, logger, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        self.logger = logger
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr

    def double_fork(self):
        """
        do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        """
        try:
                pid = os.fork()
                if pid > 0:
                        # tell first parent that they are the parent
                        return True
        except OSError as e:
                self.logger.log('fork #1 failed: {0}\n'.format(e))
                return True

        # decouple from parent environment
        os.setsid()
        os.umask(0)

        # do second fork
        try:
                pid = os.fork()
                if pid > 0:
                        # exit from second parent
                        sys.exit(0)
        except OSError as e:
                self.logger.log('fork #2 failed: {0}\n'.format(e))
                sys.exit(1)

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = file(self.stdin, 'r')
        so = file(self.stdout, 'a+')
        se = file(self.stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        return False # False, because this is the child process

    def start_daemon(self):
        # Do a double fork
        am_i_parent = self.double_fork()

        if am_i_parent:
            return
        
        # Now this is the child, hopefully will not be killed by waagent
        self.run()