import sys
import os
import subprocess
import threading
import re
import string
from time import sleep
from datetime import datetime

def parserLine(unparsedLine):
    parsedLine = [name.strip() for name in unparsedLine.split('=')[1].split(',')]
    return parsedLine

def parameterFileParser(toFind):
    filepath="/u01/app/oracle/product/19.3.0/dbhome_1/dbs/initCDB1.ora"
    unparsedControlFile = ""
    unparsedArchiveLog = ""

    with open(filepath, 'r') as parameterFile:
        line = parameterFile.readline()
        while line:
            if "*.control_files=" in line:
                unparsedControlFile = line
            if "*.db_recovery_file_dest=" in line:
                unparsedArchiveLog = line
            line = parameterFile.readline()
    parameterFile.close()

    if toFind == "archivelog":
        parsedArchiveLog = parserLine(unparsedArchiveLog)
        return parsedArchiveLog
    elif toFind == "controlfile":
        parsedControlFile = parserLine(unparsedControlFile)
        return parsedControlFile
    else:
        return None

def setLocation():
    nowTimestamp = datetime.now()
    nowTimestamp = nowTimestamp.strftime("%Y%m%d%H%M%S")
    fullPath = BaseLocation + nowTimestamp
    os.system('mkdir -m777 '+fullPath)
    return fullPath

#----Start Incremental Backup----#
def incremental():
    print("Incremental: Taking a backup")

    backupPath = setLocation()

    backupOracle = "sqlplus -s / as sysdba @/hdd/python/IncrementalBackup/backup.sql " + backupPath
    argsForControlFile = ["su", "-", login_path, "-c", backupOracle]
    snapshotControlFile = subprocess.Popen(argsForControlFile)
    while snapshotControlFile.poll()==None:
        sleep(2)

    argsForArchiveLog = ["cp", "-R", "-f", archiveLogLocation, backupPath]
    snapshotArchiveLog = subprocess.Popen(argsForArchiveLog)
    while snapshotArchiveLog.poll()==None:
        sleep(2)

    print("Incremental: Backup Complete")
#----End Incremental Backup----#

#----Start Incremental Restore----#
def switchControlFiles():
    parsedControlFile = parameterFileParser("controlfile")
    #controlFileNames = []
    for location in parsedControlFile:
        os.system('rm -f '+location)
        os.system('cp -f '+ backupPath + '/control.ctl ' +location)
        #controlFileNames.append(re.findall('[\w\.-]+.ctl', location))

def switchArchiveLogFiles():
    parsedArchiveLog = parameterFileParser("archivelog")
    print(parsedArchiveLog)

def restore():
    print("Incremental: Restoring")
    backupPath = BaseLocation + BackupSource
    scriptLocation = "/hdd/python/IncrementalBackup/recover.sh"
    args = [scriptLocation, BackupSource, login_path]
    restoreProcess = subprocess.Popen(args)
    while restoreProcess.poll()==None:
        sleep(2)
    print("Incremental: Restore Complete")
#----End Incremental Restore----#

#----Config----#
BackupSource = ""
BaseLocation = "/hdd/AutoIncrement/"
archiveLogLocation = "/hdd/CoreFiles/flash_recovery_area/CDB1/archivelog"
login_path = "oracle"
database = "oracle"
#Action = 'b'
#----End----#

switchArchiveLogFiles()

#----Prompt----#
#Action = input("Enter l for list, b for incremental backup and r for restore: ")
#----End Prompt----#


#if Action=='b':
#    incremental()
#elif Action=='r':
#    #----Restore----#
#    os.system('ls -lrt '+BaseLocation)
#    BackupSource=input("Enter the filename: ")
#    restore()
#    #----End Restore----#
#elif Action=='l':
#    os.system('ls -lrt '+BaseLocation)
#else:
#    print("Invalid input")

print("Incremental Workload: DONE")
