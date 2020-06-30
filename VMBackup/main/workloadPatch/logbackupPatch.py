import sys
import threading
import os
from time import sleep
try:
    import ConfigParser as ConfigParsers
except ImportError:
    import configparser as ConfigParsers
import subprocess

class logbackup:
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
            if 'logbackup' in str(crontabCheck):
                print("logbackup: Existing Crontab Entry: ", str(crontabCheck))
                return
            else:
                os.system("echo \"*/15 * * * * python " + os.path.join(os.getcwd(), "main/logbackup.py\"") + " >> /var/spool/cron/root")
                print("logbackup: New Crontab Entry Made")
                return
    
    def confParser(self):
        configfile = '/etc/azure/workload.conf' 
        if os.path.exists(configfile):
            config = ConfigParsers.ConfigParser()
            config.read(configfile)
            if config.has_section("logbackup"):
                print("logbackup: config section present for workload ")
                if config.has_option("workload", 'workload_name'):                        
                    self.name = config.get("workload", 'workload_name')
                    print("    logbackup: config workload name "+ self.name)
                else:
                    return None
                if config.has_option("workload", 'command'):                        
                    self.command = config.get("workload", 'command')
                    print("    logbackup: config workload command "+ self.command)
                if config.has_option("workload", 'credString'):
                    self.cred_string = config.get("workload", 'credString')
                    print("    logbackup: config workload cred_string "+ self.cred_string)
                if config.has_option("logbackup", 'parameterFilePath'):
                    self.parameterFilePath = config.get("logbackup", 'parameterFilePath')
                    print("    logbackup: config logbackup parameter file path: ", self.parameterFilePath)
                else:
                    return None
                if config.has_option("logbackup", 'baseLocation'):
                    self.baseLocation = config.get("logbackup", 'baseLocation')
                    print("    logbackup: config logbackup base location: ", self.baseLocation)
                else:
                    return None
                if config.has_option("logbackup", 'crontabLocation'):
                    self.crontabLocation = config.get("logbackup", 'crontabLocation')
                    print("    logbackup: config logbackup crontab location: ", self.crontabLocation)
        else:
            print("No matching workload config found")