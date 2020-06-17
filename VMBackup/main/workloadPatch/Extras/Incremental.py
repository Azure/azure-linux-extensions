import sys
import Utils.HandlerUtil
import threading
import os
from time import sleep
try:
    import ConfigParser as ConfigParsers
except ImportError:
    import configparser as ConfigParsers
import subprocess
from datetime import datetime
import re

#----Config----#
name = "oracle"
login_path = "oracle"
backupSource = ""
baseLocation = "/hdd/AutoIncrement/"
parameterFilePath = "/u01/app/oracle/product/19.3.0/dbhome_1/dbs/initCDB1.ora"
oracleParameter = {}
parameterFileParser()
#Action = 'b'
#----End----#

def confParser():
    print("WorkloadPatch: Entering workload config parsing")
    configfile = 'increment.conf'
    if os.path.exists(configfile):
        config = ConfigParsers.ConfigParser()
        config.read(configfile)
        if config.has_section("incremental"):
            print("Incremental: config section present for incremental ")
            if config.has_option("incremental", 'workload_name'):                        
                name = config.get("incremental", 'workload_name')
                print("Incremental: config incremental command ", name)
            else:
                return None
            if config.has_option("incremental", 'loginPath'):
                login_path = config.get("incremental", 'loginPath')
                print("Incremental: config incremental login_path ", login_path)
            if config.has_option("incremental", 'parameterFilePath'):
                parameterFilePath = config.get("incremental", 'parameterFilePath')
                print("Incremental: config incremental parameterFilePath ", parameterFilePath)
            if config.has_option("incremental", 'baseLocation'):
                baseLocation = config.get("incremental", 'baseLocation')
                print("Incremental: config incremental baseLocation ", baseLocation)
            if config.has_option("incremental", 'backupSource'):
                backupSource = config.get("incremental", 'backupSource')
                print("Incremental: config incremental backupSource ", backupSource)
    else:
        print("No matching workload config found")

def parameterFileParser():
    regX = re.compile(r"\*\..+=.+")
    parameterFile = open(parameterFilePath, 'r')
    contents = parameterFile.read()
    for match in regX.finditer(contents):
        keyParameter = match.group().split('=')[0].lstrip('*\.')
        valueParameter = [name.strip('\'') for name in match.group().split('=')[1].split(',')]
        oracleParameter[keyParameter] = valueParameter
    #print(oracleParameter)

def setLocation():
    nowTimestamp = datetime.now()
    nowTimestamp = nowTimestamp.strftime("%Y%m%d%H%M%S")
    fullPath = baseLocation + nowTimestamp
    os.system('mkdir -m777 '+ fullPath)
    return fullPath

#----Start Incremental Backup----#
def incremental():
    print("Incremental: Taking a backup")

    backupPath = setLocation()

    if 'oracle' in name.lower():
        backupOracle = "sqlplus -s / as sysdba @/hdd/python/IncrementalBackup/backup.sql " + backupPath
        argsForControlFile = ["su", "-", login_path, "-c", backupOracle]
        snapshotControlFile = subprocess.Popen(argsForControlFile)
        while snapshotControlFile.poll()==None:
            sleep(1)        
        recoveryFileDest = oracleParameter['db_recovery_file_dest']
        dbName = oracleParameter['db_name']
        print('Archive log started: ', datetime.now().strftime("%Y%m%d%H%M%S"))
        os.system('cp -R -f ' + recoveryFileDest[0] + '/' + dbName[0] + '/archivelog ' + backupPath)
        print('Archive log copied: ', datetime.now().strftime("%Y%m%d%H%M%S"))

    print("Incremental: Backup Complete")
#----End Incremental Backup----#

#----Start Incremental Restore----#
def switchControlFiles(backupPath):
    parsedControlFile = oracleParameter['control_files']
    for location in parsedControlFile:
        os.system('rm -f '+location)
        os.system('cp -f '+ backupPath + '/control.ctl ' + location)
        os.system('chmod a+wrx '+location)
    print("Switched Control Files")

def switchArchiveLogFiles(backupPath):
    recoveryFileDest = oracleParameter['db_recovery_file_dest']
    dbName = oracleParameter['db_name']
    for location in recoveryFileDest:
        os.system('rm -R -f '+ location + '/' + dbName[0] +'/archivelog')
        os.system('cp -R -f ' + backupPath + '/archivelog ' + location + '/' + dbName[0] + '/archivelog')
        os.system('chmod -R a+wrx '+ location +'/' + dbName[0] + '/archivelog')
    print("Switched Archive Log Files")

def restore():
    print("Incremental: Restoring")
    backupPath = baseLocation + backupSource
    scriptLocation = "/hdd/python/IncrementalBackup/recover.sh"
    args = [scriptLocation, backupSource, login_path]
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
    os.system('ls -lrt '+ baseLocation)
    backupSource = input("Enter the filename: ")
    restore()
    #----End Restore----#
elif Action=='l':
    os.system('ls -lrt '+ baseLocation)
else:
    print("Invalid input")

print("Incremental Workload: DONE")