#!/usr/bin/env python
#
# OmsAgentForLinux Extension
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
import datetime
import time
import string
import traceback
import shutil

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
    
    def write_waagent_event(event):
        offset = ustr(int(time.time() * 1000000))
        fn = '/var/lib/waagent/events/{}.tld'.format(offset)

        with open(fn + '.tmp') as fh:
            fh.write(event)
        shutil.move(fn + '.tmp', fn)    
    
    def create_telemetry_event(self):
        template = 
	""" {
    		"eventId": 1,
    		"providerId": "69B669B9-4AF8-4C50-BDC4-6006FA76E975",
    		"parameters": [
        		{
            			"name": "Name",
            			"value": "Microsoft.EnterpriseCloud.Monitoring.OmsLinuxAgent"
        		},
        		{
            			"name": "Version",
            			"value": "1.6"
        		},
        		{
            			"name": "Operation",
            			"value": "{}"
        		},
        		{
            			"name": "OperationSuccess",
            			"value": {}
        		},
        		{
            			"name": "Message",
            			"value": "{}"
        		},
        		{
            			"name": "Duration",
            			"value": {}
        		}
    		]
	    }"""
	
	return template.format("ODSIngestion","true","Success","300000")
	
    def upload_telemetry(self):
        pass         

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
            
            self.upload_telemetry()
	        
            # Sleep 5 minutes
            self._hutil_log('watcher thread sleeping')
            time.sleep(60 * 5)
        
        pass
