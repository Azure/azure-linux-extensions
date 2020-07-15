#!/usr/bin/env python
#
# VM Backup extension
#
# Copyright 2014 Microsoft Corporation
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

import sys
import threading
import os
from time import sleep
try:
    import ConfigParser as ConfigParsers
except ImportError:
    import configparser as ConfigParsers
import subprocess

class LogBackupPatch:
    def __init__(self):
        self.name = ""
        self.cred_string = ""
        self.baseLocation = ""
        self.parameterFilePath = ""
        self.oracleParameter = {}
        self.backupSource = ""
        self.crontabLocation = ""
        self.command = ""
        self.confParser()
        self.crontabEntry()

    def crontabEntry(self):
        if os.path.exists(self.crontabLocation):
            crontabFile = open(self.crontabLocation, 'r')
            crontabCheck = crontabFile.read()
        else:
            crontabCheck = "NO CRONTAB"

        if 'oracle' in self.name.lower():
            if 'OracleLogBackup' in str(crontabCheck):
                return
            else:
                os.system("echo \"*/15 * * * * python " + os.path.join(os.getcwd(), "main/workloadPatch/WorkloadUtils/OracleLogBackup.py\"") + " >> /var/spool/cron/root")
                return
    
    def confParser(self):
        configfile = '/etc/azure/workload.conf' 
        if os.path.exists(configfile):
            config = ConfigParsers.ConfigParser()
            config.read(configfile)
            if config.has_section("logbackup"):
                if config.has_option("workload", 'workload_name'):                        
                    self.name = config.get("workload", 'workload_name')
                else:
                    return None
                if config.has_option("workload", 'command'):                        
                    self.command = config.get("workload", 'command')
                if config.has_option("workload", 'credString'):
                    self.cred_string = config.get("workload", 'credString')
                if config.has_option("logbackup", 'parameterFilePath'):
                    self.parameterFilePath = config.get("logbackup", 'parameterFilePath')
                else:
                    return None
                if config.has_option("logbackup", 'baseLocation'):
                    self.baseLocation = config.get("logbackup", 'baseLocation')
                else:
                    return None
                if config.has_option("logbackup", 'crontabLocation'):
                    self.crontabLocation = config.get("logbackup", 'crontabLocation')
        else:
            return