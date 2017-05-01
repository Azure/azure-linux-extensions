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
    A class that handles periodic monitoring activities that are requested for LAD to perform.
    The first such activity is to watch /etc/fstab and report (log to console) if there's anything
    wrong with that. There might be other such monitoring activities that will be added later.
    """

    def __init__(self, hutil_error, hutil_log, log_to_console=False):
        """
        Constructor.
        :param hutil_error: Error logging function (e.g., hutil.error). This is not a stream.
        :param hutil_log: Normal logging function (e.g., hutil.log). This is not a stream.
        :param log_to_console: Indicates whether to log any issues to /dev/console or not.
        """
        # This is only for the /etc/fstab watcher feature.
        self._fstab_last_mod_time = os.path.getmtime('/etc/fstab')

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

    def handle_fstab(self, ignore_time=False):
        """
        Watches if /etc/fstab is modified and verifies if it's OK. Otherwise, report it in logs or to /dev/console.
        :param ignore_time: Disable the default logic of delaying /etc/fstab verification by 1 minute.
                            This is to allow any test code to avoid waiting 1 minute unnecessarily.
        :return: None
        """
        try_mount = False
        if ignore_time:
            try_mount = True
        else:
            current_mod_time = os.path.getmtime('/etc/fstab')
            current_mod_date_time = datetime.datetime.fromtimestamp(current_mod_time)

            # Only try to mount if it's been at least 1 minute since the 
            # change to fstab was done, to prevent spewing out erroneous spew
            if (current_mod_time != self._fstab_last_mod_time and
                datetime.datetime.now() > current_mod_date_time +
                    datetime.timedelta(minutes=1)):
                try_mount = True
                self._fstab_last_mod_time = current_mod_time

        ret = 0
        if try_mount:
            ret = subprocess.call(['sudo', 'mount', '-a', '-vf'])
            if ret != 0:
                # There was an error running mount, so log
                error_msg = 'fstab modification failed mount validation.  Please correct before reboot.'
                self._hutil_error(error_msg)
                self._do_log_to_console_if_enabled(error_msg)
            else:
                # No errors
                self._hutil_log('fstab modification passed mount validation')
        return ret

    def set_imds_logger(self, imds_logger):
        self._imds_logger = imds_logger

    def watch(self):
        """
        Main loop performing various monitoring activities periodically.
        Currently iterates every 5 minutes, and other periodic activities might be
        added in the loop later.
        :return: None
        """
        while True:
            # /etc/fstab watcher
            self.handle_fstab()

            # IMDS probe (only sporadically, inside the function)
            if self._imds_logger:
                try:
                    self._imds_logger.log_imds_data_if_right_time()
                except Exception as e:
                    self._hutil_error('ImdsLogger exception: {0}\nStacktrace: {1}'.format(e, traceback.format_exc()))

            # Sleep 5 minutes
            time.sleep(60 * 5)
        pass
