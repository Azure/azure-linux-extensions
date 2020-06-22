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

class ErrorDetail:
    def __init__(self, errorCode, errorMsg):
        self.errorCode = errorCode
        self.errorMsg = errorMsg
    
class WorkloadPatch:
    def __init__(self, logger):
        self.logger = logger
        self.name = ""
        self.command = "/usr/bin/"
        self.dbnames = []
        self.cred_string = ""
        self.ipc_folder = None
        self.error_details = []
        self.enforce_slave_only = True
        self.role = "master"
        self.child = []
        self.timeout = 90
        self.outfile = ""
        self.confParser()

    def pre(self):
        try:
            self.logger.log("WorkloadPatch: Entering workload pre call")
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
            self.logger.log("WorkloadPatch: Entering workload pre call")
            if self.role == "master":
                if len(self.dbnames) == 0 :
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
        self.logger.log("WorkloadPatch: Entering post mode for master")
        self.outfile = os.path.join(self.ipc_folder, "azbackupserver.txt")
        if os.path.exists(self.outfile):
            os.remove(self.outfile)
        else:
            self.logger.log("WorkloadPatch: File for IPC does not exist at pre")
            
        if 'mysql' in self.name.lower():
            self.logger.log("WorkloadPatch: Create connection string for premaster")
            prescript = os.path.join(os.getcwd(), "main/workloadPatch/scripts/preMysqlMaster.sql")
            arg = self.command+self.name+" --login-path="+self.cred_string+" -e\"set @timeout="+self.timeout+";set @outfile=\\\"\\\\\\\""+self.outfile+"\\\\\\\"\\\";source "+prescript+";\""
            binary_thread = threading.Thread(target=self.thread_for_sql, args=[arg])
            binary_thread.start()
        
            while os.path.exists(self.outfile) == False:
                self.logger.log("WorkloadPatch: Waiting for sql to complete")
                sleep(2)
            self.logger.log("WorkloadPatch: pre at server level completed")
        else:
            pass
            
            
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
        for dbname in dbnames:
            if 'mysql' in self.name.lower():#TODO DB level
                args = self.command+self.name+" --login-path="+self.cred_string+" -e\"set @timeout="+self.timeout+";set @outfile="+self.outfile+";source main/workloadPatch/scripts/preMysqlMaster.sql;\""
                binary_thread = threading.Thread(target=self.thread_for_sql, args=[args])
                binary_thread.start()
        

    def preSlave(self):
        self.logger.log("WorkloadPatch: Entering post mode for master")
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
            args = self.command+self.name+" --login-path="+self.cred_string+" < main/workloadPatch/scripts/postMysqlSlave.sql"
            post_child = subprocess.Popen(args,stdout=subprocess.PIPE,stdin=subprocess.PIPE,shell=True,stderr=subprocess.PIPE)

    def preSlaveDB(self):
        pass
    
    def postMaster(self):
        self.logger.log("WorkloadPatch: Entering post mode for master")
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
            args = self.command+self.name+" --login-path="+self.cred_string+" < main/workloadPatch/scripts/postMysqlMaster.sql"
            post_child = subprocess.Popen(args,stdout=subprocess.PIPE,stdin=subprocess.PIPE,shell=True,stderr=subprocess.PIPE)

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
            return errdetail.errorCode, errordetail.errorMsg
        else:
            return None
    
    def getRole(self):
        return "master"

    
