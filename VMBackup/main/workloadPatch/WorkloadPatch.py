#!/usr/bin/python
#
# Copyright 2015 Microsoft Corporation
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
#
# Requires Python 2.4+

import sys
#import Utils.HandlerUtil
import threading
import os
from time import sleep
try:
    import ConfigParser as ConfigParsers
except ImportError:
    import configparser as ConfigParsers
import subprocess

class WorkloadPatch:
    def __init__(self, logger):
        self.logger = logger
        self.name = "oracle"
        self.command = "/usr/bin/"
        self.dbnames = []
        self.login_path = "AzureBackup"
        self.ipc_folder = None
        self.error_details = []
        self.enforce_slave_only = False
        self.role = "master"
        self.child = []
        self.timeout = "60"
        self.confParser()

    def pre(self):
        try:
            self.logger.log("WorkloadPatch: Entering workload pre call")
            print("WorkloadPatch: Entering workload pre call")
            if self.role == "master" and int(self.enforce_slave_only) == 0:
                if len(self.dbnames) == 0 :
                    #pre at server level create fork process for child and append
                    self.preMaster()
                else:
                    self.preMasterDB()
                    # create fork process for child                  
            elif self.role == "slave":
                if len(self.dbnames) == 0 :
                    #pre at server level create fork process for child and append
                    self.preSlave()
                else:
                    self.preSlaveDB()
                # create fork process for child
            else:
                self.error_details.append("invalid role name in config")
        except Exception as e:
            self.logger.log("WorkloadPatch: exception in pre" + str(e))
            self.error_details.append("exception in processing of prescript")

    def post(self):
        try:
            self.logger.log("WorkloadPatch: Entering workload post call")
            print("WorkloadPatch: Entering workload post call")
            if self.role == "master":
                if len(self.dbnames) == 0:
                    #post at server level to turn off readonly mode
                    self.postMaster()
                else:
                    self.postMasterDB()
            elif self.role == "slave":
                if len(self.dbnames) == 0 :
                    #post at server level to turn on slave
                    self.postSlave()
                else:
                    self.postSlaveDB()
            else:
                self.error_details.append("invalid role name in config") 
        except Exception as e:
            self.logger.log("WorkloadPatch: exception in post" + str(e))
            self.error_details.append("exception in processing of postscript")

    def preMaster(self):
        self.logger.log("WorkloadPatch: Entering pre mode for master")
        print("WorkloadPatch: Entering pre mode for master")
        
        if os.path.exists("/var/lib/mysql-files/azbackupserver.txt"):
            os.remove("/var/lib/mysql-files/azbackupserver.txt")
        else:
            self.logger.log("WorkloadPatch: File for IPC does not exist at pre")
            
        if 'mysql' in self.name.lower():
            self.logger.log("WorkloadPatch: Create connection string for premaster")
            arg = self.command+self.name+" --login-path="+self.login_path+" < main/workloadPatch/scripts/preMysqlMaster.sql"
            binary_thread = threading.Thread(target=self.thread_for_sql, args=[arg])
            binary_thread.start()
        
            while os.path.exists("/var/lib/mysql-files/azbackupserver.txt") == False:
                self.logger.log("WorkloadPatch: Waiting for sql to complete")
                sleep(2)
            self.logger.log("WorkloadPatch: pre at server level completed")
        
        #----SHRID CODE START----#
        if 'oracle' in self.name.lower():
            global preOracleStatus
            preOracleStatus = self.databaseStatus()
            if "OPEN" in str(preOracleStatus):
                self.logger.log("Shrid: Pre- Database is open")
                print("Shrid: Pre- Database is open")
            else:
                self.logger.log("Shrid: Pre- Database not open. Backup may proceed without pre and post")
                print("Shrid: Pre- Database not open. Backup may proceed without pre and post")
                return

            print("Shrid: Pre- Inside oracle pre")
            self.logger.log("Shrid: Pre- Inside oracle pre")
            preOracle = "sqlplus -s / as sysdba @" + os.path.join(os.getcwd(), "main/workloadPatch/scripts/preOracleMaster.sql ")
            args = ["su", "-", self.login_path, "-c", preOracle]
            process = subprocess.Popen(args)
            while process.poll() == None:
                sleep(1)
            self.timeoutDaemon()
            self.logger.log("Shrid: Pre- Exiting pre mode for master")
            print("Shrid: Pre- Exiting pre mode for master")
        #----SHRID CODE END----#

    #----SHRID CODE START----#
    def timeoutDaemon(self):
        global preDaemonThread
        if 'oracle' in self.name.lower():
            self.logger.log("Shrid: Inside oracle condition in timeout daemon")
            print("Shrid: Inside oracle condition in timeout daemon")
            preDaemonOracle = "sqlplus -s / as sysdba @" + os.path.join(os.getcwd(), "main/workloadPatch/scripts/preOracleDaemon.sql ") + self.timeout
            argsDaemon = ["su", "-", self.login_path, "-c", preDaemonOracle]
            preDaemonThread = threading.Thread(target=self.threadForTimeoutDaemon, args=[argsDaemon])
            preDaemonThread.start()
        self.logger.log("Shrid: timeoutDaemon started for: " + self.timeout + " seconds")
        print("Shrid: timeoutDaemon started for: ", self.timeout, " seconds")
    #----SHRID CODE END----#

    #----SHRID CODE START----#
    def threadForTimeoutDaemon(self, args): 
            global daemonProcess
            daemonProcess = subprocess.Popen(args)
            self.logger.log("Shrid: daemonProcess started")
            print("Shrid: daemonProcess started")
            while daemonProcess.poll() == None:
                sleep(1)
            self.logger.log("Shrid: daemonProcess completed")
            print("Shrid: daemonProcess completed")
    #----SHRID CODE END----#

    #---- SHRID CODE START----#
    def databaseStatus(self):

        if 'oracle' in self.name.lower():
            statusArgs =  "su - " + self.login_path + " -c " + "'sqlplus -s / as sysdba<<-EOF\nSELECT STATUS FROM V\$INSTANCE;\nEOF'"
            oracleStatus = subprocess.check_output(statusArgs, shell=True)
            self.logger.log("Shrid: databaseStatus- " + str(oracleStatus))
            print("Shrid: databaseStatus- ", str(oracleStatus))
            return oracleStatus

        return False
    #----SHRID CODE END----#

    def thread_for_sql(self,args):
        self.logger.log("command to execute: "+str(args))
        self.child.append(subprocess.Popen(args,stdout=subprocess.PIPE,stdin=subprocess.PIPE,shell=True,stderr=subprocess.PIPE))
        while len(self.child) == 0:
            self.logger.log("child not created yet", True)
            sleep(1)
        self.logger.log("sql subprocess Created",True)
        self.logger.log("sql subprocess Created "+str(self.child[0].pid)) 
        sleep(1)


    def preMasterDB(self):
        for dbname in self.dbnames:
            if 'mysql' in self.name.lower():#TODO DB level
                args = self.command+self.name+" --login-path="+self.login_path+" < main/workloadPatch/scripts/preMysqlMaster.sql"
                binary_thread = threading.Thread(target=self.thread_for_sql, args=[args])
                binary_thread.start()
        
    def preSlave(self):
        pass

    def preSlaveDB(self):
        pass
    
    def postMaster(self):
        self.logger.log("WorkloadPatch: Entering post mode for master")
        print("WorkloadPatch: Entering post mode for master")
        if os.path.exists("/var/lib/mysql-files/azbackupserver.txt"):
            os.remove("/var/lib/mysql-files/azbackupserver.txt")
        #else:
        #    self.logger.log("WorkloadPatch: File for IPC does not exist at post")
        
        if 'mysql' in self.name.lower():
            if len(self.child) == 0:
                self.logger.log("WorkloadPatch: Not app consistent backup")
                self.error_details.append("not app consistent")
            elif self.child[0].poll() is None:
                self.logger.log("WorkloadPatch: pre connection still running. Sending kill signal")
                self.child[0].kill()
            self.logger.log("WorkloadPatch: Create connection string for post master")
            args = self.command+self.name+" --login-path="+self.login_path+" < main/workloadPatch/scripts/postMysqlMaster.sql"
            post_child = subprocess.Popen(args,stdout=subprocess.PIPE,stdin=subprocess.PIPE,shell=True,stderr=subprocess.PIPE)

        #----SHRID CODE START----#
        if 'oracle' in self.name.lower():
            postOracleStatus = self.databaseStatus()
            if postOracleStatus != preOracleStatus:
                self.logger.log("Shrid: Error. Pre and post database status different.")
                print("Shrid: Error. Pre and post database status different.")
            if "OPEN" in str(postOracleStatus):
                self.logger.log("Shrid: Post- Database is open")
                print("Shrid: Post- Database is open")
            else:
                self.logger.log("Shrid: Post- Database not open. Backup may proceed without pre and post")
                print("Shrid: Post- Database not open. Backup may proceed without pre and post")
                return

            self.logger.log("Shird: Post- Inside oracle post")
            print("Shird: Post- Inside oracle post")
            if preDaemonThread.isAlive():
                self.logger.log("Shird: Post- Timeout daemon still in sleep")
                print("Shird: Post- Timeout daemon still in sleep")
                self.logger.log("Shrid: Post- Initiating Post Script")
                print("Shrid: Post- Initiating Post Script")
                daemonProcess.terminate()
            else:
                self.logger.log("Shrid: Post error- Timeout daemon executed before post")
                print("Shrid: Post error- Timeout daemon executed before post")
                return
            postOracle="sqlplus -s / as sysdba @" + os.path.join(os.getcwd(), "main/workloadPatch/scripts/postOracleMaster.sql ")
            args = ["su", "-", self.login_path, "-c", postOracle]
            process = subprocess.Popen(args)
            while process.poll()==None:
                sleep(1)
            self.logger.log("Shrid: Post- Completed")
            print("Shrid: Post- Completed")
        #----SHRID CODE END----#

    def postMasterDB(self):
        pass
    
    def postSlave(self):
        pass

    def postSlaveDB(self):
        pass

    def confParser(self):
        self.logger.log("WorkloadPatch: Entering workload config parsing")
        configfile = '/etc/azure/workload.conf'
        try:
            if os.path.exists(configfile):
                config = ConfigParsers.ConfigParser()
                config.read(configfile)
                if config.has_section("workload"):
                    self.logger.log("WorkloadPatch: config section present for workloads ")
                    if config.has_option("workload", 'workload_name'):                        
                        self.name = config.get("workload", 'workload_name')
                        self.logger.log("WorkloadPatch: config workload command "+ self.workload_name)
                    else:
                        return None
                    if config.has_option("workload", 'command'):                        
                        self.command = config.get("workload", 'command')
                        self.logger.log("WorkloadPatch: config workload command "+ self.command)
                    if config.has_option("workload", 'loginPath'):
                        self.login_path = config.get("workload", 'loginPath')
                        self.logger.log("WorkloadPatch: config workload login_path "+ self.login_path)
                    if config.has_option("workload", 'role'):
                        self.role = config.get("workload", 'role')
                        self.logger.log("WorkloadPatch: config workload role "+ self.role)
                    if config.has_option("workload", 'enforceSlaveOnly'):
                        self.enforce_slave_only = config.get("workload", 'enforceSlaveOnly')
                        self.logger.log("WorkloadPatch: config workload enforce_slave_only "+ self.enforce_slave_only)
                    if config.has_option("workload", 'ipc_folder'):
                        self.ipc_folder = config.get("workload", 'ipc_folder')
                        self.logger.log("WorkloadPatch: config ipc folder "+ self.ipc_folder)
                    if config.has_option("workload", 'timeout'):
                        self.timeout = config.get("workload", 'timeout')
                        self.logger.log("WorkloadPatch: config timeout of pre script "+ self.timeout)
                    if config.has_option("workload", 'dbnames'):
                        dbnames_list = config.get("workload", 'dbnames') #mydb1;mydb2;mydb3
                        self.dbnames = dbnames_list.split(';')
                else:
                    self.error_details.append("no matching workload config found")
            else:
                self.logger.log("workload config missing",True)
                error_details.append("workload config missing")
        except Exception as e:
            self.error_details.append("exception in workloadconfig parsing")
    
    def populateErrors(self):
        error_list = []#TODO error list from error details
        return error_list  

#----SHRID CODE START----#
class Incremental:
    def __init__(self):
        self.name = "oracle"
        self.login_path = "AzureBackup"
        self.baseLocation = "/hdd/AutoIncrement/"
        self.parameterFilePath = "/u01/app/oracle/product/19.3.0/dbhome_1/dbs/initCDB1.ora"
        self.oracleParameter = {}
        self.backupSource = ""
        self.crontabLocation = "/var/spool/cron/root"
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
                print("Incremental: Crontab Entry- ", str(crontabCheck))
                return
            else:
                os.system("echo \"*/15 * * * * python " + os.path.join(os.getcwd(), "logbackup.py\"") + " >> /var/spool/cron/root")
                print("Incremental: New Crontab Entry")
                return
    
    def confParser(self):
        print("WorkloadPatch: Entering workload config parsing")
        configfile = '/etc/azure/workload.conf' 
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

#----SHRID CODE END----#