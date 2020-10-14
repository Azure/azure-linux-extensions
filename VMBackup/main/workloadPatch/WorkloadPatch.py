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
from workloadPatch.LogBackupPatch import LogBackupPatch

class ErrorDetail:
    def __init__(self, errorCode, errorMsg):
        self.errorCode = errorCode
        self.errorMsg = errorMsg
    
class WorkloadPatch:
    def __init__(self, logger):
        self.logger = logger
        self.name = None
        self.supported_workload = ["oracle", "mysql", "mariadb", "postgres"]
        self.command = ""
        self.dbnames = []
        self.cred_string = ""
        self.ipc_folder = None
        self.error_details = []
        self.enforce_slave_only = 0
        self.role = "master"
        self.child = []
        self.timeout = "90"
        self.linux_user = "root"
        self.sudo_user = "sudo"
        self.outfile = ""
        self.logbackup = ""
        self.custom_scripts_enabled = 0
        self.scriptpath= "DefaultScripts"
        self.temp_script_folder= "/etc/azure"
        self.confParser()

    def pre(self):
        try:
            self.logger.log("WorkloadPatch: Entering workload pre call")
            self.createTempScriptsFolder()
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
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadInvalidRole, "invalid role name in config"))
        except Exception as e:
            self.logger.log("WorkloadPatch: exception in pre" + str(e))
            self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadPreError, "Exception in pre"))

    def post(self):
        try:
            self.logger.log("WorkloadPatch: Entering workload post call")
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
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadInvalidRole, "invalid role name in config"))
            #Remove the temporary scripts folder created
            self.removeTempScriptsFolder()
        except Exception as e:
            self.logger.log("WorkloadPatch: exception in post" + str(e))
            #Remove the temporary scripts folder created
            self.removeTempScriptsFolder()
            self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadPostError, "exception in processing of postscript"))

    def preMaster(self):
        self.logger.log("WorkloadPatch: Entering pre mode for master")
        if self.ipc_folder != None:
            self.outfile = os.path.join(self.ipc_folder, "azbackupIPC.txt")
            if os.path.exists(self.outfile):
                os.remove(self.outfile)
            else:
                self.logger.log("WorkloadPatch: File for IPC does not exist at pre")

        global preWorkloadStatus
        preWorkloadStatus = self.workloadStatus()
        if "OPEN" in str(preWorkloadStatus):
            self.logger.log("WorkloadPatch: Pre- WorkloadStatus is open")
        elif "NOT APPLY" in str(preWorkloadStatus):
            self.logger.log("WorkloadPatch: Pre- WorkloadStatus not apply")
        else:
            self.logger.log("WorkloadPatch: Pre- WorkloadStatus not open.")
            self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadDatabaseNotOpen, "Pre- Workload not open"))
            return None
        
        if 'mysql' in self.name.lower() or 'mariadb' in self.name.lower():
            self.logger.log("WorkloadPatch: Create connection string for premaster mysql")
            if self.outfile == "":
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadIPCDirectoryMissing, "IPC directory missing"))
                return None
            prescript = os.path.join(self.temp_script_folder, self.scriptpath + "/preMysqlMaster.sql")
            arg = self.sudo_user+" "+self.command+self.name+" "+self.cred_string+" -e\"set @timeout="+self.timeout+";set @outfile=\\\"\\\\\\\""+self.outfile+"\\\\\\\"\\\";source "+prescript+";\""
            binary_thread = threading.Thread(target=self.thread_for_sql, args=[arg])
            binary_thread.start()
            self.waitForPreScriptCompletion()
        elif 'oracle' in self.name.lower():
            self.logger.log("WorkloadPatch: Pre- Inside oracle pre")
            preOracle = self.command + "sqlplus" + " -S -R 2 /nolog @" + os.path.join(self.temp_script_folder, self.scriptpath + "/preOracleMaster.sql ")
            args = ["su", "-", self.linux_user, "-c", preOracle]
            self.logger.log("WorkloadPatch: argument passed for pre script:"+str(args))

            process = subprocess.Popen(args, stdout=subprocess.PIPE)
            wait_counter = 5
            while process.poll() == None and wait_counter>0:
                wait_counter -= 1
                sleep(2)
            self.timeoutDaemon()
            self.logger.log("WorkloadPatch: Pre- Exiting pre mode for master")
        elif 'postgres' in self.name.lower():
            self.logger.log("WorkloadPatch: Pre- Inside postgres pre")
            prePostgres = self.command + "psql " + self.cred_string + " -f " + os.path.join(os.getcwd(), "main/workloadPatch/"+self.scriptpath+"/prePostgresMaster.sql")
            args =  "su - "+self.linux_user+" -c "+"\'"+prePostgres+"\'"
            self.logger.log("WorkloadPatch: argument passed for pre script:"+str(self.linux_user)+"  "+str(self.command))

            process = subprocess.Popen(args,stdout=subprocess.PIPE, shell=True)
            wait_counter = 5
            while process.poll() == None and wait_counter>0:
                wait_counter -= 1
                sleep(2)
            while True:
                line= process.stdout.readline()
                line=str(line)
                if(line != ''):
                    self.logger.log("WorkloadPatch: pre completed with output "+line.rstrip(), True)
                else:
                    break
            self.timeoutDaemon()
            self.logger.log("WorkloadPatch: Pre- Exiting pre mode for master postgres")
        #Add new workload support here
        else:
            self.logger.log("WorkloadPatch: Unsupported workload name")
            self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadInvalidWorkloadName, "Workload Not supported"))
            
    def postMaster(self):
        self.logger.log("WorkloadPatch: Entering post mode for master")
        if self.ipc_folder != None: #IPCm based workloads
            if os.path.exists(self.outfile):
                os.remove(self.outfile)
            else:
                self.logger.log("WorkloadPatch: File for IPC does not exist at post")
            if len(self.child) == 0 or self.child[0].poll() is not None:
                self.logger.log("WorkloadPatch: Not app consistent backup")
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadQuiescingTimeout,"not app consistent"))
                return
            elif self.child[0].poll() is None:
                self.logger.log("WorkloadPatch: pre connection still running. Sending kill signal")
                self.child[0].kill()
        else: #non IPC based workloads
            if daemonProcess is None or daemonProcess.poll() is not None:
                self.logger.log("WorkloadPatch: Not app consistent backup")
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadQuiescingTimeout,"not app consistent"))
                return
            elif daemonProcess.poll() is None:
                self.logger.log("WorkloadPatch: pre connection still running. Sending kill signal")
                daemonProcess.kill()

        postWorkloadStatus = self.workloadStatus()
        if postWorkloadStatus != preWorkloadStatus:
            self.logger.log("WorkloadPatch: Pre and post database status different.")
        if "OPEN" in str(postWorkloadStatus):
            self.logger.log("WorkloadPatch: Post- Workload is open")
        elif "NOT APPLY" in str(postWorkloadStatus):
            self.logger.log("WorkloadPatch: Post- WorkloadStatus not apply")
        else:
            self.logger.log("WorkloadPatch: Post- Workload is not open")
            self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadDatabaseNotOpen, "Post- Workload is not open"))
            return None
        
        if 'mysql' in self.name.lower() or 'mariadb' in self.name.lower():
            self.logger.log("WorkloadPatch: Create connection string for post master")
            postscript = os.path.join(self.temp_script_folder, self.scriptpath + "/postMysqlMaster.sql")
            args = self.sudo_user+" "+self.command+self.name+" "+self.cred_string+" < "+postscript
            self.logger.log("WorkloadPatch: command to execute: "+str(self.sudo_user)+"  "+str(self.command))
            post_child = subprocess.Popen(args,stdout=subprocess.PIPE,stdin=subprocess.PIPE,shell=True,stderr=subprocess.PIPE)
        elif 'oracle' in self.name.lower():
            self.logger.log("WorkloadPatch: Post- Inside oracle post")
            postOracle = self.command + "sqlplus" + " -S -R 2 /nolog @" + os.path.join(self.temp_script_folder, self.scriptpath + "/postOracleMaster.sql ")
            args = ["su", "-", self.linux_user, "-c", postOracle]
            self.logger.log("WorkloadPatch: argument passed for post script:"+str(args))
            process = subprocess.Popen(args, stdout=subprocess.PIPE)
            wait_counter = 5
            while process.poll()==None and wait_counter>0:
                wait_counter -= 1
                sleep(2)
            self.logger.log("WorkloadPatch: Post- Completed")
            self.callLogBackup()
        elif 'postgres' in self.name.lower():
            self.logger.log("WorkloadPatch: Post- Inside postgres post")
            postPostgres = self.command + "psql " + self.cred_string + " -f " + os.path.join(os.getcwd(), "main/workloadPatch/"+self.scriptpath+"/postPostgresMaster.sql")
            args =  "su - "+self.linux_user+" -c "+"\'"+postPostgres+"\'"
            self.logger.log("WorkloadPatch: argument passed for post script:"+str(self.linux_user)+"  "+str(self.command))
            process = subprocess.Popen(args,stdout=subprocess.PIPE, shell=True)
            wait_counter = 5
            while process.poll()==None and wait_counter>0:
                wait_counter -= 1
                sleep(2)
            self.logger.log("WorkloadPatch: Post- Completed")
        #Add new workload support here
        else:
            self.logger.log("WorkloadPatch: Unsupported workload name")
            self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadInvalidWorkloadName, "Workload Not supported"))

    def preSlave(self):
        self.logger.log("WorkloadPatch: Entering pre mode for sloave")
        if self.ipc_folder != None:
            self.outfile = os.path.join(self.ipc_folder, "azbackupIPC.txt")
            if os.path.exists(self.outfile):
                os.remove(self.outfile)
            else:
                self.logger.log("WorkloadPatch: File for IPC does not exist at pre")
        
        global preWorkloadStatus
        preWorkloadStatus = self.workloadStatus()
        if "OPEN" in str(preWorkloadStatus):
            self.logger.log("WorkloadPatch: Pre- WorkloadStatus is open")
        elif "NOT APPLY" in str(preWorkloadStatus):
            self.logger.log("WorkloadPatch: Pre- WorkloadStatus not apply")
        else:
            self.logger.log("WorkloadPatch: Pre- WorkloadStatus not open.")
            self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadDatabaseNotOpen, "Pre- Workload not open"))
            return None

        if 'mysql' in self.name.lower() or 'mariadb' in self.name.lower():
            self.logger.log("WorkloadPatch: Create connection string for preslave mysql")
            if self.outfile == "":
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadIPCDirectoryMissing, "IPC directory missing"))
                return None
            prescript = os.path.join(self.temp_script_folder, self.scriptpath + "/preMysqlSlave.sql")
            arg = self.sudo_user+" "+self.command+self.name+" "+self.cred_string+" -e\"set @timeout="+self.timeout+";set @outfile=\\\"\\\\\\\""+self.outfile+"\\\\\\\"\\\";source "+prescript+";\""
            binary_thread = threading.Thread(target=self.thread_for_sql, args=[arg])
            binary_thread.start()
            self.waitForPreScriptCompletion()
        elif 'oracle' in self.name.lower():
            self.logger.log("WorkloadPatch: Pre- Inside oracle pre")
            preOracle = self.command + "sqlplus" + " -S -R 2 /nolog @" + os.path.join(self.temp_script_folder, self.scriptpath + "/preOracleMaster.sql ")
            args = ["su", "-", self.linux_user, "-c", preOracle]
            process = subprocess.Popen(args, stdout=subprocess.PIPE)
            wait_counter = 5
            while process.poll() == None and wait_counter>0:
                wait_counter -= 1
                sleep(2)
            self.timeoutDaemon()
            self.logger.log("WorkloadPatch: Pre- Exiting pre mode for slave")
        #Add new workload support here
        else:
            self.logger.log("WorkloadPatch: Unsupported workload name")
            self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadInvalidWorkloadName, "Workload Not supported"))
         
    def postSlave(self):
        self.logger.log("WorkloadPatch: Entering post mode for slave")
        if self.ipc_folder != None: #IPCm based workloads
            if os.path.exists(self.outfile):
                os.remove(self.outfile)
            else:
                self.logger.log("WorkloadPatch: File for IPC does not exist at post")
            if len(self.child) == 0 or self.child[0].poll() is not None:
                self.logger.log("WorkloadPatch: Not app consistent backup")
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadQuiescingTimeout,"not app consistent"))
                return
            elif self.child[0].poll() is None:
                self.logger.log("WorkloadPatch: pre connection still running. Sending kill signal")
                self.child[0].kill()
        else: #non IPC based workloads
            if daemonProcess is None or daemonProcess.poll() is not None:
                self.logger.log("WorkloadPatch: Not app consistent backup")
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadQuiescingTimeout,"not app consistent"))
                return
            elif daemonProcess.poll() is None:
                self.logger.log("WorkloadPatch: pre connection still running. Sending kill signal")
                daemonProcess.kill()
        
        postWorkloadStatus = self.workloadStatus()
        if postWorkloadStatus != preWorkloadStatus:
            self.logger.log("WorkloadPatch: Pre and post database status different.")
        if "OPEN" in str(postWorkloadStatus):
            self.logger.log("WorkloadPatch: Post- Workload is open")
        elif "NOT APPLY" in str(postWorkloadStatus):
            self.logger.log("WorkloadPatch: Post- WorkloadStatus not apply")
        else:
            self.logger.log("WorkloadPatch: Post- Workload is not open")
            self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadDatabaseNotOpen, "Post- Workload is not open"))
            return None

        if 'mysql' in self.name.lower() or 'mariadb' in self.name.lower():
            self.logger.log("WorkloadPatch: Create connection string for post slave")
            postscript = os.path.join(self.temp_script_folder, self.scriptpath + "/postMysqlSlave.sql")
            args = self.sudo_user+" "+self.command+self.name+" "+self.cred_string+" < "+postscript
            self.logger.log("WorkloadPatch: command to execute: "+str(args))
            post_child = subprocess.Popen(args,stdout=subprocess.PIPE,stdin=subprocess.PIPE,shell=True,stderr=subprocess.PIPE)
        elif 'oracle' in self.name.lower():
            self.logger.log("WorkloadPatch: Post- Inside oracle post")
            postOracle = self.command + "sqlplus" + " -S -R 2 /nolog @" + os.path.join(self.temp_script_folder, self.scriptpath + "/postOracleMaster.sql ")
            args = ["su", "-", self.linux_user, "-c", postOracle]
            process = subprocess.Popen(args, stdout=subprocess.PIPE)
            while process.poll()==None:
                sleep(1)
            self.logger.log("WorkloadPatch: Post- Completed")
            self.callLogbackup()
        #Add new workload support here
        else:
            self.logger.log("WorkloadPatch: Unsupported workload name")
            self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadInvalidWorkloadName, "Workload Not supported"))
    
    def preMasterDB(self):
        pass
       
    def preSlaveDB(self):
        pass

    def postMasterDB(self):
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
                        name = config.get("workload", 'workload_name')
                        if name in self.supported_workload:
                            self.name = name
                            self.logger.log("WorkloadPatch: config workload command "+ self.name)
                        else:
                            return None
                    else:
                        return None
                    if config.has_option("workload", 'command_path'):                        
                        self.command = config.get("workload", 'command_path')
                        self.logger.log("WorkloadPatch: config workload command "+ self.command)
                    if config.has_option("workload", 'credString'):
                        self.cred_string = config.get("workload", 'credString')
                        self.logger.log("WorkloadPatch: config workload cred_string found")
                    elif not config.has_option("workload", 'linux_user'):
                        self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadAuthorizationMissing, "Cred and linux user string missing"))
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
                    if config.has_option("workload", 'linux_user'):
                        self.linux_user = config.get("workload", 'linux_user')
                        self.logger.log("WorkloadPatch: config linux user of pre script "+ self.linux_user)
                        self.sudo_user = "sudo -u "+self.linux_user
                    if config.has_option("workload", 'dbnames'):
                        dbnames_list = config.get("workload", 'dbnames') #mydb1;mydb2;mydb3
                        self.dbnames = dbnames_list.split(';')
                    if config.has_option("workload", 'customScriptEnabled'):
                        self.custom_scripts_enabled = config.get("workload", 'customScriptEnabled')
                        self.logger.log("WorkloadPatch: config workload customer using custom script "+ self.custom_scripts_enabled)
                        if int(self.custom_scripts_enabled) == 1:
                            self.scriptpath= "CustomScripts"
                    if config.has_section("logbackup"):
                        self.logbackup = "enable"
                        self.logger.log("WorkloadPatch: Logbackup Enabled")
                else:
                    self.logger.log("WorkloadPatch: workload config section missing. File system consistent backup")
            else:
                self.logger.log("WorkloadPatch: workload config file missing. File system consistent backup")
        except Exception as e:
            self.logger.log("WorkloadPatch: exception in workload conf file parsing")
            if(self.name != None):
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadConfParsingError, "exception in workloadconfig parsing"))
    
    def createTempScriptsFolder(self):
        self.logger.log("WorkloadPatch: Creating temporary scripts folder")
        try:
            originalScriptsPath = os.path.join(os.getcwd(), "main/workloadPatch/"+self.scriptpath)
            newScriptsPath = os.path.join(self.temp_script_folder, self.scriptpath)
            
            if (os.path.exists(self.temp_script_folder) == False):
                self.logger.log("WorkloadPatch: Script folder directory path not found..creating")
                os.makedirs(self.temp_script_folder)
                
            if (os.path.exists(newScriptsPath)):
                self.logger.log("WorkloadPatch: Existing temporary scripts folder found..removing")
                self.removeTempScriptsFolder()
                
            copyProcess = subprocess.Popen(['cp','-ar',originalScriptsPath,self.temp_script_folder])
            copyProcess.wait()
            changeOwnerProcess = subprocess.Popen(['chown','-R',self.linux_user,newScriptsPath], stdout=subprocess.PIPE)
            changeOwnerProcess.wait()
            permissionProcess = subprocess.Popen(['chmod','-R','500',newScriptsPath], stdout=subprocess.PIPE)
            permissionProcess.wait()
            self.logger.log("WorkloadPatch: Script files copied to temporary scripts folder present at " + newScriptsPath)
        except Exception as e:
            self.logger.log("WorkloadPatch: exception in creating temporary scripts folder: " + str(e))
        
    
    def removeTempScriptsFolder(self):
        self.logger.log("WorkloadPatch: Removing temporary scripts folder")
        try:
            newScriptsPath = os.path.join(self.temp_script_folder, self.scriptpath)
            removalProcess = subprocess.Popen(['rm','-rf',newScriptsPath], stdout=subprocess.PIPE)
            removalProcess.wait()
            self.logger.log("WorkloadPatch: Removed temporary scripts folder")
        except Exception as e:
            self.logger.log("WorkloadPatch: exception in removing temporary scripts folder: " + str(e))
        
        
    def populateErrors(self):
        if len(self.error_details) > 0:
            errdetail = self.error_details[0]
            return errdetail
        else:
            return None

    def waitForPreScriptCompletion(self):
        if self.ipc_folder != None:
            wait_counter = 5 
            while len(self.child) == 0 and wait_counter > 0:
                self.logger.log("WorkloadPatch: child not created yet", True)
                wait_counter -= 1
                sleep(2)
            if wait_counter > 0:
                self.logger.log("WorkloadPatch: sql subprocess Created "+str(self.child[0].pid))
            else:
                self.logger.log("WorkloadPatch: sql connection failed")
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadConnectionError, "sql connection failed"))
                return None
            wait_counter = 60
            while os.path.exists(self.outfile) == False and wait_counter > 0:
                self.logger.log("WorkloadPatch: Waiting for sql to complete")
                wait_counter -= 1
                sleep(2)
            if wait_counter > 0:
                self.logger.log("WorkloadPatch: pre at server level completed")
            else:
                self.logger.log("WorkloadPatch: pre failed to quiesce")
                self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadQuiescingError, "pre failed to quiesce"))
                return None
        
    def timeoutDaemon(self):
        global daemonProcess
        argsDaemon = "su - "+self.linux_user+" -c " + "'" + os.path.join(self.temp_script_folder, self.scriptpath + "/timeoutDaemon.sh")+" "+self.name+" "+self.command+" \""+self.cred_string+"\" "+self.timeout+" "+os.path.join(self.temp_script_folder, self.scriptpath + "'")
        devnull = open(os.devnull, 'w')
        daemonProcess = subprocess.Popen(argsDaemon, stdout=devnull, stderr=devnull, shell=True)
            
        wait_counter = 5
        while (daemonProcess is None or daemonProcess.poll() is not None) and wait_counter > 0:
            self.logger.log("WorkloadPatch: daemonProcess not created yet", True)
            wait_counter -= 1
            sleep(1)
        if wait_counter > 0:
            self.logger.log("WorkloadPatch: daemonProcess Created "+str(daemonProcess.pid))
        else:
            line= daemonProcess.stdout.readline()
            self.logger.log("WorkloadPatch: daemon process creation failed "+str(line))
            self.error_details.append(ErrorDetail(CommonVariables.FailedWorkloadConnectionError, "sql connection failed"))
        return None

    def workloadStatus(self):
        if 'oracle' in self.name.lower():
            statusArgs =  "su - " + self.linux_user + " -c " +"'" + self.command + "sqlplus" +" -S -R 2 /nolog<<-EOF\nCONNECT / AS SYSBACKUP\nWHENEVER SQLERROR CONTINUE\nSELECT STATUS FROM V\$INSTANCE;\nEOF'"
            oracleStatus = subprocess.check_output(statusArgs, shell=True)
            self.logger.log("WorkloadPatch: workloadStatus- " + str(oracleStatus))
            return oracleStatus
        return "NOT APPLY"

    def thread_for_sql(self,args):
        self.logger.log("WorkloadPatch: command to execute: "+str(args))
        self.child.append(subprocess.Popen(args,stdout=subprocess.PIPE,stdin=subprocess.PIPE,shell=True,stderr=subprocess.PIPE))
        sleep(1)
    
    def getRole(self):
        return "master"
    
    def callLogBackup(self):
        if 'enable' in self.logbackup.lower():
            self.logger.log("WorkloadPatch: Initializing logbackup")
            logbackupObject = LogBackupPatch()
        else:
            return
