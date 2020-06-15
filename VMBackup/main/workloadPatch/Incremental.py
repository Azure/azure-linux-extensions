import sys
import os
import subprocess
import threading
import re
import string
from time import sleep
from datetime import datetime


#----Config----#
name = "oracle"
login_path = "oracle"
BackupSource = ""
BaseLocation = "/hdd/AutoIncrement/"
#archiveLogLocation = "/hdd/CoreFiles/flash_recovery_area/CDB1/archivelog"
filepath="/u01/app/oracle/product/19.3.0/dbhome_1/dbs/initCDB1.ora"
#Action = 'b'
#----End----#

def parserLine(unparsedLine):
    parsedLine = [name.strip() for name in unparsedLine.split('=')[1].split(',')]
    return parsedLine

def parameterFileParser(toFind):
    unparsedControlFile = ""
    unparsedArchiveLog = ""

    with open(filepath, 'r') as parameterFile:
        line = parameterFile.readline()
        while line:
            if "*.control_files=" in line:
                unparsedControlFile = line
            if "*.db_recovery_file_dest=" in line:
                unparsedArchiveLog = line
            if "*.db_name=" in line:
                unparsedDBName = line
            line = parameterFile.readline()
    parameterFile.close()

    if toFind == "archivelog":
        parsedArchiveLog = parserLine(unparsedArchiveLog)
        return parsedArchiveLog
    elif toFind == "controlfile":
        parsedControlFile = parserLine(unparsedControlFile)
        return parsedControlFile
    elif toFind == "db_name":
        parsedDBName = parserLine(unparsedDBName)
        return parsedDBName
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
    
    parsedArchiveLog = parameterFileParser("archivelog")
    parsedDBName = parameterFileParser("db_name")
    archiveLogLocation = parsedArchiveLog + '/' + parsedDBName + '/archivelog'

    argsForArchiveLog = ["cp", "-R", "-f", archiveLogLocation, backupPath]
    snapshotArchiveLog = subprocess.Popen(argsForArchiveLog)
    while snapshotArchiveLog.poll()==None:
        sleep(2)

    print("Incremental: Backup Complete")
#----End Incremental Backup----#

#----Start Incremental Restore----#
def switchControlFiles(backupPath):
    parsedControlFile = parameterFileParser("controlfile")
    #controlFileNames = []
    for location in parsedControlFile:
        os.system('rm -f '+location)
        os.system('cp -f '+ backupPath + '/control.ctl ' + location)
        os.system('chmod a+wrx '+location)
    print("Switched Control Files")
        #controlFileNames.append(re.findall('[\w\.-]+.ctl', location))

def switchArchiveLogFiles(backupPath):
    parsedArchiveLog = parameterFileParser("archivelog")
    for location in parsedArchiveLog:
        os.system('rm -R -f '+ location + '/CDB1/archivelog')
        os.system('cp -R -f ' + backupPath + '/archivelog ' + location + '/CDB1/archivelog')
        os.system('chmod -R a+wrx '+location+'/CDB1/archivelog')
    print("Switched Archive Log Files")

def restore():
    print("Incremental: Restoring")
    backupPath = BaseLocation + BackupSource
    scriptLocation = "/hdd/python/IncrementalBackup/recover.sh"
    args = [scriptLocation, BackupSource, login_path]
    restoreProcess = subprocess.Popen(args)
    while restoreProcess.poll()==None:
        sleep(2)
    switchControlFiles(backupPath)
    switchArchiveLogFiles(backupPath)
    print("Incremental: Restore Complete")
#----End Incremental Restore----#



#----Prompt----#
Action = input("Enter l for list, b for incremental backup and r for restore: ")
#----End Prompt----#

if Action=='b':
    incremental()
elif Action=='r':
    #----Restore----#
    os.system('ls -lrt '+BaseLocation)
    BackupSource=input("Enter the filename: ")
    restore()
    #----End Restore----#
elif Action=='l':
    os.system('ls -lrt '+BaseLocation)
else:
    print("Invalid input")

print("Incremental Workload: DONE")
