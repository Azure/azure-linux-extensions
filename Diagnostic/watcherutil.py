#!/usr/bin/env python
#
# Azure Linux extension
#
# Linux Azure Diagnostic Extension (Current version is specified in manifest.xml)
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import logging
import subprocess
import os
import datetime


class Watcher():

    def __init__(self, errorStream, outputStream, logtoconsole=False):
        self.lastModTime = os.path.getmtime('/etc/fstab')

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        ch = logging.StreamHandler(errorStream)
        ch.setLevel(logging.WARNING)
        self.logger.addHandler(ch)
        ch = logging.StreamHandler(outputStream)
        ch.setLevel(logging.INFO)
        self.logger.addHandler(ch)

        if logtoconsole:
            ch = logging.FileHandler('/dev/console')
            ch.setLevel(logging.WARNING)
            self.logger.addHandler(ch)

    def handle_fstab(self, ignoretime=False):
        tryMount = False
        if ignoretime:
            tryMount = True
        else:
            currentModTime = os.path.getmtime('/etc/fstab')
            currentModDateTime = datetime.datetime.fromtimestamp(currentModTime)

            # Only try to mount if it's been at least 1 minute since the 
            # change to fstab was done, to prevent spewing out erroneous spew
            if (currentModTime != self.lastModTime and
                datetime.now() > currentModDateTime +
                    datetime.timedelta(minutes=1)):
                tryMount = True
                self.lastModTime = currentModTime

        ret = 0
        if tryMount:
            ret = subprocess.call(['sudo', 'mount', '-a', '-vf'])
            if ret != 0:
                # There was an error running mount, so log
                self.logger.error('fstab modification failed mount validation.  Please correct before reboot.')
            else:
                # No errors
                self.logger.info('fstab modification passed mount validation')
        return ret

    def watch(self):
        while (True):
            self.handle_fstab()
            time.sleep(60 * 5) # Sleep 5 minutes
        pass


