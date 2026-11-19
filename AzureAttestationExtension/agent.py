#!/usr/bin/env python
#
# AzureAttestationLinuxAgent Extension
#
# Copyright 2020 Microsoft Corporation
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
import os.path
import signal
import pwd
import grp
import re
import sys
import traceback
import time
import platform
import subprocess
import json
import base64
import inspect
import shutil
import crypt
import xml.dom.minidom
import re
from distutils.version import LooseVersion

from threading import Thread

try:
    from Utils.WAAgentUtil import waagent
    import Utils.HandlerUtil as HUtil    
    
except Exception as e:
    # These utils have checks around the use of them; this is not an exit case
    print('Importing utils failed with error: {0}'.format(e))

# Global Variables
InitialRetrySleepSeconds = 30

# https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
# Well known error codes for extnesion handlers. For azure attestation unsupported OS is important as we do not want to get flagged
# if customer tries to run it on one of the unsupported distros.
MissingorInvalidParameterErrorCode = 53
UnsupportedOperatingSystem = 51

# Configuration
HUtilObject = None
SettingsSequenceNumber = None
HandlerEnvironment = None
SettingsDict = None

# Default configuration settings
MaaEndpoint = "https://microsoft.attestation.net/",
AscReportingEndpoint = "https://management.azure.com/",
UseCustomeToken = "false"        
    
# Change permission of log path - if we fail, that is not an exit case
# like any other extension attestation extension is started as a root so we should be good here.
try:
    ext_log_path = '/var/log/azure/'
    if os.path.exists(ext_log_path):
        os.chmod(ext_log_path, 700)
except:
    pass

def main():
    """
    Main method
    Parse out operation from argument, invoke the operation, and finish.
    """
    init_waagent_logger()
    waagent_log_info('Azure Attestation Agent for Linux started to handle.')

    # Determine the operation being executed
    operation = None
    try:
        option = sys.argv[1]
        if re.match('^([-/]*)(disable)', option):
            operation = 'Disable'
        elif re.match('^([-/]*)(uninstall)', option):
            operation = 'Uninstall'
        elif re.match('^([-/]*)(install)', option):
            operation = 'Install'
        elif re.match('^([-/]*)(enable)', option):
            operation = 'Enable'
        elif re.match('^([-/]*)(update)', option):
            operation = 'Update'
    except Exception as e:
        waagent_log_error(str(e))

    if operation is None:
        log_and_exit('Unknown', 1, 'No valid operation provided')

    # Set up for exit code and any error messages
    exit_code = 0
    message = '{0} succeeded'.format(operation)

    # Invoke operation
    try:
        global HUtilObject
        HUtilObject = parse_context(operation)
        exit_code, output = operations[operation]()

        # Exit code 1 indicates a general problem that doesn't have a more
        # specific error code; it often indicates a missing dependency. Although
        # we don't have it right now, we should handle it properly.
        if exit_code is 1 and operation == 'Install':
            message = 'Install failed with exit code 1. Please check that ' \
                      'dependencies are installed. For details, check logs ' \
                      'in /var/log/azure/Microsoft.Azure.Attestation' \
                      '.AzureAttestationLinuxAgent'        
        elif exit_code is not 0:
            message = '{0} failed with exit code {1} {2}'.format(operation,
                                                             exit_code, output)

    except AzureAttestationAgentForLinuxException as e:
        exit_code = e.error_code
        message = e.get_error_message(operation)
    except Exception as e:
        exit_code = 1
        message = '{0} failed with error: {1}\n' \
                  'Stacktrace: {2}'.format(operation, e,
                                           traceback.format_exc())
     
    # Finish up and log messages
    log_and_exit(operation, exit_code, message)        
  

def install():
    """
    Ensure that this VM distro and version are supported.    
    """
    
    # We want to check if extension supports current distro if not 
    # then we want to exit with exit code 51 which is special error code 
    # that waagent uderstands as unsuuported OS/distro.
    exit_if_vm_not_supported('Install')

    return 0, "Successfully verified installation requirements"

def uninstall():
    """
    Uninstall the Azure Attestation Linux Agent.
    Note: uninstall operation times out from WAAgent at 5 minutes.
    We will just try to claen up the attestation client process.
    Ideally we don't need to do it if disable is called before uninstall.
    """

    try:        
        exit_code, output = stop_attestation_client()
                                            
    except Exception as ex:
        exit_code = 1
        output = 'Uninstall failed with error: {0}\n' \
                'Stacktrace: {1}'.format(ex, traceback.format_exc())

    return exit_code, output

def enable():
    """
    Start the Azure Attestation Linux Agent Service
    This call will return non-zero or throw an exception if
    the settings provided are incomplete or incorrect.
    Note: enable operation times out from WAAgent at 5 minutes
    """
       
    

    public_settings, protected_settings = get_settings()   
    
    maa_endpoint = public_settings.get("maaEndpoint")
    if maa_endpoint is not None:
        MaaEndpoint = maa_endpoint
    
    asc_endpoint = public_settings.get("ascEndpoint")
    if asc_endpoint is not None:
        AscReportingEndpoint = asc_endpoint

    # override the config settings if present.    
    hutil_log_info('Handler initiating onboarding.')
    try:        
        exit_code, output = start_attestation_client()
                                            
    except Exception as ex:
        exit_code = 1
        output = 'Enable failed with error: {0}\n' \
                'Stacktrace: {1}'.format(ex, traceback.format_exc())

    
    return exit_code, output

def disable():
    """
    Disable Azure Attestation Linux Agent process on the VM.
    Note: disable operation times out from WAAgent at 15 minutes
    """
    
    try:        
        exit_code, output = stop_attestation_client()
                                            
    except Exception as ex:
        exit_code = 1
        output = 'Disable failed with error: {0}\n' \
                'Stacktrace: {1}'.format(ex, traceback.format_exc())

    return exit_code, output

def update():
    """
    Update the current installation of AzureAttestationLinuxAgent
    No logic to install the agent as agent -> install() will be called 
    with udpate because upgradeMode = "UpgradeWithInstall" set in HandlerManifest
    """
    
    return 0, ""

# Dictionary of operations strings to methods
operations = {'Disable' : disable,
              'Uninstall' : uninstall,
              'Install' : install,
              'Enable' : enable,
              'Update' : update,
}

def parse_context(operation):
    """
    Initialize a HandlerUtil object for this operation.
    If the required modules have not been imported, this will return None.
    """
    hutil = None
    if ('Utils.WAAgentUtil' in sys.modules
            and 'Utils.HandlerUtil' in sys.modules):
        try:
            
            logFileName = 'extension.log'
            hutil = HUtil.HandlerUtility(waagent.Log, waagent.Error, logFileName=logFileName)
            hutil.do_parse_context(operation)
    
        # parse_context may throw KeyError if necessary JSON key is not
        # present in settings
        except KeyError as e:
            waagent_log_error('Unable to parse context with error: ' \
                              '{0}'.format(e))
            raise ParameterMissingException
    return hutil
 
    
def find_vm_distro(operation):
    """
    Finds the Linux Distribution this vm is running on. 
    """
    vm_dist = vm_id = vm_ver =  None
    try:
        vm_dist, vm_ver, vm_id = platform.linux_distribution()
    except AttributeError:
        vm_dist, vm_ver, vm_id = platform.dist()

    if not vm_dist and not vm_ver: # SLES 15 and others
        try:
            with open('/etc/os-release', 'r') as fp:
                for line in fp:
                    if line.startswith('ID='):
                        vm_dist = line.split('=')[1]
                        vm_dist = vm_dist.split('-')[0]
                        vm_dist = vm_dist.replace('\"', '').replace('\n', '')
                    elif line.startswith('VERSION_ID='):
                        vm_ver = line.split('=')[1]
                        vm_ver = vm_ver.split('.')[0]
                        vm_ver = vm_ver.replace('\"', '').replace('\n', '')
        except:
            log_and_exit(operation, UndeterminateOperatingSystem, 'Undeterminate operating system')
    return vm_dist, vm_ver


def is_vm_supported_for_extension(operation):
    """
    Checks if the VM this extension is running on is supported by AzureAttestationLinuxAgent
    Returns for platform.linux_distribution() 

    The supported distros of the AzureAttestationLinuxAgent are allowed to utilize
    this VM extension. All other distros will get error code 51. This error code should be exlcuded from 
    extension error reporting.
    """
    supported_dists = {'redhat' : ['8'], # Redhat                       
                       'red hat' : ['8'], # Redhat
                       'ubuntu' : ['18.04'], # Ubuntu
    }

    vm_supported = False
    vm_dist, vm_ver = find_vm_distro(operation)
    # Find this VM distribution in the supported list
    for supported_dist in supported_dists.keys():
        if not vm_dist.lower().startswith(supported_dist):
            continue

        # Check if this VM distribution version is supported
        vm_ver_split = vm_ver.split('.')
        for supported_ver in supported_dists[supported_dist]:
            supported_ver_split = supported_ver.split('.')

            # If vm_ver is at least as precise (at least as many digits) as
            # supported_ver and matches all the supported_ver digits, then
            # this VM is guaranteed to be supported
            vm_ver_match = True
            for idx, supported_ver_num in enumerate(supported_ver_split):
                try:
                    supported_ver_num = int(supported_ver_num)
                    vm_ver_num = int(vm_ver_split[idx])
                except IndexError:
                    vm_ver_match = False
                    break
                if vm_ver_num is not supported_ver_num:
                    vm_ver_match = False
                    break
            if vm_ver_match:
                vm_supported = True
                break

        if vm_supported:
            break

    return vm_supported, vm_dist, vm_ver


def exit_if_vm_not_supported(operation):
    """
    Check if this VM distro and version are supported by the AzureAttestationLinuxAgent.
    If VM is supported, find the package manager present in this distro
    If this VM is not supported, log the proper error code and exit.
    """
    vm_supported, vm_dist, vm_ver = is_vm_supported_for_extension(operation)
    if not vm_supported:
        log_and_exit(operation, UnsupportedOperatingSystem, 'Unsupported operating system: ' \
                                    '{0} {1}'.format(vm_dist, vm_ver))
    return 0


def run_command_and_log(cmd, check_error = True, log_cmd = True):
    """
    Run the provided shell command and log its output, including stdout and
    stderr.
    The output should not contain any PII, but the command might. In this case,
    log_cmd should be set to False.
    """
    exit_code, output = run_get_output(cmd, check_error, log_cmd)
    if log_cmd:
        hutil_log_info('Output of command "{0}": \n{1}'.format(cmd, output))
    else:
        hutil_log_info('Output: \n{0}'.format(output))
        
    # also write output to STDERR since WA agent uploads that to Azlinux Kusto DB	
    # take only the last 100 characters as extension cuts off after that	
    try:	
        if exit_code is not 0:	
            sys.stderr.write(output[-500:])        

        if "Permission denied" in output:
            # Enable failures
            # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
            exit_code = 52        
 
    except:	
        hutil_log_info('Failed to write output to STDERR')	
  
    return exit_code, output

def run_command_with_retries_output(cmd, retries, retry_check = None,
                             check_error = True, log_cmd = True,
                             initial_sleep_time = InitialRetrySleepSeconds,
                             sleep_increase_factor = 1):
    """
    Caller provides a method, retry_check, to use to determine if a retry
    should be performed. This must be a function with two parameters:
    exit_code and output
    The final_check can be provided as a method to perform a final check after
    retries have been exhausted
    Logic used: will retry up to retries times with initial_sleep_time in
    between tries
    If retry check is not none we will check if we should retry or not with 
    custom implementation of retry_check function
    """
    try_count = 0
    sleep_time = initial_sleep_time
    run_cmd = cmd
 
    while try_count <= retries:
        exit_code, output = run_command_and_log(run_cmd, check_error, log_cmd)
        
        """
        If retry_check is none then exit with curret exit_code.
        """
        if retry_check is not None:
            break
        
        should_retry, retry_message= retry_check(exit_code,  output)
        
        if not should_retry:
            break
        try_count += 1
        hutil_log_info(retry_message)
        time.sleep(sleep_time)
        sleep_time *= sleep_increase_factor

    return exit_code, output


def get_settings():
    """
    Retrieve the configuration for this extension operation
    """
    global SettingsDict
    public_settings = None
    protected_settings = None

    if HUtilObject is not None:
        public_settings = HUtilObject.get_public_settings()
        protected_settings = HUtilObject.get_protected_settings()
    elif SettingsDict is not None:
        public_settings = SettingsDict['public_settings']
        protected_settings = SettingsDict['protected_settings']

    return public_settings, protected_settings


def update_status_file(operation, exit_code, exit_status, message):
    """
    Mimic HandlerUtil method do_status_report in case hutil method is not
    available
    Write status to status file
    """
    
    handler_env = get_handler_env()
    try:
        extension_version = str(handler_env['version'])
        status_dir = str(handler_env['handlerEnvironment']['statusFolder'])
    except:
        extension_version = "1.0"
        status_dir = os.path.join(os.getcwd(), 'status')

    status_txt = [{
        "version" : extension_version,
        "timestampUTC" : time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status" : {
            "name" : "Microsoft.Azure.Attestation.AzureAttestationLinuxAgent",
            "operation" : operation,
            "status" : exit_status,
            "code" : exit_code,
            "formattedMessage" : {
                "lang" : "en-US",
                "message" : message
            }
        }
    }]

    status_json = json.dumps(status_txt)

    # Find the most recently changed config file and then use the
    # corresponding status file
    latest_seq_no = get_latest_seq_no()

    status_path = os.path.join(status_dir, '{0}.status'.format(latest_seq_no))
    status_tmp = '{0}.tmp'.format(status_path)
    with open(status_tmp, 'w+') as tmp_file:
        tmp_file.write(status_json)
    os.rename(status_tmp, status_path)


def get_handler_env():
    """
    Retrieve the contents of HandlerEnvironment.json as JSON
    """
    global HandlerEnvironment
    
    if HandlerEnvironment is None:
        handler_env_path = os.path.join(os.getcwd(), 'HandlerEnvironment.json')
        try:
            with open(handler_env_path, 'r') as handler_env_file:
                handler_env_txt = handler_env_file.read()
            handler_env = json.loads(handler_env_txt)
            if type(handler_env) == list:
                handler_env = handler_env[0]
            HandlerEnvironment = handler_env
        except Exception as e:
            waagent_log_error(str(e))

    return HandlerEnvironment


def get_latest_seq_no():
    """
    Determine the latest operation settings number to use. WAAgent uses sequence number to identify 
    latest config update version.
    """
    
    global SettingsSequenceNumber
     
    if SettingsSequenceNumber is None:
        if HUtilObject is None:
            
            handler_env = get_handler_env()
            try:
                config_dir = str(handler_env['handlerEnvironment']['configFolder'])
            except:
                config_dir = os.path.join(os.getcwd(), 'config')

            latest_seq_no = -1
            cur_seq_no = -1
            latest_time = None
            try:
                for dir_name, sub_dirs, file_names in os.walk(config_dir):
                    for file_name in file_names:
                        file_basename = os.path.basename(file_name)
                        match = re.match(r'[0-9]{1,10}\.settings', file_basename)
                        if match is None:
                            continue
                        cur_seq_no = int(file_basename.split('.')[0])
                        file_path = os.path.join(config_dir, file_name)
                        cur_time = os.path.getmtime(file_path)
                        if latest_time is None or cur_time > latest_time:
                            latest_time = cur_time
                            latest_seq_no = cur_seq_no
            except:
                pass
            if latest_seq_no < 0:
                latest_seq_no = 0            
        else:
            SettingsSequenceNumber = HUtilObject._get_current_seq_no()

    return SettingsSequenceNumber


def run_get_output(cmd, chk_err = False, log_cmd = True):
    """
    Mimic waagent mothod RunGetOutput in case waagent is not available
    Run shell command and return exit code and output
    """
    if 'Utils.WAAgentUtil' in sys.modules:  
            exit_code, output = waagent.RunGetOutput(cmd, chk_err, log_cmd)
    else:
        try:
            output = subprocess.check_output(cmd, stderr = subprocess.STDOUT,
                                             shell = True)
            exit_code = 0
        except subprocess.CalledProcessError as e:
            exit_code = e.returncode
            output = e.output

    return exit_code, output.encode('utf-8').strip()


def init_waagent_logger():
    """
    Initialize waagent logger
    If waagent has not been imported, catch the exception
    """
    try:
        waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout', True)
    except Exception as e:
        print('Unable to initialize waagent log because of exception ' \
              '{0}'.format(e))

def waagent_log_info(message):
    """
    Log informational message, being cautious of possibility that waagent may
    not be imported
    """
    if 'Utils.WAAgentUtil' in sys.modules:
        waagent.Log(message)
    else:
        print('Info: {0}'.format(message))


def waagent_log_error(message):
    """
    Log error message, being cautious of possibility that waagent may not be
    imported
    """
    if 'Utils.WAAgentUtil' in sys.modules:
        waagent.Error(message)
    else:
        print('Error: {0}'.format(message))


def hutil_log_info(message):
    """
    Log informational message, being cautious of possibility that hutil may
    not be imported and configured
    """
    if HUtilObject is not None:
        HUtilObject.log(message)
    else:
        print('Info: {0}'.format(message))


def hutil_log_error(message):
    """
    Log error message, being cautious of possibility that hutil may not be
    imported and configured
    """
    if HUtilObject is not None:
        HUtilObject.error(message)
    else:
        print('Error: {0}'.format(message))


def log_and_exit(operation, exit_code = 1, message = ''):
    """
    Log the exit message and perform the exit
    """
    if exit_code is 0:
        waagent_log_info(message)
        hutil_log_info(message)
        exit_status = 'success'
    else:
        waagent_log_error(message)
        hutil_log_error(message)
        exit_status = 'failed'

    if HUtilObject is not None:
        HUtilObject.do_exit(exit_code, operation, exit_status, str(exit_code),
                            message)
    else:
        update_status_file(operation, str(exit_code), exit_status, message)
        sys.exit(exit_code)

def get_log_directory():
    if HUtilObject is None:
        handler_env = get_handler_env()
        return str(handler_env['handlerEnvironment']['logFolder'])
    else:
        return HUtilObject._context._log_dir

def start_attestation_client():
    """
    Start attestation process that performs periodic monitoring of attestion process.
    :return: None

    """
    stop_process('attestation_client')    
    log_dir = get_log_directory()
    attestation_client_filepath = os.path.join(os.getcwd(),'attestationclient')
    args = [attestation_client_filepath, '-e', MaaEndpoint, '-a' AscReportingEndpoint, '-l' log_dir ]
    log = open(os.path.join(os.getcwd(), 'daemon.log'), 'w')
    
    child = subprocess.Popen(args, stdout=log, stderr=log)        
    pids_filepath = os.path.join(os.getcwd(), 'attestation_client.pid')
    
    with open(pids_filepath, 'w') as f:
        f.write(str(child.pid) + '\n')
  
def stop_attestation_client(processname):
    pid_file = 'attestation_client.pid'
    pids_filepath = os.path.join(os.getcwd(),pid_file)

    # kill existing attestation process
    if os.path.exists(pids_filepath):
        with open(pids_filepath, "r") as f:
            for pids in f.readlines():
                kill_cmd = "kill " + pids
                run_command_and_log(kill_cmd)
                run_command_and_log("rm "+pids_filepath)

def stop_attestation_client_process():    
    stop_process('attestation_extension')

    return 0, "Successfully stopped attestation proces"

# Exceptions
# If these exceptions are expected to be caught by the main method, they
# include an error_code field with an integer with which to exit from main

class AzureAttestationAgentForLinuxException(Exception):
    """
    Base exception class for all exceptions; as such, its error code is the
    basic error code traditionally returned in Linux: 1
    """
    error_code = 1
    def get_error_message(self, operation):
        """
        Return a descriptive error message based on this type of exception
        """
        return '{0} failed with exit code {1}'.format(operation,
                                                      self.error_code)


class ParameterMissingException(AzureAttestationAgentForLinuxException):
    """
    There is a missing parameter for the AzureAttestationLinuxAgent Extension
    """
    error_code = MissingorInvalidParameterErrorCode
    def get_error_message(self, operation):
        return '{0} failed due to a missing parameter: {1}'.format(operation,
                                                                   self)

if __name__ == '__main__' :
    main()
