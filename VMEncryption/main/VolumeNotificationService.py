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

from configparser import ConfigParser
from Common import CommonVariables
from CommandExecutor import CommandExecutor,ProcessCommunicator

'''This class used to create a systemd service for volume notifiction.
for block device type and partition sub system.
VNS service invokes ADE if any add/change event get created.'''
class VolumeNotificationService(object):
    VnsServiceRegistered = "registered"
    VnsServiceNotRegistered = "notregistered"
    VnsServiceActive = "active"
    VnsServiceNotActive = "inactive"
    VnsServiceEnabled="enabled"

    def __init__(self,logger,servicepath = None):
        '''init call'''
        self.logger = logger
        self.command_executor = CommandExecutor(self.logger)
        if servicepath and os.path.exists(servicepath):
            self.workingDirectory = servicepath
        else:
             self.workingDirectory = os.path.join(os.getcwd(),'..')
        #normalize the path
        self.workingDirectory = os.path.normpath(self.workingDirectory)
    
    def _service_file(self):
        '''service file path'''
        return os.path.join(self.workingDirectory,CommonVariables.vns_service_file)
    
    def _tmp_service_file(self):
        '''get tem service file path'''
        return self._service_file()+'_tmp'
    
    def _service_file_exists(self):
        '''check if service file exists.'''
        serviceFilePath = self._service_file()
        return os.path.exists(serviceFilePath)
    
    def enable(self):
        '''enable the vns service'''
        cmd = 'systemctl enable '+CommonVariables.vns_service_file
        return self.command_executor.Execute(cmd)
    
    def disable(self):
        '''disabling the service'''
        cmd = 'systemctl disable '+CommonVariables.vns_service_file
        return self.command_executor.Execute(cmd)
    
    def is_enabled(self):
        '''check if service is enabled or not, if service not registered it returns VnsServiceNotRegistered'''
        cmd = 'systemctl is-enabled '+CommonVariables.vns_service_file
        proc_comm = ProcessCommunicator()
        return_code = self.command_executor.Execute(cmd,communicator=proc_comm)
        if return_code!=0 and proc_comm.stderr:
            self.logger("VolumeNotificationService::is_enabled %s",proc_comm.stderr.strip())
            return VolumeNotificationService.VnsServiceNotRegistered
        return proc_comm.stdout.strip()

    def _edit_service_config(self):
        '''edit WorkingDirectory and ExecStart path of config file'''
        if self._service_file_exists():
            config = ConfigParser()
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
                     config['Service']['ExecStart'] =vnsservice+' -d'
            #save config file
            with open(self._tmp_service_file(), 'w') as configfile:
                config.write(configfile) 
            return True
        return False

    def register(self):
        '''update service config file in systemd and load it'''
        return_code=None
        if self._edit_service_config():
            runningservicefilepath = os.path.join(CommonVariables.vns_service_placeholder_path,
                                                   CommonVariables.vns_service_file)
            if os.path.exists(runningservicefilepath):
                os.remove(runningservicefilepath)
            shutil.copy(self._tmp_service_file(),runningservicefilepath)
            cmd = 'systemctl daemon-reload'
            return_code = self.command_executor.Execute(cmd)
            if return_code == 0:
                #enable the service 
                return_code = self.enable()
        return return_code

    def deRegister(self):
        '''remove service config file from systemd and reload systemctl.'''
        #stop service
        self.stop()
        #disable service
        self.disable()
        #remove file from service placeholder.
        runningservicefilepath = os.path.join(CommonVariables.vns_service_placeholder_path,
                                              CommonVariables.vns_service_file)
        if os.path.exists(runningservicefilepath):
            os.remove(runningservicefilepath)
        cmd = 'systemctl daemon-reload'
        return_code = self.command_executor.Execute(cmd)
        return return_code

    def start(self):
        '''this will start the service'''
        cmd = 'systemctl start ' + CommonVariables.vns_service_file
        return_code = self.command_executor.Execute(cmd)
        return return_code

    def stop(self):
        '''this will stop the service'''
        cmd = 'systemctl stop ' + CommonVariables.vns_service_file
        return self.command_executor.Execute(cmd)

    def restart(self):
        '''This will restart the service'''
        cmd = 'systemctl restart '+CommonVariables.vns_service_file
        return self.command_executor.Execute(cmd)

    def status(self):
        '''
        ActiveState of service is active and inactive 
        '''
        cmd = 'systemctl show -p ActiveState --value '+ CommonVariables.vns_service_file
        proc_comm=ProcessCommunicator()
        self.command_executor.Execute(cmd,communicator=proc_comm)
        status=proc_comm.stdout
        return status.strip()