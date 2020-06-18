import os
import re
import sys
import subprocess
import threading
from .WorkloadPatch import Incremental
from time import sleep
from datetime import datetime

logbackup = Incremental()

def parameterFileParser():
    regX = re.compile(r"\*\..+=.+")
    parameterFile = open(logbackup.parameterFilePath, 'r')
    contents = parameterFile.read()
    for match in regX.finditer(contents):
        keyParameter = match.group().split('=')[0].lstrip('*\.')
        valueParameter = [name.strip('\'') for name in match.group().split('=')[1].split(',')]
        logbackup.oracleParameter[keyParameter] = valueParameter
    print(logbackup.oracleParameter)

def setLocation():
    nowTimestamp = datetime.now()
    nowTimestamp = nowTimestamp.strftime("%Y%m%d%H%M%S")
    fullPath = logbackup.baseLocation + nowTimestamp
    os.system('mkdir -m777 '+ fullPath)
    return fullPath

def incremental():
    print("Logbackup: Taking a backup")

    backupPath = setLocation()

    if 'oracle' in logbackup.name.lower():
        backupOracle = "sqlplus -s / as sysdba @" + os.path.join(os.getcwd(), "main/workloadPatch/scripts/logbackup.sql " + backupPath
        argsForControlFile = ["su", "-", logbackup.login_path, "-c", backupOracle]
        snapshotControlFile = subprocess.Popen(argsForControlFile)
        while snapshotControlFile.poll()==None:
            sleep(1)        
        recoveryFileDest = logbackup.oracleParameter['db_recovery_file_dest']
        dbName = logbackup.oracleParameter['db_name']
        print('Archive log started: ', datetime.now().strftime("%Y%m%d%H%M%S"))
        os.system('cp -R -f ' + recoveryFileDest[0] + '/' + dbName[0] + '/archivelog ' + backupPath)
        print('Archive log copied: ', datetime.now().strftime("%Y%m%d%H%M%S"))

    print("Logbackup: Backup Complete")

parameterFileParser()
incremental()