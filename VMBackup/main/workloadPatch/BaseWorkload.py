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

class BaseWorkload(object):
    def __init__(self, workload_name, logger):
        self.name = workload_name
        self.command = "/usr/bin/" + workload_name
        self.dbnames = []
        self.username = None
        self.password = None
        self.workload_cnf_folder = None
        self.error_details = []
        self.confParser(workload_name)
        self.role = "master"
        self.child = []
        self.logger = logger

    def __pre__(self):
        if self.role == "master":
            if len(self.dbnames) == 0 :
                #pre at server level create fork process for child and append
                self.preMaster()
            else:
                self.preMasterDB()
                for dbname in self.dbnames:
                    # create fork process for child
                    #self.child.append()                    
        else if self.role == "slave":
            if len(self.dbnames) == 0 :
                #pre at server level create fork process for child and append
                self.preSlave()
            else:
                self.preSlaveDB()
                for dbname in self.dbnames:
                    # create fork process for child
                    #self.child.append()
        else:
            self.error_details.append("invalid role name in config")

        if len(self.child) > 0 :
            poll()

    def __post__(self):
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

    def preMaster(self):
        if 'mysql' in self.name.lower():
            args = [self.command, '-u',self.username,'-p'+self.password,'-h', localhost, '<' , preMysqlMaster.sql]
            self.startproc(args)

    def startproc(self,args):
        binary_thread = threading.Thread(target=thread_for_binary, args=[self, args])
        binary_thread.start()


    def preMasterDB(self):
        pass

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
                    if config.has_option(workload_name, username):
                        self.username = config.get(workload_name, username)
                    if config.has_option(workload_name, password):
                        self.password = config.get(workload_name, password)
                    if config.has_option(workload_name, workload_cnf_folder):
                        self.workload_cnf_folder = config.get(workload_name, workload_cnf_folder)
                    if config.has_option(workload_name, dbnames):
                        dbnames_list = config.get(workload_name, dbnames) #mydb1;mydb2;mydb3
                        self.dbnames = dbnames_list.split(';')
                else:
                    error_details.append("no matching workload config found")
            
            if self.name
        

    