import sys
import threading
import os
from time import sleep
import subprocess
from datetime import datetime
import re
#import Utils.HandlerUtil
try:
    import ConfigParser as ConfigParsers
except ImportError:
    import configparser as ConfigParsers

class Incremental:
    def __init__(self):
        self.name = "oracle"
        self.login_path = "oracle"
        self.baseLocation = "/hdd/AutoIncrement/"
        self.parameterFilePath = "/u01/app/oracle/product/19.3.0/dbhome_1/dbs/initCDB1.ora"
        self.oracleParameter = {}
        self.backupSource = ""
        #Action = 'b' #To always perform backup by default

    def parameterFileParser(self):
        regX = re.compile(r"\*\..+=.+")
        parameterFile = open(self.parameterFilePath, 'r')
        contents = parameterFile.read()
        for match in regX.finditer(contents):
            keyParameter = match.group().split('=')[0].lstrip('*\.')
            valueParameter = [name.strip('\'') for name in match.group().split('=')[1].split(',')]
            self.oracleParameter[keyParameter] = valueParameter
        #print(self.oracleParameter)

    def setLocation(self):
        nowTimestamp = datetime.now()
        nowTimestamp = nowTimestamp.strftime("%Y%m%d%H%M%S")
        fullPath = self.baseLocation + nowTimestamp
        os.system('mkdir -m777 '+ fullPath)
        return fullPath

    #----Start Incremental Backup----#
    def incremental(self):
        print("Incremental: Taking a backup")

        backupPath = self.setLocation()

        if 'oracle' in self.name.lower():
            backupOracle = "sqlplus -s / as sysdba @/hdd/python/IncrementalBackup/backup.sql " + backupPath
            argsForControlFile = ["su", "-", self.login_path, "-c", backupOracle]
            snapshotControlFile = subprocess.Popen(argsForControlFile)
            while snapshotControlFile.poll()==None:
                sleep(1)        
            recoveryFileDest = self.oracleParameter['db_recovery_file_dest']
            dbName = self.oracleParameter['db_name']
            print('Archive log started: ', datetime.now().strftime("%Y%m%d%H%M%S"))
            os.system('cp -R -f ' + recoveryFileDest[0] + '/' + dbName[0] + '/archivelog ' + backupPath)
            print('Archive log copied: ', datetime.now().strftime("%Y%m%d%H%M%S"))

        print("Incremental: Backup Complete")
    #----End Incremental Backup----#

    #----Start Incremental Restore----#
    def switchControlFiles(self, backupPath):
        parsedControlFile = self.oracleParameter['control_files']
        for location in parsedControlFile:
            os.system('rm -f '+location)
            os.system('cp -f '+ backupPath + '/control.ctl ' + location)
            os.system('chmod a+wrx '+location)
        print("Switched Control Files")

    def switchArchiveLogFiles(self, backupPath):
        recoveryFileDest = self.oracleParameter['db_recovery_file_dest']
        dbName = self.oracleParameter['db_name']
        for location in recoveryFileDest:
            os.system('rm -R -f '+ location + '/' + dbName[0] +'/archivelog')
            os.system('cp -R -f ' + backupPath + '/archivelog ' + location + '/' + dbName[0] + '/archivelog')
            os.system('chmod -R a+wrx '+ location +'/' + dbName[0] + '/archivelog')
        print("Switched Archive Log Files")

    def restore(self):
        print("Incremental: Restoring")
        backupPath = self.baseLocation + self.backupSource
        scriptLocation = "/hdd/python/IncrementalBackup/recover.sh"
        args = [scriptLocation, self.backupSource, self.login_path]
        restoreProcess = subprocess.Popen(args)
        while restoreProcess.poll()==None:
            sleep(2)
        self.switchControlFiles(backupPath)
        self.switchArchiveLogFiles(backupPath)
        print("Incremental: Restore Complete")
    #----End Incremental Restore----#

    def confParser(self):
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

oracleIncremental = Incremental()
#----Parse the parameter file----#
oracleIncremental.parameterFileParser()
#----End----#

#----Prompt----#
Action = input("Enter l for list, b for incremental backup and r for restore: ")
#----End Prompt----#

if Action=='b':
    oracleIncremental.incremental()
elif Action=='r':
    #----Restore----#
    os.system('ls -lrt '+ oracleIncremental.baseLocation)
    oracleIncremental.backupSource = input("Enter the filename: ")
    oracleIncremental.restore()
    #----End Restore----#
elif Action=='l':
    os.system('ls -lrt '+ oracleIncremental.baseLocation)
else:
    print("Invalid input")

print("Incremental Workload: DONE")