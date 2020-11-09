#!/usr/bin/env python
#
# AzureMonitoringLinuxAgent Extension
#
# Copyright 2019 Microsoft Corporation
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
import datetime
import signal
import pwd
import grp
import re
import filecmp
import stat
import sys
import traceback
import time
import platform
import subprocess
import json
import base64
import inspect
import urllib
import urllib2
import shutil
import crypt
import xml.dom.minidom
import re
import hashlib
from distutils.version import LooseVersion
from hashlib import sha256
from shutil import copyfile

from threading import Thread
import telegraf_utils.telegraf_config_handler as telhandler
import metrics_ext_utils.metrics_constants as metrics_constants
import metrics_ext_utils.metrics_ext_handler as me_handler
import metrics_ext_utils.metrics_common_utils as metrics_utils

try:
    from Utils.WAAgentUtil import waagent
    import Utils.HandlerUtil as HUtil
except Exception as e:
    # These utils have checks around the use of them; this is not an exit case
    print('Importing utils failed with error: {0}'.format(e))

# Global Variables
PackagesDirectory = 'packages'
# TO BE CHANGED WITH EACH NEW RELEASE IF THE BUNDLE VERSION CHANGES
# TODO: Installer should automatically figure this out from the folder instead of requiring this update
BundleFileNameDeb = 'azure-mdsd_1.5.124-build.master.89_x86_64.deb'
BundleFileNameRpm = 'azure-mdsd_1.5.124-build.master.89_x86_64.rpm'
BundleFileName = ''
TelegrafBinName = 'telegraf'
InitialRetrySleepSeconds = 30
PackageManager = ''
MdsdCounterJsonPath = '/etc/mdsd.d/config-cache/metricCounters.json'

# Commands
OneAgentInstallCommand = ''
OneAgentUninstallCommand = ''
RestartOneAgentServiceCommand = ''
DisableOneAgentServiceCommand = ''

# Error codes
DPKGLockedErrorCode = 56
MissingorInvalidParameterErrorCode = 53
UnsupportedOperatingSystem = 51

# Configuration
HUtilObject = None
SettingsSequenceNumber = None
HandlerEnvironment = None
SettingsDict = None


# Change permission of log path - if we fail, that is not an exit case
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
    waagent_log_info('Azure Monitoring Agent for Linux started to handle.')

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
        elif re.match('^([-/]*)(metrics)', option):
            operation = 'Metrics'
        elif re.match('^([-/]*)(arc)', option):
            operation = 'Arc'
    except Exception as e:
        waagent_log_error(str(e))

    if operation is None:
        log_and_exit('Unknown', 1, 'No valid operation provided')

    # Set up for exit code and any error messages
    exit_code = 0
    message = '{0} succeeded'.format(operation)

    exit_code = check_disk_space_availability()
    if exit_code is not 0:
        message = '{0} failed due to low disk space'.format(operation)
        log_and_exit(operation, exit_code, message)   

    # Invoke operation
    try:
        global HUtilObject
        HUtilObject = parse_context(operation)
        exit_code, output = operations[operation]()

        # Exit code 1 indicates a general problem that doesn't have a more
        # specific error code; it often indicates a missing dependency
        if exit_code is 1 and operation == 'Install':
            message = 'Install failed with exit code 1. Please check that ' \
                      'dependencies are installed. For details, check logs ' \
                      'in /var/log/azure/Microsoft.Azure.Monitor' \
                      '.AzureMonitorLinuxAgent'
        elif exit_code is DPKGLockedErrorCode and operation == 'Install':
            message = 'Install failed with exit code {0} because the ' \
                      'package manager on the VM is currently locked: ' \
                      'please wait and try again'.format(DPKGLockedErrorCode)
        elif exit_code is not 0:
            message = '{0} failed with exit code {1} {2}'.format(operation,
                                                             exit_code, output)

    except AzureMonitorAgentForLinuxException as e:
        exit_code = e.error_code
        message = e.get_error_message(operation)
    except Exception as e:
        exit_code = 1
        message = '{0} failed with error: {1}\n' \
                  'Stacktrace: {2}'.format(operation, e,
                                           traceback.format_exc())
     
    # Finish up and log messages
    log_and_exit(operation, exit_code, message)   
        
def check_disk_space_availability():
    """
    Check if there is the required space on the machine.
    """
    try:
        if get_free_space_mb("/var") < 500 or get_free_space_mb("/etc") < 500 :
            # 52 is the exit code for missing dependency i.e. disk space
            # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
            return 52
        else:
            return 0
    except:
        print('Failed to check disk usage.')
        return 0
        

def get_free_space_mb(dirname):
    """
    Get the free space in MB in the directory path.
    """
    st = os.statvfs(dirname)
    return st.f_bavail * st.f_frsize / 1024 / 1024


def is_systemd():
    """
    Check if the system is using systemd
    """
    check_systemd = os.system("pidof systemd 1>/dev/null 2>&1")
    return check_systemd == 0

def install():
    """
    Ensure that this VM distro and version are supported.
    Install the Azure Monitor Linux Agent package, using retries.
    Note: install operation times out from WAAgent at 15 minutes, so do not
    wait longer.
    """
    find_package_manager("Install")
    exit_if_vm_not_supported('Install')

    public_settings, protected_settings = get_settings()
    
    package_directory = os.path.join(os.getcwd(), PackagesDirectory)
    bundle_path = os.path.join(package_directory, BundleFileName)
    os.chmod(bundle_path, 100)
    print (PackageManager, " and ", BundleFileName)
    OneAgentInstallCommand = "{0} -i {1}".format(PackageManager, bundle_path)        
    hutil_log_info('Running command "{0}"'.format(OneAgentInstallCommand))

    # Retry, since install can fail due to concurrent package operations
    exit_code, output = run_command_with_retries_output(OneAgentInstallCommand, retries = 15,
                                         retry_check = retry_if_dpkg_locked,
                                         final_check = final_check_if_dpkg_locked)    
    
    default_configs = {   
        "MDSD_LOG" : "/var/log",
        "MDSD_ROLE_PREFIX" : "/var/run/mdsd/default",
        "MDSD_SPOOL_DIRECTORY" : "/var/opt/microsoft/linuxmonagent",
        "MDSD_OPTIONS" : "\"-A -c /etc/mdsd.d/mdsd.xml -d -r $MDSD_ROLE_PREFIX -S $MDSD_SPOOL_DIRECTORY/eh -e $MDSD_LOG/mdsd.err -w $MDSD_LOG/mdsd.warn -o $MDSD_LOG/mdsd.info\"",
        "MCS_ENDPOINT" : "handler.control.monitor.azure.com",
        "AZURE_ENDPOINT" : "https://monitor.azure.com/",
        "ADD_REGION_TO_MCS_ENDPOINT" : "true",
        "ENABLE_MCS" : "false",
        "MONITORING_USE_GENEVA_CONFIG_SERVICE" : "false",
        #"OMS_TLD" : "int2.microsoftatlanta-int.com",
        #"customResourceId" : "/subscriptions/42e7aed6-f510-46a2-8597-a5fe2e15478b/resourcegroups/amcs-test/providers/Microsoft.OperationalInsights/workspaces/amcs-pretend-linuxVM",        
    }

    # Decide the mode
    if public_settings is not None and public_settings.get("GCS_AUTO_CONFIG") == "true":
        hutil_log_info("Detecting Auto-Config mode.")
        return 0, ""
    elif protected_settings is None or len(protected_settings) is 0:
        default_configs["ENABLE_MCS"] = "true"
    else:
        # look for LA protected settings
        for var in protected_settings.keys():
            if "_key" in var or "_id" in var:
                default_configs[var] = protected_settings.get(var)
        
        # check if required GCS params are available
        MONITORING_GCS_CERT_CERTFILE = None
        if protected_settings.has_key("certificate"):
            MONITORING_GCS_CERT_CERTFILE = base64.standard_b64decode(protected_settings.get("certificate"))

        MONITORING_GCS_CERT_KEYFILE = None
        if protected_settings.has_key("certificateKey"):
            MONITORING_GCS_CERT_KEYFILE = base64.standard_b64decode(protected_settings.get("certificateKey"))

        MONITORING_GCS_ENVIRONMENT = ""
        if protected_settings.has_key("monitoringGCSEnvironment"):
            MONITORING_GCS_ENVIRONMENT = protected_settings.get("monitoringGCSEnvironment")

        MONITORING_GCS_NAMESPACE = ""
        if protected_settings.has_key("namespace"):
            MONITORING_GCS_NAMESPACE = protected_settings.get("namespace")

        MONITORING_GCS_ACCOUNT = ""
        if protected_settings.has_key("monitoringGCSAccount"):
            MONITORING_GCS_ACCOUNT = protected_settings.get("monitoringGCSAccount")

        MONITORING_GCS_REGION = ""
        if protected_settings.has_key("monitoringGCSRegion"):
            MONITORING_GCS_REGION = protected_settings.get("monitoringGCSRegion")

        MONITORING_CONFIG_VERSION = ""
        if protected_settings.has_key("configVersion"):
            MONITORING_CONFIG_VERSION = protected_settings.get("configVersion")

        MONITORING_GCS_AUTH_ID_TYPE = ""
        if protected_settings.has_key("MONITORING_GCS_AUTH_ID_TYPE"):
            MONITORING_GCS_AUTH_ID_TYPE = protected_settings.get("MONITORING_GCS_AUTH_ID_TYPE")

        if ((MONITORING_GCS_CERT_CERTFILE is None or MONITORING_GCS_CERT_KEYFILE is None) and (MONITORING_GCS_AUTH_ID_TYPE is "")) or MONITORING_GCS_ENVIRONMENT is "" or MONITORING_GCS_NAMESPACE is "" or MONITORING_GCS_ACCOUNT is "" or MONITORING_GCS_REGION is "" or MONITORING_CONFIG_VERSION is "":
            waagent_log_error('Not all required GCS parameters are provided')
            raise ParameterMissingException
        else:
            # set the values for GCS
            default_configs["MONITORING_USE_GENEVA_CONFIG_SERVICE"] = "true"        
            default_configs["MONITORING_GCS_ENVIRONMENT"] = MONITORING_GCS_ENVIRONMENT
            default_configs["MONITORING_GCS_NAMESPACE"] = MONITORING_GCS_NAMESPACE
            default_configs["MONITORING_GCS_ACCOUNT"] = MONITORING_GCS_ACCOUNT
            default_configs["MONITORING_GCS_REGION"] = MONITORING_GCS_REGION
            default_configs["MONITORING_CONFIG_VERSION"] = MONITORING_CONFIG_VERSION

            # write the certificate and key to disk
            uid = pwd.getpwnam("syslog").pw_uid
            gid = grp.getgrnam("syslog").gr_gid
            
            if MONITORING_GCS_AUTH_ID_TYPE is not "":
                default_configs["MONITORING_GCS_AUTH_ID_TYPE"] = MONITORING_GCS_AUTH_ID_TYPE

            if MONITORING_GCS_CERT_CERTFILE is not None:
                default_configs["MONITORING_GCS_CERT_CERTFILE"] = "/etc/mdsd.d/gcscert.pem"
                fh = open("/etc/mdsd.d/gcscert.pem", "wb")
                fh.write(MONITORING_GCS_CERT_CERTFILE)
                fh.close()
                os.chown("/etc/mdsd.d/gcscert.pem", uid, gid)
                os.system('chmod {1} {0}'.format("/etc/mdsd.d/gcscert.pem", 400))  

            if MONITORING_GCS_CERT_KEYFILE is not None:
                default_configs["MONITORING_GCS_CERT_KEYFILE"] = "/etc/mdsd.d/gcskey.pem"
                fh = open("/etc/mdsd.d/gcskey.pem", "wb")
                fh.write(MONITORING_GCS_CERT_KEYFILE)
                fh.close()
                os.chown("/etc/mdsd.d/gcskey.pem", uid, gid)
                os.system('chmod {1} {0}'.format("/etc/mdsd.d/gcskey.pem", 400))  

    config_file = "/etc/default/mdsd"
    config_updated = False
    try:
        if os.path.isfile(config_file):
            data = []
            new_data = ""
            vars_set = set()
            with open(config_file, "r") as f:
                data = f.readlines()
                for line in data:
                    for var in default_configs.keys():
                        if var in line:
                            line = "export " + var + "=" + default_configs[var] + "\n"
                            vars_set.add(var)
                            break
                    new_data += line
            
            for var in default_configs.keys():
                if var not in vars_set:
                    new_data += "export " + var + "=" + default_configs[var] + "\n"

            with open("/etc/default/mdsd_temp", "w") as f:
                f.write(new_data)
                config_updated = True if len(new_data) > 0 else False 

            if not config_updated or not os.path.isfile("/etc/default/mdsd_temp"):
                log_and_exit("install",MissingorInvalidParameterErrorCode, "Error while updating MCS Environment Variables in /etc/default/mdsd")

            os.remove(config_file)
            os.rename("/etc/default/mdsd_temp", config_file)

            uid = pwd.getpwnam("syslog").pw_uid
            gid = grp.getgrnam("syslog").gr_gid
            os.chown(config_file, uid, gid)
            os.system('chmod {1} {0}'.format(config_file, 400))  

        else:
            log_and_exit("install", MissingorInvalidParameterErrorCode, "Could not find the file - /etc/default/mdsd" )        
    except:
        log_and_exit("install", MissingorInvalidParameterErrorCode, "Failed to add MCS Environment Variables in /etc/default/mdsd" )        
    return exit_code, output

def check_kill_process(pstring):
    for line in os.popen("ps ax | grep " + pstring + " | grep -v grep"):
        fields = line.split()
        pid = fields[0]
        os.kill(int(pid), signal.SIGKILL)

def uninstall():
    """
    Uninstall the Azure Monitor Linux Agent.
    This is a somewhat soft uninstall. It is not a purge.
    Note: uninstall operation times out from WAAgent at 5 minutes
    """
    find_package_manager("Uninstall")
    if PackageManager == "dpkg":
        OneAgentUninstallCommand = "dpkg -P azure-mdsd"
    elif PackageManager == "rpm":
        OneAgentUninstallCommand = "rpm -e azure-mdsd"
    else:
        log_and_exit(operation, UnsupportedOperatingSystem, "The OS has neither rpm nor dpkg" )
    hutil_log_info('Running command "{0}"'.format(OneAgentUninstallCommand))

    # Retry, since uninstall can fail due to concurrent package operations
    try:
        exit_code, output = run_command_with_retries_output(OneAgentUninstallCommand, retries = 4,
                                            retry_check = retry_if_dpkg_locked,
                                            final_check = final_check_if_dpkg_locked)
    except Exception as ex:
        exit_code = 1
        output = 'Uninstall failed with error: {0}\n' \
                'Stacktrace: {1}'.format(ex, traceback.format_exc())
    return exit_code, output

def enable():
    """
    Start the Azure Monitor Linux Agent Service
    This call will return non-zero or throw an exception if
    the settings provided are incomplete or incorrect.
    Note: enable operation times out from WAAgent at 5 minutes
    """
    exit_if_vm_not_supported('Enable')

    # Check if this is Arc VM and enable arc daemon if it is
    if metrics_utils.is_arc_installed():
        hutil_log_info("This VM is an Arc VM, Running the arc watcher daemon.")
        start_arc_process()

    if is_systemd():
        OneAgentEnableCommand = "systemctl start mdsd"
    else:
        hutil_log_info("The VM doesn't have systemctl. Using the init.d service to start mdsd.")
        OneAgentEnableCommand = "/etc/init.d/mdsd start"
    
    public_settings, protected_settings = get_settings()

    if public_settings is not None and public_settings.get("GCS_AUTO_CONFIG") == "true":
        OneAgentEnableCommand = "systemctl start mdsdmgr"
        if not is_systemd():
            hutil_log_info("The VM doesn't have systemctl. Using the init.d service to start mdsdmgr.")
            OneAgentEnableCommand = "/etc/init.d/mdsdmgr start"

    hutil_log_info('Handler initiating onboarding.')
    exit_code, output = run_command_and_log(OneAgentEnableCommand)

    if exit_code is 0:
        #start metrics process if enable is successful
        start_metrics_process()
        
    return exit_code, output

def disable():
    """
    Disable Azure Monitor Linux Agent process on the VM.
    Note: disable operation times out from WAAgent at 15 minutes
    """

    # disable arc daemon if it is running
    stop_arc_watcher()

    #stop the metrics process
    stop_metrics_process()

    #stop the Azure Monitor Linux Agent service
    if is_systemd():
        DisableOneAgentServiceCommand = "systemctl stop mdsd"
        
    else:
        DisableOneAgentServiceCommand = "/etc/init.d/mdsd stop"
        hutil_log_info("The VM doesn't have systemctl. Using the init.d service to stop mdsd.")
    
    exit_code, output = run_command_and_log(DisableOneAgentServiceCommand)
    return exit_code, output

def update():
    """
    Update the current installation of AzureMonitorLinuxAgent
    No logic to install the agent as agent -> install() will be called 
    with udpate because upgradeMode = "UpgradeWithInstall" set in HandlerManifest
    """
    
    return 0, ""

def stop_metrics_process():
    
    if telhandler.is_running(is_lad=False):
        #Stop the telegraf and ME services
        tel_out, tel_msg = telhandler.stop_telegraf_service(is_lad=False)
        if tel_out:
            HUtilObject.log(tel_msg)
        else:
            HUtilObject.error(tel_msg)
        
        #Delete the telegraf and ME services
        tel_rm_out, tel_rm_msg = telhandler.remove_telegraf_service()
        if tel_rm_out:
            HUtilObject.log(tel_rm_msg)
        else:
            HUtilObject.error(tel_rm_msg)
    
    if me_handler.is_running(is_lad=False):
        me_out, me_msg = me_handler.stop_metrics_service(is_lad=False)
        if me_out:
            HUtilObject.log(me_msg)
        else:
            HUtilObject.error(me_msg)

        me_rm_out, me_rm_msg = me_handler.remove_metrics_service(is_lad=False)
        if me_rm_out:
            HUtilObject.log(me_rm_msg)
        else:
            HUtilObject.error(me_rm_msg)

    pids_filepath = os.path.join(os.getcwd(),'amametrics.pid')

    # kill existing telemetry watcher
    if os.path.exists(pids_filepath):
        with open(pids_filepath, "r") as f:
            for pids in f.readlines():
                kill_cmd = "kill " + pids
                run_command_and_log(kill_cmd)
                run_command_and_log("rm "+pids_filepath)

def start_metrics_process():
    """
    Start telemetry process that performs periodic monitoring activities
    :return: None

    """
    stop_metrics_process()
    
    #start telemetry watcher
    oneagent_filepath = os.path.join(os.getcwd(),'agent.py')
    args = ['python', oneagent_filepath, '-metrics']
    log = open(os.path.join(os.getcwd(), 'daemon.log'), 'w')
    HUtilObject.log('start watcher process '+str(args))
    subprocess.Popen(args, stdout=log, stderr=log)

def metrics_watcher(hutil_error, hutil_log):
    """
    Watcher thread to monitor metric configuration changes and to take action on them
    """    
    
    # check every 30 seconds
    sleepTime =  30

    # sleep before starting the monitoring.
    time.sleep(sleepTime)
    last_crc = None
    me_msi_token_expiry_epoch = None

    while True:
        try:
            if os.path.isfile(MdsdCounterJsonPath):
                f = open(MdsdCounterJsonPath, "r")
                data = f.read()
                    
                if (data != ''):
                    json_data = json.loads(data)  
                    
                    if len(json_data) == 0:
                        last_crc = hashlib.sha256(data).hexdigest()                    
                        if telhandler.is_running(is_lad=False):
                            #Stop the telegraf and ME services
                            tel_out, tel_msg = telhandler.stop_telegraf_service(is_lad=False)
                            if tel_out:
                                HUtilObject.log(tel_msg)
                            else:
                                HUtilObject.error(tel_msg)

                            #Delete the telegraf and ME services
                            tel_rm_out, tel_rm_msg = telhandler.remove_telegraf_service()
                            if tel_rm_out:
                                HUtilObject.log(tel_rm_msg)
                            else:
                                HUtilObject.error(tel_rm_msg)

                        if me_handler.is_running(is_lad=False):
                            me_out, me_msg = me_handler.stop_metrics_service(is_lad=False)
                            if me_out:
                                HUtilObject.log(me_msg)
                            else:
                                HUtilObject.error(me_msg)

                            me_rm_out, me_rm_msg = me_handler.remove_metrics_service(is_lad=False)
                            if me_rm_out:
                                HUtilObject.log(me_rm_msg)
                            else:
                                HUtilObject.error(me_rm_msg)
                    else:
                        crc = hashlib.sha256(data).hexdigest()                    
                        generate_token = False
                        me_token_path = os.path.join(os.getcwd(), "/config/metrics_configs/AuthToken-MSI.json")

                        if me_msi_token_expiry_epoch is None or me_msi_token_expiry_epoch == "":
                            if os.path.isfile(me_token_path):
                                with open(me_token_path, "r") as f:
                                    authtoken_content = f.read()
                                    if authtoken_content and "expires_on" in authtoken_content:
                                        me_msi_token_expiry_epoch = authtoken_content["expires_on"]
                                    else:
                                        generate_token = True
                            else:
                                generate_token = True

                        if me_msi_token_expiry_epoch:                
                            currentTime = datetime.datetime.now()
                            token_expiry_time = datetime.datetime.fromtimestamp(int(me_msi_token_expiry_epoch))
                            if token_expiry_time - currentTime < datetime.timedelta(minutes=30):
                                # The MSI Token will expire within 30 minutes. We need to refresh the token
                                generate_token = True

                        if generate_token:
                            generate_token = False
                            msi_token_generated, me_msi_token_expiry_epoch, log_messages = me_handler.generate_MSI_token()
                            if msi_token_generated:
                                hutil_log("Successfully refreshed metrics-extension MSI Auth token.")
                            else:
                                hutil_error(log_messages)

                        if(crc != last_crc):
                            hutil_log("Start processing metric configuration")
                            hutil_log(data)

                            telegraf_config, telegraf_namespaces = telhandler.handle_config(
                                json_data, 
                                "udp://127.0.0.1:" + metrics_constants.ama_metrics_extension_udp_port, 
                                "unix:///var/run/mdsd/default_influx.socket",
                                is_lad=False)

                            me_handler.setup_me(is_lad=False)

                            start_telegraf_out, log_messages = telhandler.start_telegraf(is_lad=False)
                            if start_telegraf_out:
                                hutil_log("Successfully started metrics-sourcer.")
                            else:
                                hutil_error(log_messages)


                            start_metrics_out, log_messages = me_handler.start_metrics(is_lad=False)
                            if start_metrics_out:
                                hutil_log("Successfully started metrics-extension.")
                            else:
                                hutil_error(log_messages)

                            last_crc = crc

                        telegraf_restart_retries = 0
                        me_restart_retries = 0
                        max_restart_retries = 10

                        # Check if telegraf is running, if not, then restart
                        if not telhandler.is_running(is_lad=False):
                            if telegraf_restart_retries < max_restart_retries:
                                telegraf_restart_retries += 1
                                hutil_log("Telegraf binary process is not running. Restarting telegraf now. Retry count - {0}".format(telegraf_restart_retries))
                                tel_out, tel_msg = telhandler.stop_telegraf_service(is_lad=False)
                                if tel_out:
                                    hutil_log(tel_msg)
                                else:
                                    hutil_error(tel_msg)
                                start_telegraf_out, log_messages = telhandler.start_telegraf(is_lad=False)
                                if start_telegraf_out:
                                    hutil_log("Successfully started metrics-sourcer.")
                                else:
                                    hutil_error(log_messages)
                            else:
                                hutil_error("Telegraf binary process is not running. Failed to restart after {0} retries. Please check telegraf.log".format(max_restart_retries))
                        else:
                            telegraf_restart_retries = 0

                        # Check if ME is running, if not, then restart
                        if not me_handler.is_running(is_lad=False):
                            if me_restart_retries < max_restart_retries:
                                me_restart_retries += 1
                                hutil_log("MetricsExtension binary process is not running. Restarting MetricsExtension now. Retry count - {0}".format(me_restart_retries))
                                me_out, me_msg = me_handler.stop_metrics_service(is_lad=False)
                                if me_out:
                                    hutil_log(me_msg)
                                else:
                                    hutil_error(me_msg)                  
                                start_metrics_out, log_messages = me_handler.start_metrics(is_lad=False)

                                if start_metrics_out:
                                    hutil_log("Successfully started metrics-extension.")
                                else:
                                    hutil_error(log_messages)
                            else:
                                hutil_error("MetricsExtension binary process is not running. Failed to restart after {0} retries. Please check /var/log/syslog for ME logs".format(max_restart_retries))
                        else:
                            me_restart_retries = 0   
        
        except IOError as e:
            hutil_error('I/O error in monitoring metrics. Exception={0}'.format(e))

        except Exception as e:
            hutil_error('Error in monitoring metrics. Exception={0}'.format(e))

        finally:
            time.sleep(sleepTime)

def metrics():
    """
    Take care of setting up telegraf and ME for metrics if configuration is present
    """    
    pids_filepath = os.path.join(os.getcwd(), 'amametrics.pid')
    py_pid = os.getpid()
    with open(pids_filepath, 'w') as f:
        f.write(str(py_pid) + '\n')

    watcher_thread = Thread(target = metrics_watcher, args = [HUtilObject.error, HUtilObject.log])
    watcher_thread.start()
    watcher_thread.join()

    return 0, ""


def start_arc_process():
    """
    Start arc process that performs periodic monitoring activities
    :return: None

    """
    hutil_log_info("stopping previously running arc process")
    stop_arc_watcher()
    hutil_log_info("starting arc process")
    
    #start telemetry watcher
    oneagent_filepath = os.path.join(os.getcwd(),'agent.py')
    args = ['python', oneagent_filepath, '-arc']
    log = open(os.path.join(os.getcwd(), 'daemon.log'), 'w')
    HUtilObject.log('start watcher process '+str(args))
    subprocess.Popen(args, stdout=log, stderr=log)

def start_arc_watcher():
    """
    Take care of starting arc_watcher daemon if the VM has arc running
    """    
    hutil_log_info("Starting the watcher")
    print("Starting the watcher")
    pids_filepath = os.path.join(os.getcwd(), 'amaarc.pid')
    py_pid = os.getpid()
    print("pid ", py_pid)
    with open(pids_filepath, 'w') as f:
        f.write(str(py_pid) + '\n')
    hutil_log_info("Written all the pids")
    print("Written all the pids")
    watcher_thread = Thread(target = arc_watcher, args = [HUtilObject.error, HUtilObject.log])
    watcher_thread.start()
    watcher_thread.join()

    return 0, ""

# Dictionary of operations strings to methods
operations = {'Disable' : disable,
              'Uninstall' : uninstall,
              'Install' : install,
              'Enable' : enable,
              'Update' : update,
              'Metrics' : metrics,
              'Arc' : start_arc_watcher,
}


def stop_arc_watcher():
    """
    Take care of stopping arc_watcher daemon if the VM has arc running
    """    
    pids_filepath = os.path.join(os.getcwd(),'amaarc.pid')

    # kill existing telemetry watcher
    if os.path.exists(pids_filepath):
        with open(pids_filepath, "r") as f:
            for pids in f.readlines():
                proc = subprocess.Popen(["ps -o cmd= {0}".format(pids)], stdout=subprocess.PIPE, shell=True)
                output = proc.communicate()[0]
                if "arc" in output:
                    kill_cmd = "kill " + pids 
                    run_command_and_log(kill_cmd)
        
        # Delete the file after to avoid clutter
        os.remove(pids_filepath)

def arc_watcher(hutil_error, hutil_log):
    """
    This is needed to override mdsd's syslog permissions restriction which prevents mdsd 
    from reading temporary key files that are needed to make https calls to get an MSI token for arc during onboarding to download amcs config
    This method spins up a process that will continuously keep refreshing that particular file path with valid keys
    So that whenever mdsd needs to refresh it's MSI token, it is able to find correct keys there to make the https calls
    """
    # check every 25 seconds
    sleepTime =  25

    # sleep before starting the monitoring.
    time.sleep(sleepTime)

    while True:
        try:
            arc_token_mdsd_dir = "/etc/mdsd.d/arc_tokens/"
            if not os.path.exists(arc_token_mdsd_dir):
                os.makedirs(arc_token_mdsd_dir)
            else:
                # delete the existing keys as they might not be valid anymore
                for filename in os.listdir(arc_token_mdsd_dir):
                    filepath = arc_token_mdsd_dir + filename
                    os.remove(filepath)

            arc_endpoint = metrics_utils.get_arc_endpoint()
            try:
                msiauthurl = arc_endpoint + "/metadata/identity/oauth2/token?api-version=2019-11-01&resource=https://monitor.azure.com/"
                req = urllib2.Request(msiauthurl, headers={'Metadata':'true'})
                res = urllib2.urlopen(req)
            except:
                # The above request is expected to fail and add a key to the path - 
                authkey_dir = "/var/opt/azcmagent/tokens/"
                if not os.path.exists(authkey_dir):
                    raise Exception("Unable to find the auth key file at {0} returned from the arc msi auth request.".format(authkey_dir))
                # Copy the tokens to mdsd accessible dir
                for filename in os.listdir(authkey_dir):
                    filepath = authkey_dir + filename
                    print filepath
                    shutil.copy(filepath, arc_token_mdsd_dir)
                
                # Change the ownership of the mdsd arc token dir to be accessible by syslog (since mdsd runs as syslog user)
                os.system("chown -R syslog:syslog {0}".format(arc_token_mdsd_dir))

        except Exception as e:
            hutil_error('Error in arc watcher process while copying token for arc MSI auth queries. Exception={0}'.format(e))

        finally:
            time.sleep(sleepTime)

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


def find_package_manager(operation):
    """
    Checks if the dist is debian based or centos based and assigns the package manager accordingly
    """
    global PackageManager
    global BundleFileName
    dist, ver = find_vm_distro(operation)

    dpkg_set = set(["debian", "ubuntu"])
    rpm_set = set(["oracle", "redhat", "centos", "red hat", "suse"])
    for dpkg_dist in dpkg_set:
        if dist.lower().startswith(dpkg_dist):
            PackageManager = "dpkg"
            BundleFileName = BundleFileNameDeb
            break

    for rpm_dist in rpm_set:
        if dist.lower().startswith(rpm_dist):
            PackageManager = "rpm"
            BundleFileName = BundleFileNameRpm
            break

    if PackageManager == "":
        log_and_exit(operation, UnsupportedOperatingSystem, "The OS has neither rpm nor dpkg" )
    
    
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
    Checks if the VM this extension is running on is supported by AzureMonitorAgent
    Returns for platform.linux_distribution() vary widely in format, such as
    '7.3.1611' returned for a VM with CentOS 7, so the first provided
    digits must match
    The supported distros of the AzureMonitorLinuxAgent are allowed to utilize
    this VM extension. All other distros will get error code 51
    """
    supported_dists = {'redhat' : ['6', '7'], # CentOS
                       'centos' : ['6', '7'], # CentOS
                       'red hat' : ['6', '7'], # Oracle, RHEL
                       'oracle' : ['6', '7'], # Oracle
                       'debian' : ['8', '9'], # Debian
                       'ubuntu' : ['14.04', '16.04', '18.04'], # Ubuntu
                       'suse' : ['12'], 'sles' : ['15'] # SLES
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
    Check if this VM distro and version are supported by the AzureMonitorLinuxAgent.
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

def run_command_with_retries_output(cmd, retries, retry_check, final_check = None,
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
    If the retry_check retuns True for retry_verbosely, we will try cmd with
    the standard -v verbose flag added
    """
    try_count = 0
    sleep_time = initial_sleep_time
    run_cmd = cmd
    run_verbosely = False

    while try_count <= retries:
        if run_verbosely:
            run_cmd = cmd + ' -v'
        exit_code, output = run_command_and_log(run_cmd, check_error, log_cmd)
        should_retry, retry_message, run_verbosely = retry_check(exit_code,
                                                                 output)
        if not should_retry:
            break
        try_count += 1
        hutil_log_info(retry_message)
        time.sleep(sleep_time)
        sleep_time *= sleep_increase_factor

    if final_check is not None:
        exit_code = final_check(exit_code, output)

    return exit_code, output


def is_dpkg_locked(exit_code, output):
    """
    If dpkg is locked, the output will contain a message similar to 'dpkg
    status database is locked by another process'
    """
    if exit_code is not 0:
        dpkg_locked_search = r'^.*dpkg.+lock.*$'
        dpkg_locked_re = re.compile(dpkg_locked_search, re.M)
        if dpkg_locked_re.search(output):
            return True
    return False


def retry_if_dpkg_locked(exit_code, output):
    """
    Some commands fail because the package manager is locked (apt-get/dpkg
    only); this will allow retries on failing commands.
    """
    retry_verbosely = False
    dpkg_locked = is_dpkg_locked(exit_code, output)
    apt_get_exit_code, apt_get_output = run_get_output('which apt-get',
                                                       chk_err = False,
                                                       log_cmd = False)
    if dpkg_locked:
        return True, 'Retrying command because package manager is locked.', \
               retry_verbosely
    else:
        return False, '', False


def final_check_if_dpkg_locked(exit_code, output):
    """
    If dpkg is still locked after the retries, we want to return a specific
    error code
    """
    dpkg_locked = is_dpkg_locked(exit_code, output)
    if dpkg_locked:
        exit_code = DPKGLockedErrorCode
    return exit_code


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
    else:
        SettingsDict = {}
        handler_env = get_handler_env()
        try:
            config_dir = str(handler_env['handlerEnvironment']['configFolder'])
        except:
            config_dir = os.path.join(os.getcwd(), 'config')

        seq_no = get_latest_seq_no()
        settings_path = os.path.join(config_dir, '{0}.settings'.format(seq_no))
        try:
            with open(settings_path, 'r') as settings_file:
                settings_txt = settings_file.read()
            settings = json.loads(settings_txt)
            h_settings = settings['runtimeSettings'][0]['handlerSettings']
            public_settings = h_settings['publicSettings']
            SettingsDict['public_settings'] = public_settings
        except:
            hutil_log_error('Unable to load handler settings from ' \
                            '{0}'.format(settings_path))

        if (h_settings.has_key('protectedSettings')
                and h_settings.has_key('protectedSettingsCertThumbprint')
                and h_settings['protectedSettings'] is not None
                and h_settings['protectedSettingsCertThumbprint'] is not None):
            encoded_settings = h_settings['protectedSettings']
            settings_thumbprint = h_settings['protectedSettingsCertThumbprint']
            encoded_cert_path = os.path.join('/var/lib/waagent',
                                             '{0}.crt'.format(
                                                       settings_thumbprint))
            encoded_key_path = os.path.join('/var/lib/waagent',
                                            '{0}.prv'.format(
                                                      settings_thumbprint))
            decoded_settings = base64.standard_b64decode(encoded_settings)
            decrypt_cmd = 'openssl smime -inform DER -decrypt -recip {0} ' \
                          '-inkey {1}'.format(encoded_cert_path,
                                              encoded_key_path)

            try:
                session = subprocess.Popen([decrypt_cmd], shell = True,
                                           stdin = subprocess.PIPE,
                                           stderr = subprocess.STDOUT,
                                           stdout = subprocess.PIPE)
                output = session.communicate(decoded_settings)
            except OSError:
                pass
            protected_settings_str = output[0]

            if protected_settings_str is None:
                log_and_exit('Enable', 1, 'Failed decrypting ' \
                                          'protectedSettings')
            protected_settings = ''
            try:
                protected_settings = json.loads(protected_settings_str)
            except:
                hutil_log_error('JSON exception decoding protected settings')
            SettingsDict['protected_settings'] = protected_settings

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
            "name" : "Microsoft.Azure.Monitor.AzureMonitorLinuxAgent",
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
    Set and retrieve the contents of HandlerEnvironment.json as JSON
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
    Determine the latest operation settings number to use
    """
    global SettingsSequenceNumber
    if SettingsSequenceNumber is None:
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
        SettingsSequenceNumber = latest_seq_no

    return SettingsSequenceNumber


def run_get_output(cmd, chk_err = False, log_cmd = True):
    """
    Mimic waagent mothod RunGetOutput in case waagent is not available
    Run shell command and return exit code and output
    """
    if 'Utils.WAAgentUtil' in sys.modules:
        # WALinuxAgent-2.0.14 allows only 2 parameters for RunGetOutput
        # If checking the number of parameters fails, pass 2
        try:
            sig = inspect.signature(waagent.RunGetOutput)
            params = sig.parameters
            waagent_params = len(params)
        except:
            try:
                spec = inspect.getargspec(waagent.RunGetOutput)
                params = spec.args
                waagent_params = len(params)
            except:
                waagent_params = 2
        if waagent_params >= 3:
            exit_code, output = waagent.RunGetOutput(cmd, chk_err, log_cmd)
        else:
            exit_code, output = waagent.RunGetOutput(cmd, chk_err)
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


# Exceptions
# If these exceptions are expected to be caught by the main method, they
# include an error_code field with an integer with which to exit from main

class AzureMonitorAgentForLinuxException(Exception):
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


class ParameterMissingException(AzureMonitorAgentForLinuxException):
    """
    There is a missing parameter for the AzureMonitorLinuxAgent Extension
    """
    error_code = MissingorInvalidParameterErrorCode
    def get_error_message(self, operation):
        return '{0} failed due to a missing parameter: {1}'.format(operation,
                                                                   self)

if __name__ == '__main__' :
    main()
