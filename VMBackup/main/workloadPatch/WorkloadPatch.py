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
import Utils.HandlerUtil
import threading
import os
from time import sleep
try:
    import ConfigParser as ConfigParsers
except ImportError:
    import configparser as ConfigParsers
import subprocess
from common import CommonVariables
from workloadPatch.logbackupPatch import logbackup

class ErrorDetail:
    def __init__(self, errorCode, errorMsg):
        self.errorCode = errorCode
        self.errorMsg = errorMsg
    
class WorkloadPatch:
    def __init__(self, logger):
        self.logger = logger
        self.name = "oracle"
        self.command = "sqlplus"
        self.dbnames = []
        self.cred_string = ""
        self.ipc_folder = None
        self.error_details = []
        self.enforce_slave_only = False
        self.role = "master"
        self.child = []
        self.timeout = 90
        self.outfile = ""
        self.logbackup = ""
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
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadPatchInvalidRole, "invalid role name in config"))
        except Exception as e:
            self.logger.log("WorkloadPatch: exception in pre" + str(e))
            self.error_details.append(ErrorDetail(CommonVariables.FailedPreWorkloadPatch, "Exception in pre"))

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
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadPatchInvalidRole, "invalid role name in config"))
        except Exception as e:
            self.logger.log("WorkloadPatch: exception in post" + str(e))
            self.error_details.append(ErrorDetail(CommonVariables.FailedPreWorkloadPatch, "exception in processing of postscript"))

    def preMaster(self):
        self.logger.log("WorkloadPatch: Entering pre mode for master")
        if self.ipc_folder != None:
            self.outfile = os.path.join(self.ipc_folder, "azbackupserver.txt")
            if os.path.exists(self.outfile):
                os.remove(self.outfile)
            else:
                self.logger.log("WorkloadPatch: File for IPC does not exist at pre")
        
        if 'mysql' in self.name.lower():
            self.logger.log("WorkloadPatch: Create connection string for premaster")
            prescript = os.path.join(os.getcwd(), "main/workloadPatch/scripts/preMysqlMaster.sql")
            arg = "sudo "+self.command+self.name+" "+self.cred_string+" -e\"set @timeout="+self.timeout+";set @outfile=\\\"\\\\\\\""+self.outfile+"\\\\\\\"\\\";source "+prescript+";\""
            binary_thread = threading.Thread(target=self.thread_for_sql, args=[arg])
            binary_thread.start()
        
            while os.path.exists(self.outfile) == False:
                self.logger.log("WorkloadPatch: Waiting for sql to complete")
                sleep(2)
            self.logger.log("WorkloadPatch: pre at server level completed")
        #----SHRID CODE START----#
        elif 'oracle' in self.name.lower():
            global preOracleStatus
            preOracleStatus = self.databaseStatus()
            if "OPEN" in str(preOracleStatus):
                self.logger.log("WorkloadPatch: Pre- Database is open")
                print("WorkloadPatch: Pre- Database is open")
            else:
                self.logger.log("WorkloadPatch: Pre- Database not open. Backup may proceed without pre and post")
                print("WorkloadPatch: Pre- Database not open. Backup may proceed without pre and post")
                return None

            print("WorkloadPatch: Pre- Inside oracle pre")
            self.logger.log("WorkloadPatch: Pre- Inside oracle pre")
            preOracle = self.command + " -s / as sysdba @" + os.path.join(os.getcwd(), "main/workloadPatch/scripts/preOracleMaster.sql ")
            args = ["su", "-", self.cred_string, "-c", preOracle]
            process = subprocess.Popen(args)
            while process.poll() == None:
                sleep(1)
            self.timeoutDaemon()
            self.logger.log("WorkloadPatch: Pre- Exiting pre mode for master")
            print("WorkloadPatch: Pre- Exiting pre mode for master")
        #----SHRID CODE END----#

    #----SHRID CODE START----#
    def timeoutDaemon(self):
        global preDaemonThread
        if 'oracle' in self.name.lower():
            self.logger.log("WorkloadPatch: Inside oracle condition in timeout daemon")
            print("WorkloadPatch: Inside oracle condition in timeout daemon")
            preDaemonOracle = self.command + " -s / as sysdba @" + os.path.join(os.getcwd(), "main/workloadPatch/scripts/preOracleDaemon.sql ") + self.timeout
            argsDaemon = ["su", "-", self.cred_string, "-c", preDaemonOracle]
            preDaemonThread = threading.Thread(target=self.threadForTimeoutDaemon, args=[argsDaemon])
            preDaemonThread.start()
        self.logger.log("WorkloadPatch: timeoutDaemon started for: " + self.timeout + " seconds")
        print("WorkloadPatch: timeoutDaemon started for: ", self.timeout, " seconds")
    #----SHRID CODE END----#

    #----SHRID CODE START----#
    def threadForTimeoutDaemon(self, args): 
            global daemonProcess
            daemonProcess = subprocess.Popen(args)
            self.logger.log("WorkloadPatch: daemonProcess started")
            print("WorkloadPatch: daemonProcess started")
            while daemonProcess.poll() == None:
                sleep(1)
            self.logger.log("WorkloadPatch: daemonProcess completed")
            print("WorkloadPatch: daemonProcess completed")
    #----SHRID CODE END----#

    #---- SHRID CODE START----#
    def databaseStatus(self):

        if 'oracle' in self.name.lower():
            statusArgs =  "su - " + self.cred_string + " -c " + "'" + self.command +" -s / as sysdba<<-EOF\nSELECT STATUS FROM V\$INSTANCE;\nEOF'"
            oracleStatus = subprocess.check_output(statusArgs, shell=True)
            self.logger.log("WorkloadPatch: databaseStatus- " + str(oracleStatus))
            print("WorkloadPatch: databaseStatus- ", str(oracleStatus))
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
                args = "sudo "+self.command+self.name+" --login-path="+self.cred_string+" -e\"set @timeout="+self.timeout+";set @outfile="+self.outfile+";source main/workloadPatch/scripts/preMysqlMaster.sql;\""
                binary_thread = threading.Thread(target=self.thread_for_sql, args=[args])
                binary_thread.start()
        
    def preSlave(self):
        self.logger.log("WorkloadPatch: Entering post mode for master")
        if self.ipc_folder != None:
            if os.path.exists(self.outfile):
                os.remove(self.outfile)
            else:
                self.logger.log("WorkloadPatch: File for IPC does not exist at post")
            if len(self.child) == 0:
                self.logger.log("WorkloadPatch: Not app consistent backup")
                self.error_details.append("not app consistent")
            elif self.child[0].poll() is None:
                self.logger.log("WorkloadPatch: pre connection still running. Sending kill signal")
                self.child[0].kill()
        
        if 'mysql' in self.name.lower():
            self.logger.log("WorkloadPatch: Create connection string for post master")
            args = "sudo "+self.command+self.name+" --login-path="+self.cred_string+" < main/workloadPatch/scripts/postMysqlSlave.sql"
            post_child = subprocess.Popen(args,stdout=subprocess.PIPE,stdin=subprocess.PIPE,shell=True,stderr=subprocess.PIPE)

    def preSlaveDB(self):
        pass
    
    def postMaster(self):
        self.logger.log("WorkloadPatch: Entering post mode for master")
        if self.ipc_folder != None:
            if os.path.exists(self.outfile):
                os.remove(self.outfile)
            else:
                self.logger.log("WorkloadPatch: File for IPC does not exist at post")
            if len(self.child) == 0:
                self.logger.log("WorkloadPatch: Not app consistent backup")
                self.error_details.append("not app consistent")
            elif self.child[0].poll() is None:
                self.logger.log("WorkloadPatch: pre connection still running. Sending kill signal")
                self.child[0].kill()
        
        if 'mysql' in self.name.lower():
            if len(self.child) == 0:
                self.logger.log("WorkloadPatch: Not app consistent backup")
                self.error_details.append("not app consistent")
            elif self.child[0].poll() is None:
                self.logger.log("WorkloadPatch: pre connection still running. Sending kill signal")
                self.child[0].kill()
            self.logger.log("WorkloadPatch: Create connection string for post master")
            args = self.command+self.name+" --login-path="+self.cred_string+" < main/workloadPatch/scripts/postMysqlMaster.sql"
            post_child = subprocess.Popen(args,stdout=subprocess.PIPE,stdin=subprocess.PIPE,shell=True,stderr=subprocess.PIPE)
        elif 'oracle' in self.name.lower():
            postOracleStatus = self.databaseStatus()
            if postOracleStatus != preOracleStatus:
                self.logger.log("WorkloadPatch: Error. Pre and post database status different.")
                print("WorkloadPatch: Error. Pre and post database status different.")
            if "OPEN" in str(postOracleStatus):
                self.logger.log("WorkloadPatch: Post- Database is open")
                print("WorkloadPatch: Post- Database is open")
            else:
                self.logger.log("WorkloadPatch: Post- Database not open. Backup may proceed without pre and post")
                print("WorkloadPatch: Post- Database not open. Backup may proceed without pre and post")
                return

            self.logger.log("Shird: Post- Inside oracle post")
            print("Shird: Post- Inside oracle post")
            if preDaemonThread.isAlive():
                self.logger.log("Shird: Post- Timeout daemon still in sleep")
                print("Shird: Post- Timeout daemon still in sleep")
                self.logger.log("WorkloadPatch: Post- Initiating Post Script")
                print("WorkloadPatch: Post- Initiating Post Script")
                daemonProcess.terminate()
            else:
                self.logger.log("WorkloadPatch: Post error- Timeout daemon executed before post")
                print("WorkloadPatch: Post error- Timeout daemon executed before post")
                return
            postOracle = self.command + " -s / as sysdba @" + os.path.join(os.getcwd(), "main/workloadPatch/scripts/postOracleMaster.sql ")
            args = ["su", "-", self.cred_string, "-c", postOracle]
            process = subprocess.Popen(args)
            while process.poll()==None:
                sleep(1)
            self.logger.log("WorkloadPatch: Post- Completed")
            print("WorkloadPatch: Post- Completed")
            self.callLogbackup()
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
                        self.logger.log("WorkloadPatch: config workload command "+ self.name)
                    else:
                        return None
                    if config.has_option("workload", 'command'):                        
                        self.command = config.get("workload", 'command')
                        self.logger.log("WorkloadPatch: config workload command "+ self.command)
                    if config.has_option("workload", 'credString'):
                        self.cred_string = config.get("workload", 'credString')
                        self.logger.log("WorkloadPatch: config workload cred_string "+ self.cred_string)
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
                    if config.has_option("workload", 'logbackup'):
                        self.logbackup = config.get("workload", 'logbackup')
                        self.logger.log("WorkloadPatch: config logbackup " + self.logbackup)
                else:
                    self.error_details.append(ErrorDetail(CommonVariables.FailedPreWorkloadPatch, "no matching workload config found"))
            else:
                self.logger.log("workload config missing",True)
                self.error_details.append(ErrorDetail(CommonVariables.FailedPreWorkloadPatch, "workload config missing"))
        except Exception as e:
            self.logger.log
            self.error_details.append(ErrorDetail(CommonVariables.FailedPreWorkloadPatch, "exception in workloadconfig parsing"))
    
    def populateErrors(self):
        if len(self.error_details) > 0:
            errdetail = self.error_details[0]
            return errdetail
        else:
            return None
    
    def getRole(self):
        return "master"
    
    def callLogbackup(self):
        if 'enable' in self.logbackup.lower():
            self.logger.log("WorkloadPatch: Initializing logbackup")
            print("WorkloadPatch: Initializing logbackup")
            logbackupObject = logbackup()
        else:
            return