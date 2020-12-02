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
import subprocess
from datetime import datetime
import re
try:
    import ConfigParser as ConfigParsers
except ImportError:
    import configparser as ConfigParsers

class LogRestore:
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
        self.parameterFileParser()

    # Example of Parameter File Content:
    # *.db_name='CDB1'
    def parameterFileParser(self):
        regX = re.compile(r"\*\..+=.+")
        parameterFile = open(self.parameterFilePath, 'r')
        contents = parameterFile.read()
        for match in regX.finditer(contents):
            keyParameter = match.group().split('=')[0].lstrip('*\.')
            valueParameter = [name.strip('\'') for name in match.group().split('=')[1].split(',')]
            self.oracleParameter[keyParameter] = valueParameter

    # To replace the existing control files in the DB with new control files
    def switchControlFiles(self, backupPath):
        parsedControlFile = self.oracleParameter['control_files']
        for location in parsedControlFile:
            os.system('rm -f '+location)
            os.system('cp -f '+ backupPath + '/control.ctl ' + location)
            os.system('chmod a+wrx '+location)

    # To replace the existing archive log files in the DB with new archive log file
    def switchArchiveLogFiles(self, backupPath):
        recoveryFileDest = self.oracleParameter['db_recovery_file_dest']
        dbName = self.oracleParameter['db_name']
        for location in recoveryFileDest:
            os.system('rm -R -f '+ location + '/' + dbName[0] +'/archivelog')
            os.system('cp -R -f ' + backupPath + '/archivelog ' + location + '/' + dbName[0] + '/archivelog')
            os.system('chmod -R a+wrx '+ location +'/' + dbName[0] + '/archivelog')

    # To trigger the restore of control files and archive log files
    def triggerRestore(self):
        backupPath = self.baseLocation + self.backupSource
        self.switchControlFiles(backupPath)
        self.switchArchiveLogFiles(backupPath)

    def confParser(self):
        configfile = '/etc/azure/workload.conf' 
        if os.path.exists(configfile):
            config = ConfigParsers.ConfigParser()
            config.read(configfile)
            if config.has_section("logbackup"):
                #self.logger.log("LogRestore: config section present for workload ")
                if config.has_option("workload", 'workload_name'):                        
                    self.name = config.get("workload", 'workload_name')
                #self.logger.log("LogRestore: config workload name "+ self.name)
                else:
                    return None
                if config.has_option("workload", 'command'):                        
                    self.command = config.get("workload", 'command')
                #self.logger.log("LogRestore: config workload command " + self.command)
                if config.has_option("workload", 'credString'):
                    self.cred_string = config.get("workload", 'credString')
                #self.logger.log("LogRestore: config workload cred_string " + self.cred_string)
                if config.has_option("logbackup", 'parameterFilePath'):
                    self.parameterFilePath = config.get("logbackup", 'parameterFilePath')
                #self.logger.log("LogRestore: config logbackup parameter file path: " + self.parameterFilePath)
                else:
                    return None
                if config.has_option("logbackup", 'baseLocation'):
                    self.baseLocation = config.get("logbackup", 'baseLocation')
                #self.logger.log("LogRestore: config logbackup base location: " + self.baseLocation)
                else:
                    return None
                if config.has_option("logbackup", 'crontabLocation'):
                    self.crontabLocation = config.get("logbackup", 'crontabLocation')
                #self.logger.log("LogRestore: config logbackup crontab location: " + self.crontabLocation)
        else:
            return
            #self.logger.log("No matching workload config found")
def main():
    oracleLogRestore = LogRestore()

    os.system('ls -lrt ' + oracleLogRestore.baseLocation)
    oracleLogRestore.backupSource = input("Enter the timestamp: ")
    oracleLogRestore.triggerRestore()

if __name__ == "__main__":
    main()