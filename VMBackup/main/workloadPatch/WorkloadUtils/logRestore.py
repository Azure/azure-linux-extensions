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

class Incremental:
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

    def parameterFileParser(self):
        regX = re.compile(r"\*\..+=.+")
        parameterFile = open(self.parameterFilePath, 'r')
        contents = parameterFile.read()
        for match in regX.finditer(contents):
            keyParameter = match.group().split('=')[0].lstrip('*\.')
            valueParameter = [name.strip('\'') for name in match.group().split('=')[1].split(',')]
            self.oracleParameter[keyParameter] = valueParameter
        #print(self.oracleParameter)

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
        self.switchControlFiles(backupPath)
        self.switchArchiveLogFiles(backupPath)
        print("Incremental: Restore Complete")
    #----End Incremental Restore----#

    def confParser(self):
        configfile = '/etc/azure/workload.conf' 
        if os.path.exists(configfile):
            config = ConfigParsers.ConfigParser()
            config.read(configfile)
            if config.has_section("logbackup"):
                #print("logbackup: config section present for workload ")
                if config.has_option("workload", 'workload_name'):                        
                    self.name = config.get("workload", 'workload_name')
                #    print("    logbackup: config workload name "+ self.name)
                else:
                    return None
                if config.has_option("workload", 'command'):                        
                    self.command = config.get("workload", 'command')
                #    print("    logbackup: config workload command "+ self.command)
                if config.has_option("workload", 'credString'):
                    self.cred_string = config.get("workload", 'credString')
                #    print("    logbackup: config workload cred_string "+ self.cred_string)
                if config.has_option("logbackup", 'parameterFilePath'):
                    self.parameterFilePath = config.get("logbackup", 'parameterFilePath')
                #    print("    logbackup: config logbackup parameter file path: ", self.parameterFilePath)
                else:
                    return None
                if config.has_option("logbackup", 'baseLocation'):
                    self.baseLocation = config.get("logbackup", 'baseLocation')
                #    print("    logbackup: config logbackup base location: ", self.baseLocation)
                else:
                    return None
                if config.has_option("logbackup", 'crontabLocation'):
                    self.crontabLocation = config.get("logbackup", 'crontabLocation')
                #    print("    logbackup: config logbackup crontab location: ", self.crontabLocation)
        else:
            print("No matching workload config found")

oracleIncremental = Incremental()

#----Prompt----#
#Action = input("Enter l for list, b for incremental backup and r for restore: ")
Action = 'r'
#----End Prompt----#

if Action == 'r':
    #----Restore----#
    os.system('ls -lrt '+ oracleIncremental.baseLocation)
    oracleIncremental.backupSource = input("Enter the filename: ")
    oracleIncremental.restore()
    #----End Restore----#
elif Action == 'l':
    os.system('ls -lrt '+ oracleIncremental.baseLocation)
else:
    print("Invalid input")

print("Incremental Workload: DONE")