#!/usr/bin/env python
#
# Azure Linux extension
#
# Linux Azure Diagnostic Extension (Current version is specified in manifest.xml)
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import subprocess
import os
import datetime
import time
import string
import traceback


class Watcher:
    """
    A class that handles periodic monitoring activities.
    """

    def __init__(self, hutil_error, hutil_log, log_to_console=False):
        """
        Constructor.
        :param hutil_error: Error logging function (e.g., hutil.error). This is not a stream.
        :param hutil_log: Normal logging function (e.g., hutil.log). This is not a stream.
        :param log_to_console: Indicates whether to log any issues to /dev/console or not.
        """
        self._hutil_error = hutil_error
        self._hutil_log = hutil_log
        self._log_to_console = log_to_console

        self._imds_logger = None

    def _do_log_to_console_if_enabled(self, message):
        """
        Write 'message' to console. Stolen from waagent LogToCon().
        """
        if self._log_to_console:
            try:
                with open('/dev/console', 'w') as console:
                    message = filter(lambda x: x in string.printable, message)
                    console.write(message.encode('ascii', 'ignore') + '\n')
            except IOError as e:
                self._hutil_error('Error writing to console. Exception={0}'.format(e))


    def watch(self):
        """
        Main loop performing various monitoring activities periodically.
        Currently iterates every 5 minutes, and other periodic activities might be
        added in the loop later.
        :return: None
        """
        self._hutil_log('started watcher thread')
        while True:
	    self._hutil_log('watcher thread waking')

	    # Sleep 5 minutes
	    self._hutil_log('watcher thread sleeping')
            time.sleep(60 * 5)
        pass
