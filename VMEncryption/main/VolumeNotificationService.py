#!/usr/bin/env python
#
# VM Backup extension
#
# Copyright 2014 Microsoft Corporation
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

import os
import shutil
try:
    import ConfigParser as ConfigParsers
except ImportError:
    import configparser as ConfigParsers
from Common import CommonVariables
from CommandExecutor import CommandExecutor,ProcessCommunicator

'''This class used to create a systemd service for volume notifiction.
for block device type and partition sub system.
VNS service invokes ADE if any add/change event get created.'''
class VolumeNotificationService(object):
    def __init__(self,logger,servicepath = None):
        '''init call'''
        self.logger = logger
        self.command_executor = CommandExecutor(self.logger)
        if servicepath and os.path.exists(servicepath):
            self.workingDirectory = servicepath
        else:
             absFilePath=os.path.abspath(__file__)
             fileDirectory=os.path.dirname(absFilePath)
             self.workingDirectory = os.path.join(fileDirectory,'..')
        #normalize the path
        self.workingDirectory = os.path.normpath(self.workingDirectory)

    def _service_file(self):
        '''service file path'''
        return os.path.join(self.workingDirectory,CommonVariables.vns_service_file)
    
    def _temp_service_file(self):
        '''get tem service file path'''
        return self._service_file()+'_tmp'
    
    def _service_file_exists(self):
        '''check if service file exists.'''
        serviceFilePath = self._service_file()
        return os.path.exists(serviceFilePath)

    def _edit_service_config(self,log_path):
        '''edit WorkingDirectory and ExecStart path of config file'''
        if self._service_file_exists():
            config = ConfigParsers.ConfigParser()
            config.optionxform = lambda option:option
            #update workingdirectory and execution path in service file. 
            config.read(self._service_file())
            #update WorkingDirectory
            if 'WorkingDirectory' in config['Service']:
                config['Service']['WorkingDirectory']=self.workingDirectory             
            #update ExecStart
            if 'ExecStart' in config['Service']:
                vnsservice = os.path.join(self.workingDirectory,CommonVariables.vns_service_name)
                if os.path.exists(vnsservice):
                    if log_path:
                        config['Service']['ExecStart'] ='{0} -d -l {1}'.format(vnsservice,log_path)
                    else:
                        config['Service']['ExecStart'] ='{0} -d'.format(vnsservice)
            #save config file
            with open(self._temp_service_file(), 'w') as configfile:
                config.write(configfile) 
            return True
        return False
    
    def mask(self):
        '''mask service'''
        cmd = 'systemctl mask '+CommonVariables.vns_service_file
        return self.command_executor.Execute(cmd)==0
        
    def unmask(self):
        '''unmask service'''
        cmd = 'systemctl unmask '+CommonVariables.vns_service_file
        return self.command_executor.Execute(cmd)==0

    def enable(self):
        '''enable the vns service,required in case of restart.'''
        cmd = 'systemctl enable '+CommonVariables.vns_service_file
        return self.command_executor.Execute(cmd)==0
    
    def disable(self):
        '''disabling the service'''
        cmd = 'systemctl disable '+CommonVariables.vns_service_file
        return self.command_executor.Execute(cmd)==0
    
    def is_enabled(self):
        '''check if service is enabled or not'''
        cmd = 'systemctl is-enabled '+CommonVariables.vns_service_file
        proc_comm = ProcessCommunicator()
        ret = self.command_executor.Execute(cmd,communicator=proc_comm)==0
        status = ""
        if proc_comm.stderr:
            status=proc_comm.stderr.strip()
        else:
            status=proc_comm.stdout.strip()
        msg="VolumeNotificationService:is_enabled status is {0}".format(status)
        self.logger.log(msg=msg)
        return ret
        

    def register(self,log_path=None):
        '''update service config file in systemd and load it'''
        return_code=1
        self.logger.log("service file path: {0}".format(self._service_file()))
        if self._edit_service_config(log_path):
            runningservicefilepath = os.path.join(CommonVariables.vns_service_placeholder_path,
                                                   CommonVariables.vns_service_file)
            if os.path.exists(runningservicefilepath):
                os.remove(runningservicefilepath)
            shutil.copy(self._temp_service_file(),runningservicefilepath)
            cmd = 'systemctl daemon-reload'
            return_code = self.command_executor.Execute(cmd)
        return return_code==0

    def unregister(self):
        '''remove service config file from systemd and reload systemctl.'''
        #remove file from service placeholder.
        runningservicefilepath = os.path.join(CommonVariables.vns_service_placeholder_path,
                                              CommonVariables.vns_service_file)
        if os.path.exists(runningservicefilepath):
            os.remove(runningservicefilepath)
        cmd = 'systemctl daemon-reload'
        return self.command_executor.Execute(cmd)==0

    def start(self):
        '''this will start the service'''
        cmd = 'systemctl start ' + CommonVariables.vns_service_file
        return self.command_executor.Execute(cmd)==0

    def stop(self):
        '''this will stop the service'''
        cmd = 'systemctl stop ' + CommonVariables.vns_service_file
        return self.command_executor.Execute(cmd)==0

    def restart(self):
        '''This will restart the service'''
        cmd = 'systemctl restart '+CommonVariables.vns_service_file
        return self.command_executor.Execute(cmd)==0

    def is_active(self):
        '''
        ActiveState of service is active (0) and inactive (1) 
        '''
        cmd = 'systemctl is-active '+ CommonVariables.vns_service_file
        proc_comm = ProcessCommunicator()
        ret=self.command_executor.Execute(cmd,communicator=proc_comm)==0
        status = ""
        if proc_comm.stderr:
            status=proc_comm.stderr.strip()
        else:
            status=proc_comm.stdout.strip()
        msg="VolumeNotificationService:is_active status is {0}".format(status)
        self.logger.log(msg=msg)
        return ret