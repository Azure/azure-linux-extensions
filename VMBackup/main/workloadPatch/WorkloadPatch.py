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

class WorkloadPatch:
    def __init__(self, workload_name, logger):
        self.logger = logger
        self.name = workload_name
        self.command = "/usr/bin/"
        self.dbnames = []
        self.login_path = ""
        self.ipc_folder = None
        self.error_details = []
        self.enforce_slave_only = True
        self.role = "master"
        self.child = []

    def pre(self):
        try:
            self.logger.log("WorkloadPatch: Entering workload pre call")
            self.confParser(self.name)
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
                self.error_details.append("invalid role name in config") 
        except Exception as e:
            self.logger.log("WorkloadPatch: exception in post" + str(e))
            self.error_details.append("exception in processing of postscript")

    def preMaster(self):
        self.logger.log("WorkloadPatch: Entering pre mode for master")
        if os.path.exists("/var/lib/mysql-files/azbackupserver.txt"):
            os.remove("/var/lib/mysql-files/azbackupserver.txt")
        else:
            self.logger.log("WorkloadPatch: File for IPC does not exist at pre")
            
        if 'mysql' in self.name.lower():
            self.logger.log("WorkloadPatch: Create connection string for premaster")
            args = [self.command+self.name, ' --login-path =',self.login_path, '<' , "main/workloadPatch/scripts/preMySqlMaster.sql"]
            binary_thread = threading.Thread(target=self.thread_for_sql, args=[args])
            binary_thread.start()
            while os.path.exists("/var/lib/mysql-files/azbackupserver.txt") == False:
                self.logger.log("WorkloadPatch: Waiting for sql to complete")
                sleep(2)
            self.logger.log("WorkloadPatch: pre at server level completed")
            
    def thread_for_sql(self,args):
        sleep(1)
        self.child.append(subprocess.Popen(args,stdout=subprocess.PIPE))
        self.logger.log("sql subprocess Created",True)


    def preMasterDB(self):
        for dbname in dbnames:
            if 'mysql' in self.name.lower():#TODO DB level
                args = [self.command+self.name, '-login-path = ',self.login_path, '<' , "main/workloadPatch/scripts/preMySqlMaster.sql"]
                binary_thread = threading.Thread(target=self.thread_for_sql, args=[args])
                binary_thread.start()
        

    def preSlave(self):
        pass

    def preSlaveDB(self):
        pass
    
    def postMaster(self):
        self.logger.log("WorkloadPatch: Entering post mode for master")
        if os.path.exists("/var/lib/mysql-files/azbackupserver.txt"):
            os.remove("/var/lib/mysql-files/azbackupserver.txt")
        else:
            self.logger.log("WorkloadPatch: File for IPC does not exist at post")
        if len(self.child) == 0:
            self.logger.log("WorkloadPatch: Not app consistent backup")
            self.error_details.append("not app consistent")
        elif self.child[0].poll() is None:
            self.logger.log("WorkloadPatch: pre connection still running")
            ##TODO send sig kill
        if 'mysql' in self.name.lower():
            self.logger.log("WorkloadPatch: Create connection string for post master")
            args = [self.command+self.name, ' --login-path =',self.login_path, '<' , "main/workloadPatch/scripts/postMySqlMaster.sql"]
            post_child = subprocess.Popen(args,stdout=subprocess.PIPE)

    def postMasterDB(self):
        pass
    
    def postSlave(self):
        pass

    def postSlaveDB(self):
        pass

    def confParser(self, workload_name):
        self.logger.log("WorkloadPatch: Entering workload config parsing")
        configfile = '/etc/azure/workload.conf'
        try:
            if os.path.exists(configfile):
                config = ConfigParsers.ConfigParser()
                config.read(configfile)
                if config.has_section(workload_name):
                    self.logger.log("WorkloadPatch: config section present for workload "+ workload_name)
                    if config.has_option(workload_name, 'command'):                        
                        self.command = config.get(workload_name, 'command')
                        self.logger.log("WorkloadPatch: config workload command "+ self.command)
                    if config.has_option(workload_name, 'loginPath'):
                        self.login_path = config.get(workload_name, 'loginPath')
                        self.logger.log("WorkloadPatch: config workload login_path "+ self.login_path)
                    if config.has_option(workload_name, 'role'):
                        self.role = config.get(workload_name, 'role')
                        self.logger.log("WorkloadPatch: config workload role "+ self.role)
                    if config.has_option(workload_name, 'enforceSlaveOnly'):
                        self.enforce_slave_only = config.get(workload_name, 'enforceSlaveOnly')
                        self.logger.log("WorkloadPatch: config workload enforce_slave_only "+ self.enforce_slave_only)
                    if config.has_option(workload_name, 'ipc_folder'):
                        self.ipc_folder = config.get(workload_name, 'ipc_folder')
                        self.logger.log("WorkloadPatch: config workload command "+ self.workload_folder)
                    if config.has_option(workload_name, 'dbnames'):
                        dbnames_list = config.get(workload_name, 'dbnames') #mydb1;mydb2;mydb3
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

    