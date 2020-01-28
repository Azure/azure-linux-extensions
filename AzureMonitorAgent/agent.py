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
import urllib
import urllib2
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
PackagesDirectory = 'packages'
# TO BE CHANGED WITH EACH NEW RELEASE IF THE BUNDLE VERSION CHANGES
BundleFileNameDeb = 'azure-mdsd_1.5.119-build.develop.805_x86_64.deb'
BundleFileNameRpm = 'azure-mdsd_1.5.119-build.develop.805_x86_64.rpm'
BundleFileName = ''
InitialRetrySleepSeconds = 30
PackageManager = ''

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
    
    # if public_settings is None:
    #     raise ParameterMissingException('Public configuration must be ' \
    #                                     'provided')
    #public_settings.get('workspaceId')
    #protected_settings.get('workspaceKey')
    
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
        "MCS_ENDPOINT" : "amcs.control.monitor.azure.com",
        "AZURE_ENDPOINT" : "https://management.azure.com/",
        "ADD_REGION_TO_MCS_ENDPOINT" : "true",
        "ENABLE_MCS" : "false",
        "MONITORING_USE_GENEVA_CONFIG_SERVICE" : "false",
        #"OMS_TLD" : "int2.microsoftatlanta-int.com",
        #"customResourceId" : "/subscriptions/42e7aed6-f510-46a2-8597-a5fe2e15478b/resourcegroups/amcs-test/providers/Microsoft.OperationalInsights/workspaces/amcs-pretend-linuxVM",        
    }

    # decide the mode
    if protected_settings is None:
        default_configs["ENABLE_MCS"] = "true"
    else:
        # look for LA protected settings
        for var in protected_settings.keys():
            if "_key" in var:
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

        if MONITORING_GCS_CERT_CERTFILE is None or MONITORING_GCS_CERT_KEYFILE is None or MONITORING_GCS_ENVIRONMENT is "" or MONITORING_GCS_NAMESPACE is "" or MONITORING_GCS_ACCOUNT is "" or MONITORING_GCS_REGION is "" or MONITORING_CONFIG_VERSION is "":
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
            default_configs["MONITORING_GCS_CERT_CERTFILE"] = "/etc/mdsd.d/gcscert.pem"
            default_configs["MONITORING_GCS_CERT_KEYFILE"] = "/etc/mdsd.d/gcskey.pem"

            # write the certificate and key to disk
            uid = pwd.getpwnam("syslog").pw_uid
            gid = grp.getgrnam("syslog").gr_gid
            
            fh = open("/etc/mdsd.d/gcscert.pem", "wb")
            fh.write(MONITORING_GCS_CERT_CERTFILE)
            fh.close()
            os.chown("/etc/mdsd.d/gcscert.pem", uid, gid)
            os.system('chmod {1} {0}'.format("/etc/mdsd.d/gcscert.pem", 400))  

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
            export_dict = {}
            vars_set = set()
            with open(config_file, "r") as f:
                data = f.readlines()
                for line in data:
                    for var in default_configs.keys():
                        export_dict[var] = "export " + var + "=" + default_configs[var] + "\n"
                        if var in line:
                            line = export_dict[var]
                            vars_set.add(var)
                            break
                    new_data += line
            
            for var in default_configs.keys():
                if var not in vars_set:
                    new_data += export_dict[var]

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

    OneAgentEnableCommand = "systemctl start mdsd"

    hutil_log_info('Handler initiating onboarding.')
    exit_code, output = run_command_and_log(OneAgentEnableCommand)
    return exit_code, output

def disable():
    """
    Disable Azure Monitor Linux Agent process on the VM.
    Note: disable operation times out from WAAgent at 15 minutes
    """
    #stop the Azure Monitor Linux Agent service
    DisableOneAgentServiceCommand = "systemctl stop mdsd"

    exit_code, output = run_command_and_log(DisableOneAgentServiceCommand)
    return exit_code, output

def update():
    """
    Update the current installation of AzureMonitorLinuxAgent
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


def find_package_manager(operation):
    """
    Checks if the dist is debian based or centos based and assigns the package manager accordingly
    """
    global PackageManager
    global BundleFileName
    dist, ver = find_vm_distro(operation)

    dpkg_set = {"oracle", "debian", "ubuntu", "suse"}
    rpm_set = {"redhat", "centos", "red hat"}
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
