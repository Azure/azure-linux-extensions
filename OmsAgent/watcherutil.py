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
import io
import datetime
from datetime import datetime, timedelta
import time
import string
import traceback
import shutil
import sys
import json
import uuid
from threading import Thread
import re
import hashlib
from omsagent import run_command_and_log
from omsagent import RestartOMSAgentServiceCommand

"""
    Write now hardcode memory threshold to watch for to 20 %.
    If agent is using more than 20% of memory it is definitely very high. 
    In future we may want to set it based on customer configuration.
"""

# Constants.
MemoryThresholdToWatchFor = 20
OmsAgentPidFile = "/var/opt/microsoft/omsagent/run/omsagent.pid"
OmsAgentLogFile = "/var/opt/microsoft/omsagent/log/omsagent.log"
reg_ex = re.compile('([0-9]{4}-[0-9]{2}-[0-9]{2}.*)\[(\w+)\]:(.*)')
maxMessageSize = 100

"""
We can add to the list below with more error messages to identify non recoverable errors.
"""
ErrorStatements = ["Errono::ENOSPC error=", "Fatal error, can not clear buffer file", "No space left on the device"]

class SelfMonitorInfo:
    """
        Class to hold self mon info for omsagent.
    """
    def __init__(self):
        self._consecutive_error_count = 0        
        self._last_reset_success = True        
        self._error_count = 0        
        self._memory_used_in_percent = 0
        self._consecutive_high_memory_usage = 0        

    def reset(self):
        self._consecutive_error_count = 0        
        self._consecutive_high_memory_usage = 0
        self._memory_used_in_percent = 0

    def reset_error_info(self):
        self._consecutive_error_count = 0                

    def increment_heartbeat_missing_count(self):
        self._consecutive_error_count += 1   
    
    def crossed_error_threshold(self):
        if (self._consecutive_error_count > 3):
            return True
        else:
            return False

    def corssed_memory_threshold(self):
        if (self._consecutive_high_memory_usage > 3):
            return True
        else:
            return False            

    def increment_high_memory_count(self):
        self._consecutive_high_memory_usage += 1
    
    def reset_high_memory_count(self):
        self._consecutive_high_memory_usage = 0        

    def current_status(self):
        """
            Python 2.6 does not support enum.
        """
        if (self._consecutive_error_count == 0 and self._consecutive_high_memory_usage == 0):
            return "Green"
        elif (self._consecutive_error_count < 3 and self._consecutive_high_memory_usage < 3):
            return "Yellow"
        else:
            return "Red"

class LogFileMarker:
    """
        Class to hold omsagent log file marker information.        
    """
    def __init__(self):
        self._last_pos = 0
        self._last_crc = ""
    
    def reset_marker(self):
        self._last_pos = 0
        self._last_crc = ""

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
        self._consecutive_error_count = 0
        self._consecutive_restarts_due_to_error = 0

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
            			"value": "1.12.3"
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
                "/var/opt/microsoft/omsconfig/status/dscsetlcm",
                "/var/opt/microsoft/omsconfig/status/omsconfighost"
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
                            # Truncating the message to prevent flooding the system
                            message = status_data["message"][:maxMessageSize]

                            event = self.create_telemetry_event(operation,operation_success,message,"300000")
                            self._hutil_log("Writing telemetry event: "+event)
                            self.write_waagent_event(event)
                            self._hutil_log("Successfully processed telemetry status file: "+sf)

                        except Exception as e:
                            self._hutil_log("Error parsing telemetry status file: "+sf)
                            self._hutil_log("Exception info: "+traceback.format_exc())
                    if sf.startswith("/var/opt/microsoft/omsconfig/status"):
                        try:
                            self._hutil_log("Cleaning up: " + sf)
                            os.remove(sf)
                        except Exception as e:
                            self._hutil_log("Error removing telemetry status file: "+  sf)
                            self._hutil_log("Exception info: " + traceback.format_exc())
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

    def monitor_heartbeat(self, self_mon_info, log_file_marker):
        """
            Monitor heartbeat health. OMS output plugin will update the timestamp
            of new heartbeat file every 5 minutes. We will check if it is updated
            If not, we will look into omsagent logs and look for specific error logs
            which indicate we are in non recoverable state.             
        """ 
        take_action = False
        
        if (not self.received_heartbeat_recently()):
            """
                We haven't seen heartbeat in more than past 300 seconds
            """
            self_mon_info.increment_heartbeat_missing_count()
            take_action = False
            if (self_mon_info.crossed_error_threshold()):
                # If we do not see heartbeat for last 3 iterations, take corrective action.
                take_action = True 

            elif (self.check_for_fatal_oms_logs(log_file_marker)):

                # If we see hearbeat missing and error message, no need to wait for more than one
                # iteration. It is not a false positive. Take corrective action immediately.                       
                take_action = True 

            if (take_action):
                if (self._consecutive_restarts_due_to_error < 5):
                    self.take_corrective_action(self_mon_info)                                    
                    self._consecutive_restarts_due_to_error += 1
                else:
                    self._hutil_error("Last 5 restarts did not help. So we will not restart the agent immediately")
                    
                    # Reset historical infomration. 
                    self._consecutive_restarts_due_to_error = 0    
                    self_mon_info.reset_error_info()
        else:
            """
                If we are able to get the heartbeats, check omsagent logs
                to identify if there are any error logs.
            """                                                                    
            self_mon_info.reset_error_info()   
            self._consecutive_restarts_due_to_error = 0       

    def received_heartbeat_recently(self):
        heartbeat_file = '/var/opt/microsoft/omsagent/log/ODSIngestion.status'
        curr_time = int(time.time()) 
        return_val = True
        file_update_time = curr_time

        if (os.path.isfile(heartbeat_file)):
            file_update_time = os.path.getmtime(heartbeat_file)
            self._hutil_log("File update time={0}, current time={1}".format(file_update_time, curr_time))
        else:
            self._hutil_log("Heartbeat file is not present on the disk.")            
            file_update_time = curr_time - 1000

        if (file_update_time + 360 < curr_time):
            return_val = False
        else:        
            try:
                with open(heartbeat_file) as json_file:
                    status_data = json.load(json_file)
                    operation_success = status_data["success"]           
                    if (operation_success.lower() == "true"):
                        self._hutil_log("Found success message from ODS Ingestion.")
                        return_val = True
                    else:
                        self._hutil_log("Did not find success message in heart beat file. {0}".format(operation_success))
                        return_val = False
            except Exception as e:
                self._hutil_log("Error parsing ODS Ingestion status file: "+sf)                
            
                # Return True in case we failed to parse the file. We do not want to go into recycle loop in this scenario. 
                return_val = True
        
        return return_val
                
    def monitor_resource(self, self_mon_info):
        """
            Monitor resource utilization of omsagent.
            Check for memory and CPU periodically. If they cross the threshold for consecutive 3 iterations
            we will restart the agent. 
        """

        resource_usage = self.get_oms_agent_resource_usage()
        message = "Memory : {0}, CPU : {1}".format(resource_usage[0], resource_usage[1])
        event = self.create_telemetry_event("agenttelemetry","True",message,"300000")        
        self.write_waagent_event(event)

        self_mon_info._memory_used_in_percent = resource_usage[0]
                
        if (self_mon_info._memory_used_in_percent > 0):
            if (self_mon_info._memory_used_in_percent > MemoryThresholdToWatchFor):
                # check consecutive memory usage.
                self_mon_info.increment_high_memory_count()
                if (self_mon_info.corssed_memory_threshold()):
                    # if we have crossed the memory threshold take corrective action.
                    self.take_corrective_action(self_mon_info)
                else:
                    self_mon_info.reset_high_memory_count()
            else:
                self_mon_info.reset_high_memory_count()

    def monitor_health(self):
        """
            Role of this function is monitor the health of the oms agent.
            To begin with it will monitor heartbeats flowing through oms agent. 
            We will also read oms agent logs to determine some error conditions.
            We don't want to interfare with log watcher function.
            So we will start this on a new thread.
        """

        self_mon_info = SelfMonitorInfo()
        log_file_marker = LogFileMarker()
        
        # check every 6 minutes. we want to be bit pessimistic while looking for health, especially heartbeats which is emitted every 5 minutes.
        sleepTime =  6 * 60  

        # sleep before starting the monitoring.
        time.sleep(sleepTime)  

        while True:
            try:
                # Monitor heartbeat and logs.
                self.monitor_heartbeat(self_mon_info, log_file_marker)

                # Monitor memory usage
                self.monitor_resource(self_mon_info)

            except IOError as e:    
                self._hutil_error('I/O error in monitoring health of the omsagent. Exception={0}'.format(e))

            except Exception as e:
                self._hutil_error('Error in monitoring health of the omsagent. Exception={0}'.format(e))

            finally:                        
                time.sleep(sleepTime)                     

    def take_corrective_action(self, self_mon_info):
        """
            Take a corrective action. 
        """
        run_command_and_log(RestartOMSAgentServiceCommand)
        self._hutil_log("Successfully restarted OMS linux agent, resetting self mon information.")
            
        # Reset self mon information.
        self_mon_info.reset()   
    
    def emit_telemetry_after_corrective_action(self):
        """
            TODO : Emit telemetry after taking corrective action.
        """   
    def get_total_seconds_from_epoch_for_fluent_logs(self, datetime_string):
        # fluentd logs timestamp format : 2018-08-02 19:27:34 +0000
        # for python 2.7 or earlier there is no good way to convert it into seconds.
        # so we parse upto seconds, and parse utc specific offset seperately.
        try:
            date_time_format = '%Y-%m-%d %H:%M:%S'
            epoch = datetime(1970, 1, 1)        

            # get hours and minute delta for utc offset.
            hours_delta_utc = int(datetime_string[21:23])
            minutes_delta_utc= int(datetime_string[23:])        
        
            log_time = datetime.strptime(datetime_string[:19], date_time_format) + ((timedelta(hours=hours_delta_utc, minutes=minutes_delta_utc)) * (-1 if datetime_string[20] == "+" else 1))                
            return (log_time - epoch).total_seconds()
        except Exception as e:
            self._hutil_error('Error converting timestamp string to seconds. Exception={0}'.format(e))
        
        return 0

    def check_for_fatal_oms_logs(self, log_file_marker):                
        """
            This function will go through oms log file and check for the 
            logs indicating non recoverable state. That set is hardcoded right now
            and we can add it to it as we learn more.
            If we find there is atleast one occurance of such log line from last occurance,
            we will return True else will return False.
        """
        
        read_start_time = int(time.time())

        if os.path.isfile(OmsAgentLogFile):
            last_crc = log_file_marker._last_crc
            last_pos = log_file_marker._last_pos           

            # We do not want to propogate any exception to the caller.                
                
            try:	
                f = open(OmsAgentLogFile, "r")

                text = f.readline()	            
                
                #  Handle log rotate. Check for CRC of first line of the log file.        
                #  Some of the agents like Splunk uses this technique.
                #  If it matches with previous CRC, then file has not changed.
                #  If it is not matching then file has changed and do not seek from 	
                #  the last_pos rather continue from the begining.
                
                if (text != ''):				
                    crc = hashlib.md5(text).hexdigest()										
                    self._hutil_log("Last crc = {0}, current crc= {1} position = {2}".format(last_crc, crc, last_pos))                        
                    if (last_crc == crc):
                        
                        if (last_pos > 0):
                            f.seek(last_pos)
                    else:
                        self._hutil_log("File has changed do not seek from the offset. current crc = {0}".format(crc))
                     
                    log_file_marker._last_crc = crc	
                    total_lines_read = 1		
                
                while True:                  		
                    text = f.readline()						

                    if (text == ''):
                        log_file_marker._last_pos = f.tell()                		
                        break

                    total_lines_read += 1 		                        
                    res = reg_ex.match(text)

                    if res:
                        log_entry_time = self.get_total_seconds_from_epoch_for_fluent_logs(res.group(1))
                        if (log_entry_time + (10 * 60) < read_start_time):
                            # ignore log line if we are reading logs older than 10 minutes.
                            pass                        
                        elif (res.group(2) == "warn" or res.group(2) == "error"):                           
                            for error_statement in ErrorStatements:
                                if (res.group(3) in error_statement):
                                    self._hutil_error("Found non recoverable error log in agent log file")
                                    
                                    # File should be closed in the finally block.
                                    return True

                self._hutil_log("Did not find any non recoverable logs in omsagent log file")

            except Exception as e:
                self._hutil_error ("Caught an exception {0}".format(traceback.format_exc()))

            finally:			                    
                f.close()	                
        else:
            self._hutil_error ("Omsagent log file not found : {0}".format(OmsAgentLogFile))	
            
        return False        

    def get_oms_agent_resource_usage(self):
        """
            If we hit any exception in getting resoource usage of the omsagent return 0,0
            We need not crash/fail in this case. 
            return tuple : memory, cpu.
            Long run for north star we should use cgroups. cgroups tools are not available 
            by default on all the distros and we would need to package with the agent those and use.
            Also at this point it is not very clear if customers would want us to create cgroups on their vms.            
        """
        
        try:		
            mem_usage = 0.0
            cpu_usage = 0.0
            with open(OmsAgentPidFile, 'r') as infile:
                pid = infile.readline()	 # Get pid of omsagent process.

                # top output: 
                # $1 - PID, 
                # $2 - account, 
                # $9 - CPU, 
                # $10 - Memory, 
                # $12 - Process name
                out = subprocess.Popen('top -bn1 | grep -i omsagent | awk \'{print $1 " " $2 " " $9 " " $10  " " $12}\'', shell=True, stdout=subprocess.PIPE)
                for line in out.stdout:
                    s = line.split()      

                    if (len(s) >= 4 and s[0] == pid and s[1] == 'omsagent' and s[4] == 'omsagent'):
                        return float(s[3]) , float(s[2])                                                
                    
        except Exception as e:
            self._hutil_error('Error getting memory usage for omsagent process. Exception={0}'.format(e))
        
        # Control will reach here only in case of error condition. In that case it is ok to return 0 as it is harmless to be cautious.
        return mem_usage, cpu_usage
