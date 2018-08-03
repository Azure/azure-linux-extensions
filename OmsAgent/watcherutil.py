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
import sys
import json
import uuid

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

    def write_waagent_event(self, event):
        offset = str(int(time.time() * 1000000))

        temp_fn = '/var/lib/waagent/events/'+str(uuid.uuid4())
        with open(temp_fn,'w+') as fh:
            fh.write(event)

        fn_template = '/var/lib/waagent/events/{}.tld'
        fn = fn_template.format(offset)
        while os.path.isfile(fn):
            offset += 1
            fn = fn_template.format(offset)

        shutil.move(temp_fn, fn)

        self._hutil_log(fn)

    def create_telemetry_event(self, operation, operation_success, message, duration):
        template = """ {{
    		"eventId": 1,
    		"providerId": "69B669B9-4AF8-4C50-BDC4-6006FA76E975",
    		"parameters": [
                        {{
            			"name": "Name",
            			"value": "Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux"
        		}},
                        {{
            			"name": "Version",
            			"value": "1.7.3"
        		}},
                        {{
            			"name": "Operation",
            			"value": "{}"
        		}},
                        {{
            			"name": "OperationSuccess",
            			"value": {}
        		}},
                        {{
            			"name": "Message",
            			"value": "{}"
        		}},
                        {{
            			"name": "Duration",
            			"value": {}
        		}}
    		]
            }}"""

        operation_success_as_string = str(operation_success).lower()
        formatted_message = message.replace("\n", "\\n").replace("\t", "\\t").replace('"', '\"')

        return template.format(operation, operation_success_as_string, formatted_message, duration)

    def upload_telemetry(self):
        status_files = [
                "/var/opt/microsoft/omsagent/log/ODSIngestion.status",
                "/var/opt/microsoft/omsagent/log/ODSIngestionBlob.status",
                "/var/opt/microsoft/omsagent/log/ODSIngestionAPI.status",
                "/var/opt/microsoft/omsconfig/status/dscperformconsistency",
                "/var/opt/microsoft/omsconfig/status/dscperforminventory",
                "/var/opt/microsoft/omsconfig/status/dscsetlcm"
            ]
        for sf in status_files:
            if os.path.isfile(sf):
                mod_time = os.path.getmtime(sf)
                curr_time = int(time.time())
                if (curr_time - mod_time < 300):
                    with open(sf) as json_file:
                        try:
                            status_data = json.load(json_file)
                            operation = status_data["operation"]
                            operation_success = status_data["success"]
                            message = status_data["message"]

                            event = self.create_telemetry_event(operation,operation_success,message,"300000")
                            self._hutil_log("Writing telemetry event: "+event)
                            self.write_waagent_event(event)
                            self._hutil_log("Successfully processed telemetry status file: "+sf)

                        except Exception as e:
                            self._hutil_log("Error parsing telemetry status file: "+sf)
                            self._hutil_log("Exception info: "+traceback.format_exc())
                else:
                    self._hutil_log("Telemetry status file not updated in last 5 mins: "+sf)
            else:
                self._hutil_log("Telemetry status file does not exist: "+sf)
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
