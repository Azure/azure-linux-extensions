import os
import re
import sys
import subprocess
import threading
from workloadPatch.logbackupPatch import logbackup
from time import sleep
from datetime import datetime

def parameterFileParser():
    regX = re.compile(r"\*\..+=.+")
    parameterFile = open(logbackup.parameterFilePath, 'r')
    contents = parameterFile.read()
    for match in regX.finditer(contents):
        keyParameter = match.group().split('=')[0].lstrip('*\.')
        valueParameter = [name.strip('\'') for name in match.group().split('=')[1].split(',')]
        logbackup.oracleParameter[keyParameter] = valueParameter
    #print(logbackup.oracleParameter)

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

logbackup = logbackup()
parameterFileParser()
takeBackup()