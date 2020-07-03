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

import os
import re
import sys
import subprocess
import threading
from workloadPatch.LogbackupPatch import LogBackupPatch
from time import sleep
from datetime import datetime

# Example of Parameter File Content:
# *.db_name='CDB1'
def parameterFileParser():
    regX = re.compile(r"\*\..+=.+")
    parameterFile = open(logbackup.parameterFilePath, 'r')
    contents = parameterFile.read()
    for match in regX.finditer(contents):
        keyParameter = match.group().split('=')[0].lstrip('*\.')
        valueParameter = [name.strip('\'') for name in match.group().split('=')[1].split(',')]
        logbackup.oracleParameter[keyParameter] = valueParameter

def setLocation():
    nowTimestamp = datetime.now()
    nowTimestamp = nowTimestamp.strftime("%Y%m%d%H%M%S")
    fullPath = logbackup.baseLocation + nowTimestamp
    os.system('mkdir -m777 '+ fullPath)
    return fullPath

def takeBackup():
    print("logbackup: Taking a backup")

    backupPath = setLocation()

    if 'oracle' in logbackup.name.lower():
        backupOracle = logbackup.command + " -s / as sysdba @" +  "/var/lib/waagent/Microsoft.Azure.RecoveryServices.VMSnapshotLinux-1.0.9164.0/main/workloadPatch/scripts/logbackup.sql " + backupPath
        argsForControlFile = ["su", "-", logbackup.cred_string, "-c", backupOracle]
        snapshotControlFile = subprocess.Popen(argsForControlFile)
        while snapshotControlFile.poll()==None:
            sleep(1)        
        recoveryFileDest = logbackup.oracleParameter['db_recovery_file_dest']
        dbName = logbackup.oracleParameter['db_name']
        print('    logbackup: Archive log backup started at ', datetime.now().strftime("%Y%m%d%H%M%S"))
        os.system('cp -R -f ' + recoveryFileDest[0] + '/' + dbName[0] + '/archivelog ' + backupPath)
        print('    logbackup: Archive log backup complete at ', datetime.now().strftime("%Y%m%d%H%M%S"))

    print("logbackup: Backup Complete")

def main():
    global logbackup
    logbackup = LogBackupPatch()
    parameterFileParser()
    takeBackup()

if __name__ == "__main__":
    main()