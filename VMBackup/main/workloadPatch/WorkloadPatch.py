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
import os
import ConfigParsers

class WorkloadPatch(object):
    def __init__(self, workload_name, logger):
        self.name = workload_name
        self.command = "/usr/bin/"
        self.dbnames = []
        self.login_path = ""
        self.workload_cnf_folder = None
        self.error_details = []
        self.confParser(workload_name)
        self.enforce_slave_only = True
        self.role = "master"
        self.child = []
        self.logger = logger

    def pre(self):
        if self.role == "master" and self.enforce_slave_only == False:
            if len(self.dbnames) == 0 :
                #pre at server level create fork process for child and append
                self.preMaster()
            else:
                self.preMasterDB()
                # create fork process for child
                    #self.child.append()                    
        else if self.role == "slave":
            if len(self.dbnames) == 0 :
                #pre at server level create fork process for child and append
                self.preSlave()
            else:
                self.preSlaveDB()
                # create fork process for child
                    #self.child.append()
        else:
            self.error_details.append("invalid role name in config")

    def post(self):
        if self.role == "master":
            if len(self.dbnames) == 0 :
                #post at server level to turn off readonly mode
            else:
                for dbname in self.dbnames:
                    # post at DB level to turn off readonly
        else if self.role == "slave":
            if len(self.dbnames) == 0 :
                #post at server level to turn on slave
            else:
                for dbname in self.dbnames:
                    #post at db level to turn on slave
        else:
            self.error_details.append("invalid role name in config") 
            
        if os.path.exists("/var/lib/mysql-files/azbackupserver.txt"):
            os.remove("/var/lib/mysql-files/azbackupserver.txt")
        else:
            self.logger.log("The file does not exist")

    def preMaster(self):
        if os.path.exists("/var/lib/mysql-files/azbackupserver.txt"):
            os.remove("/var/lib/mysql-files/azbackupserver.txt")
        else:
            self.logger.log("The file does not exist")
            
        if 'mysql' in self.name.lower():
            args = [self.command+self.name, ' --login-path =',self.login_path, '<' , "scripts/preMySqlMaster.sql"]
            binary_thread = threading.Thread(target=thread_for_sql, args=[self, args])
            binary_thread.start()
            while os.path.exists("/var/lib/mysql-files/azbackupserver.txt") == False:
                sleep(2)
            self.logger.log("pre at server level completed")
            
    def thread_for_sql(self,args):
        time.sleep(1)
        self.child.append(subprocess.Popen(args,stdout=subprocess.PIPE))
        self.logger.log("sql subprocess Created",True)


    def preMasterDB(self):
        for dbname in dbnames:
            if 'mysql' in self.name.lower():#TODO DB level
                args = [self.command+self.name, '-login-path = ',self.login_path, '<' , preMySqlMaster.sql]
                binary_thread = threading.Thread(target=thread_for_sql, args=[self, args])
                binary_thread.start()
        

    def preSlave(self):
        pass

    def preSlaveDB(self):
        pass

    def confParser(self, workload_name):
        configfile = '/etc/azure/workload.conf'
        try:
            if os.path.exists(configfile):
                config = ConfigParsers.ConfigParser()
                config.read(configfile)
                if config.has_section(workload_name):
                    if config.has_option(workload_name, command):
                        self.command = config.get(workload_name, command)
                    if config.has_option(workload_name, loginPath):
                        self.login_path = config.get(workload_name, loginPath)
                    if config.has_option(workload_name, role):
                        self.role = config.get(workload_name, role)
                    if config.has_option(workload_name, enforceSlaveOnly):
                        self.enforce_slave_only = config.get(workload_name, enforceSlaveOnly)
                    if config.has_option(workload_name, workload_cnf_folder):
                        self.workload_cnf_folder = config.get(workload_name, workload_cnf_folder)
                    if config.has_option(workload_name, dbnames):
                        dbnames_list = config.get(workload_name, dbnames) #mydb1;mydb2;mydb3
                        self.dbnames = dbnames_list.split(';')
                else:
                    error_details.append("no matching workload config found")
            
    def populateErrors(self)
        error_list = []#TODO error list from error details
        return error_list  

    