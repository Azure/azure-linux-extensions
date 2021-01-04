#!/usr/bin/env python
#
# OmsAgentForLinux Extension
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

from __future__ import print_function
import sys

# future imports have no effect on python 3 (verified in official docs)
# importing from source causes import errors on python 3, lets skip import
if sys.version_info[0] < 3:
    from future import standard_library
    standard_library.install_aliases()
    from builtins import str

import os
import os.path
import signal
import pwd
import grp
import re
import traceback
import time
import platform
import subprocess
import json
import base64
import inspect
import urllib.request, urllib.parse, urllib.error
import watcherutil
import shutil

from threading import Thread

try:
    from Utils.WAAgentUtil import waagent
    import Utils.HandlerUtil as HUtil
except Exception as e:
    # These utils have checks around the use of them; this is not an exit case
    print('Importing utils failed with error: {0}'.format(e))

# This monkey patch duplicates the one made in the waagent import above.
# It is necessary because on 2.6, the waagent monkey patch appears to be overridden
# by the python-future subprocess.check_output backport.
if sys.version_info < (2,7):
    def check_output(*popenargs, **kwargs):
        r"""Backport from subprocess module from python 2.7"""
        if 'stdout' in kwargs:
            raise ValueError('stdout argument not allowed, it will be overridden.')
        process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            raise subprocess.CalledProcessError(retcode, cmd, output=output)
        return output

    # Exception classes used by this module.
    class CalledProcessError(Exception):
        def __init__(self, returncode, cmd, output=None):
            self.returncode = returncode
            self.cmd = cmd
            self.output = output

        def __str__(self):
            return "Command '%s' returned non-zero exit status %d" % (self.cmd, self.returncode)

    subprocess.check_output = check_output
    subprocess.CalledProcessError = CalledProcessError

# Global Variables
ProceedOnSigningVerificationFailure = True
PackagesDirectory = 'packages'
keysDirectory = 'keys'
BundleFileName = 'omsagent-1.13.11-0.universal.x64.sh'
GUIDRegex = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
GUIDOnlyRegex = r'^' + GUIDRegex + '$'
SCOMCertIssuerRegex = r'^[\s]*Issuer:[\s]*CN=SCX-Certificate/title=SCX' + GUIDRegex + ', DC=.*$'
SCOMPort = 1270
PostOnboardingSleepSeconds = 5
InitialRetrySleepSeconds = 30
IsUpgrade = False

# Paths
OMSAdminPath = '/opt/microsoft/omsagent/bin/omsadmin.sh'
OMSAgentServiceScript = '/opt/microsoft/omsagent/bin/service_control'
OMIConfigEditorPath = '/opt/omi/bin/omiconfigeditor'
OMIServerConfPath = '/etc/opt/omi/conf/omiserver.conf'
EtcOMSAgentPath = '/etc/opt/microsoft/omsagent/'
VarOMSAgentPath = '/var/opt/microsoft/omsagent/'
SCOMCertPath = '/etc/opt/microsoft/scx/ssl/scx.pem'
ExtensionStateSubdirectory = 'state'

# Commands
# Always use upgrade - will handle install if scx, omi are not installed or upgrade if they are.
InstallCommandTemplate = '{0} --upgrade'
UninstallCommandTemplate = '{0} --remove'
WorkspaceCheckCommand = '{0} -l'.format(OMSAdminPath)
OnboardCommandWithOptionalParams = '{0} -w {1} -s {2} {3}'

RestartOMSAgentServiceCommand = '{0} restart'.format(OMSAgentServiceScript)
DisableOMSAgentServiceCommand = '{0} disable'.format(OMSAgentServiceScript)

# Cloud Environments
PublicCloudName     = "AzurePublicCloud"
FairfaxCloudName    = "AzureUSGovernmentCloud"
MooncakeCloudName   = "AzureChinaCloud"
USNatCloudName      = "USNat" # EX
USSecCloudName      = "USSec" # RX
DefaultCloudName    = PublicCloudName # Fallback

CloudDomainMap = {
    PublicCloudName:   "opinsights.azure.com",
    FairfaxCloudName:  "opinsights.azure.us",
    MooncakeCloudName: "opinsights.azure.cn",
    USNatCloudName:    "opinsights.azure.eaglex.ic.gov",
    USSecCloudName:    "opinsights.azure.microsoft.scloud"
}

# Error codes
DPKGLockedErrorCode = 55 #56, temporary as it excludes from SLA
InstallErrorCurlNotInstalled = 55 #64, temporary as it excludes from SLA
EnableErrorOMSReturned403 = 5
EnableErrorOMSReturnedNon200 = 6
EnableErrorResolvingHost = 7
EnableErrorOnboarding = 8
EnableCalledBeforeSuccessfulInstall = 52 # since install is a missing dependency
UnsupportedOpenSSL = 55 #60, temporary as it excludes from SLA
# OneClick error codes
OneClickErrorCode = 40
ManagedIdentityExtMissingErrorCode = 41
ManagedIdentityExtErrorCode = 42
MetadataAPIErrorCode = 43
OMSServiceOneClickErrorCode = 44
MissingorInvalidParameterErrorCode = 11
UnwantedMultipleConnectionsErrorCode = 10
CannotConnectToOMSErrorCode = 55
UnsupportedOperatingSystem = 51

# Configuration
HUtilObject = None
SettingsSequenceNumber = None
HandlerEnvironment = None
SettingsDict = None

# OneClick Constants
ManagedIdentityExtListeningURLPath = '/var/lib/waagent/ManagedIdentity-Settings'
GUIDRegex = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
OAuthTokenResource = 'https://management.core.windows.net/'
OMSServiceValidationEndpoint = 'https://global.oms.opinsights.azure.com/ManagedIdentityService.svc/Validate'
AutoManagedWorkspaceCreationSleepSeconds = 20

# agent permissions
AgentUser='omsagent'
AgentGroup='omiusers'

# Change permission of log path - if we fail, that is not an exit case
try:
    ext_log_path = '/var/log/azure/'
    if os.path.exists(ext_log_path):
        os.chmod(ext_log_path, 700)
except:
    pass

"""
What need to be packaged to make the signing work:
    keys
        dscgpgkey.asc
        msgpgkey.asc
    packages
        omsagent-*.universal.x64.asc
        omsagent-*.universal.x64.sha256sums
"""
def verifyShellBundleSigningAndChecksum():
    cert_directory = os.path.join(os.getcwd(), PackagesDirectory)
    keys_directory = os.path.join(os.getcwd(), keysDirectory)
    # import GPG key
    dscGPGKeyFilePath = os.path.join(keys_directory, 'dscgpgkey.asc')
    if not os.path.isfile(dscGPGKeyFilePath):
        raise Exception("Unable to find the dscgpgkey.asc file at " + dscGPGKeyFilePath)

    importGPGKeyCommand = "sh ImportGPGkey.sh " + dscGPGKeyFilePath
    exit_code, output = run_command_with_retries_output(importGPGKeyCommand, retries = 0, retry_check = retry_skip, check_error = False)

    # Check that we can find the keyring file
    keyringFilePath = os.path.join(keys_directory, 'keyring.gpg')
    if not os.path.isfile(keyringFilePath):
        raise Exception("Unable to find the Extension keyring file at " + keyringFilePath)

    # Check that we can find the asc file
    bundleFileName, file_ext = os.path.splitext(BundleFileName)
    ascFilePath = os.path.join(cert_directory, bundleFileName + ".asc")
    if not os.path.isfile(ascFilePath):
        raise Exception("Unable to find the OMS shell bundle asc file at " + ascFilePath)

    # check that we can find the SHA256 sums file
    sha256SumsFilePath = os.path.join(cert_directory, bundleFileName + ".sha256sums")
    if not os.path.isfile(sha256SumsFilePath):
        raise Exception("Unable to find the OMS shell bundle SHA256 sums file at " + sha256SumsFilePath)

    # Verify the SHA256 sums file with the keyring and asc files
    verifySha256SumsCommand = "HOME=" + keysDirectory + " gpg --no-default-keyring --keyring " + keyringFilePath + " --verify " + ascFilePath  + " " + sha256SumsFilePath
    exit_code, output = run_command_with_retries_output(verifySha256SumsCommand, retries = 0, retry_check = retry_skip, check_error = False)
    if exit_code != 0:
        raise Exception("Failed to verify SHA256 sums file at " + sha256SumsFilePath)

    # Perform SHA256 sums to verify shell bundle
    hutil_log_info("Perform SHA256 sums to verify shell bundle")
    performSha256SumsCommand = "cd %s; sha256sum -c %s" % (cert_directory, sha256SumsFilePath)
    exit_code, output = run_command_with_retries_output(performSha256SumsCommand, retries = 0, retry_check = retry_skip, check_error = False)
    if exit_code != 0:
        raise Exception("Failed to verify shell bundle with the SHA256 sums file at " + sha256SumsFilePath)

def main():
    """
    Main method
    Parse out operation from argument, invoke the operation, and finish.
    """
    init_waagent_logger()
    waagent_log_info('OmsAgentForLinux started to handle.')
    global IsUpgrade

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
            IsUpgrade = True
        elif re.match('^([-/]*)(telemetry)', option):
            operation = 'Telemetry'
    except Exception as e:
        waagent_log_error(str(e))

    if operation is None:
        log_and_exit('Unknown', 1, 'No valid operation provided')

    # Set up for exit code and any error messages
    exit_code = 0
    message = '{0} succeeded'.format(operation)

    # Clean status file to mitigate diskspace issues on small VMs
    status_files = [
            "/var/opt/microsoft/omsconfig/status/dscperformconsistency",
            "/var/opt/microsoft/omsconfig/status/dscperforminventory",
            "/var/opt/microsoft/omsconfig/status/dscsetlcm",
            "/var/opt/microsoft/omsconfig/status/omsconfighost"
        ]
    for sf in status_files:
        if os.path.isfile(sf):
            if sf.startswith("/var/opt/microsoft/omsconfig/status"):
                try:
                    os.remove(sf)
                except Exception as e:
                    hutil_log_info('Error removing telemetry status file before installation: {0}'.format(sf))
                    hutil_log_info('Exception info: {0}'.format(traceback.format_exc()))

    exit_code = check_disk_space_availability()
    if exit_code is not 0:
        message = '{0} failed due to low disk space'.format(operation)
        log_and_exit(operation, exit_code, message)

    # Invoke operation
    try:
        global HUtilObject
        HUtilObject = parse_context(operation)

        # Verify shell bundle signing
        try:
            hutil_log_info("Start signing verification")
            verifyShellBundleSigningAndChecksum()
            hutil_log_info("ShellBundle signing verification succeeded")
        except Exception as ex:
            errmsg = "ShellBundle signing verification failed with '%s'" % ex.message
            if ProceedOnSigningVerificationFailure:
                hutil_log_error(errmsg)
            else:
                log_and_exit(operation, errmsg)
        
        # invoke operation
        exit_code, output = operations[operation]()

        # Exit code 1 indicates a general problem that doesn't have a more
        # specific error code; it often indicates a missing dependency
        if exit_code is 1 and operation == 'Install':
            message = 'Install failed with exit code 1. Please check that ' \
                      'dependencies are installed. For details, check logs ' \
                      'in /var/log/azure/Microsoft.EnterpriseCloud.' \
                      'Monitoring.OmsAgentForLinux'
        elif exit_code is 127 and operation == 'Install':
            # happens if shell bundle couldn't be extracted due to low space or missing dependency
            exit_code = 52 # since it is a missing dependency
            message = 'Install failed with exit code 127. Please check that ' \
                      'dependencies are installed. For details, check logs ' \
                      'in /var/log/azure/Microsoft.EnterpriseCloud.' \
                      'Monitoring.OmsAgentForLinux'
        elif exit_code is DPKGLockedErrorCode and operation == 'Install':
            message = 'Install failed with exit code {0} because the ' \
                      'package manager on the VM is currently locked: ' \
                      'please wait and try again'.format(DPKGLockedErrorCode)
        elif exit_code is not 0:
            message = '{0} failed with exit code {1} {2}'.format(operation,
                                                             exit_code, output)
    except OmsAgentForLinuxException as e:
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
        if get_free_space_mb("/var") < 500 or get_free_space_mb("/etc") < 500 or get_free_space_mb("/opt") < 500:
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
    return (st.f_bavail * st.f_frsize) // (1024 * 1024)

def stop_telemetry_process():
    pids_filepath = os.path.join(os.getcwd(),'omstelemetry.pid')

    # kill existing telemetry watcher
    if os.path.exists(pids_filepath):
        with open(pids_filepath, "r") as f:
            for pids in f.readlines():
                kill_cmd = "kill " + pids
                run_command_and_log(kill_cmd)
                run_command_and_log("rm "+pids_filepath)

def start_telemetry_process():
    """
    Start telemetry process that performs periodic monitoring activities
    :return: None

    """
    stop_telemetry_process()

    #start telemetry watcher
    omsagent_filepath = os.path.join(os.getcwd(),'omsagent.py')
    args = ['python{0}'.format(sys.version_info[0]), omsagent_filepath, '-telemetry']
    log = open(os.path.join(os.getcwd(), 'daemon.log'), 'w')
    hutil_log_info('start watcher process '+str(args))
    subprocess.Popen(args, stdout=log, stderr=log)

def telemetry():
    pids_filepath = os.path.join(os.getcwd(), 'omstelemetry.pid')
    py_pid = os.getpid()
    with open(pids_filepath, 'w') as f:
        f.write(str(py_pid) + '\n')

    if HUtilObject is not None:
        watcher = watcherutil.Watcher(HUtilObject.error, HUtilObject.log)

        watcher_thread = Thread(target = watcher.watch)
        self_mon_thread = Thread(target = watcher.monitor_health)

        watcher_thread.start()
        self_mon_thread.start()

        watcher_thread.join()
        self_mon_thread.join()

    return 0, ""

def prepare_update():
    """
    Copy / move configuration directory to the backup
    """

    # First check if backup directory was previously created for given workspace.
    # If it is created with all the files , we need not move the files again.

    public_settings, _ = get_settings()
    workspaceId = public_settings.get('workspaceId')
    etc_remove_path = os.path.join(EtcOMSAgentPath, workspaceId)
    etc_move_path = os.path.join(EtcOMSAgentPath, ExtensionStateSubdirectory, workspaceId)
    if (not os.path.isdir(etc_move_path)):
        shutil.move(etc_remove_path, etc_move_path)

    return 0, ""

def restore_state(workspaceId):
    """
    Copy / move state from backup to the expected location.
    """
    try:
        etc_backup_path = os.path.join(EtcOMSAgentPath, ExtensionStateSubdirectory, workspaceId)
        etc_final_path = os.path.join(EtcOMSAgentPath, workspaceId)
        if (os.path.isdir(etc_backup_path) and not os.path.isdir(etc_final_path)):
            shutil.move(etc_backup_path, etc_final_path)
    except Exception as e:
        hutil_log_error("Error while restoring the state. Exception : "+traceback.format_exc())


def install():
    """
    Ensure that this VM distro and version are supported.
    Install the OMSAgent shell bundle, using retries.
    Note: install operation times out from WAAgent at 15 minutes, so do not
    wait longer.
    """
    exit_if_vm_not_supported('Install')

    public_settings, protected_settings = get_settings()
    if public_settings is None:
        raise ParameterMissingException('Public configuration must be ' \
                                        'provided')
    workspaceId = public_settings.get('workspaceId')
    check_workspace_id(workspaceId)

    # Take the backup of the state for given workspace.
    restore_state(workspaceId)

    # In the case where a SCOM connection is already present, we should not
    # create conflicts by installing the OMSAgent packages
    stopOnMultipleConnections = public_settings.get('stopOnMultipleConnections')
    if (stopOnMultipleConnections is not None
            and stopOnMultipleConnections is True):
        detect_multiple_connections(workspaceId)

    package_directory = os.path.join(os.getcwd(), PackagesDirectory)
    bundle_path = os.path.join(package_directory, BundleFileName)

    os.chmod(bundle_path, 100)
    cmd = InstallCommandTemplate.format(bundle_path)
    hutil_log_info('Running command "{0}"'.format(cmd))

    # Retry, since install can fail due to concurrent package operations
    exit_code, output = run_command_with_retries_output(cmd, retries = 15,
                                         retry_check = retry_if_dpkg_locked_or_curl_is_not_found,
                                         final_check = final_check_if_dpkg_locked)

    return exit_code, output

def check_kill_process(pstring):
    for line in os.popen("ps ax | grep " + pstring + " | grep -v grep"):
        fields = line.split()
        pid = fields[0]
        os.kill(int(pid), signal.SIGKILL)

def uninstall():
    """
    Uninstall the OMSAgent shell bundle.
    This is a somewhat soft uninstall. It is not a purge.
    Note: uninstall operation times out from WAAgent at 5 minutes
    """
    package_directory = os.path.join(os.getcwd(), PackagesDirectory)
    bundle_path = os.path.join(package_directory, BundleFileName)
    global IsUpgrade

    os.chmod(bundle_path, 100)
    cmd = UninstallCommandTemplate.format(bundle_path)
    hutil_log_info('Running command "{0}"'.format(cmd))

    # Retry, since uninstall can fail due to concurrent package operations
    try:
        exit_code, output = run_command_with_retries_output(cmd, retries = 5,
                                            retry_check = retry_if_dpkg_locked_or_curl_is_not_found,
                                            final_check = final_check_if_dpkg_locked)
    except Exception as e:
        # try to force clean the installation
        try:
            check_kill_process("omsagent")
            exit_code = 0
        except Exception as ex:
            exit_code = 1
            message = 'Uninstall failed with error: {0}\n' \
                    'Stacktrace: {1}'.format(ex, traceback.format_exc())

    if IsUpgrade:
        IsUpgrade = False
    else:
        remove_workspace_configuration()

    return exit_code, output

def enable():
    """
    Onboard the OMSAgent to the specified OMS workspace.
    This includes enabling the OMS process on the VM.
    This call will return non-zero or throw an exception if
    the settings provided are incomplete or incorrect.
    Note: enable operation times out from WAAgent at 5 minutes
    """
    exit_if_vm_not_supported('Enable')

    public_settings, protected_settings = get_settings()

    if public_settings is None:
        raise ParameterMissingException('Public configuration must be ' \
                                        'provided')
    if protected_settings is None:
        raise ParameterMissingException('Private configuration must be ' \
                                        'provided')

    vmResourceId = protected_settings.get('vmResourceId')

    # If vmResourceId is not provided in private settings, get it from metadata API
    if vmResourceId is None or not vmResourceId:
        vmResourceId = get_vmresourceid_from_metadata()
        hutil_log_info('vmResourceId from Metadata API is {0}'.format(vmResourceId))

    if vmResourceId is None:
        hutil_log_info('This may be a classic VM')

    enableAutomaticManagement = public_settings.get('enableAutomaticManagement')

    if (enableAutomaticManagement is not None
           and enableAutomaticManagement is True):
        hutil_log_info('enableAutomaticManagement is set to true; the ' \
                       'workspace ID and key will be determined by the OMS ' \
                       'service.')

        workspaceInfo = retrieve_managed_workspace(vmResourceId)
        if (workspaceInfo is None or 'WorkspaceId' not in workspaceInfo
                or 'WorkspaceKey' not in workspaceInfo):
            raise OneClickException('Workspace info was not determined')
        else:
            # Note: do NOT log workspace keys!
            hutil_log_info('Managed workspaceInfo has been retrieved')
            workspaceId = workspaceInfo['WorkspaceId']
            workspaceKey = workspaceInfo['WorkspaceKey']
            try:
                check_workspace_id_and_key(workspaceId, workspaceKey)
            except InvalidParameterError as e:
                raise OMSServiceOneClickException('Received invalid ' \
                                                  'workspace info: ' \
                                                  '{0}'.format(e))

    else:
        workspaceId = public_settings.get('workspaceId')
        workspaceKey = protected_settings.get('workspaceKey')
        check_workspace_id_and_key(workspaceId, workspaceKey)

    # Check if omsadmin script is available
    if not os.path.exists(OMSAdminPath):
        log_and_exit('Enable', EnableCalledBeforeSuccessfulInstall,
                     'OMSAgent onboarding script {0} does not exist. Enable ' \
                     'cannot be called before install.'.format(OMSAdminPath))

    vmResourceIdParam = '-a {0}'.format(vmResourceId)

    proxy = protected_settings.get('proxy')
    proxyParam = ''
    if proxy is not None:
        proxyParam = '-p {0}'.format(proxy)

    # get domain from protected settings
    domain = protected_settings.get('domain')
    if domain is None:
        # detect opinsights domain using IMDS
        domain = get_azure_cloud_domain()
    else:
        hutil_log_info("Domain retrieved from protected settings '{0}'".format(domain))

    domainParam = ''
    if domain:
        domainParam = '-d {0}'.format(domain)

    optionalParams = '{0} {1} {2}'.format(domainParam, proxyParam, vmResourceIdParam)
    onboard_cmd = OnboardCommandWithOptionalParams.format(OMSAdminPath,
                                                          workspaceId,
                                                          workspaceKey,
                                                          optionalParams)

    hutil_log_info('Handler initiating onboarding.')
    exit_code, output = run_command_with_retries_output(onboard_cmd, retries = 5,
                                         retry_check = retry_onboarding,
                                         final_check = raise_if_no_internet,
                                         check_error = True, log_cmd = False)

    # now ensure the permissions and ownership is set recursively
    try:
        workspaceId = public_settings.get('workspaceId')
        etc_final_path = os.path.join(EtcOMSAgentPath, workspaceId)
        if (os.path.isdir(etc_final_path)):
            uid = pwd.getpwnam(AgentUser).pw_uid
            gid = grp.getgrnam(AgentGroup).gr_gid
            os.chown(etc_final_path, uid, gid)
            os.system('chmod {1} {0}'.format(etc_final_path, 750))

            for root, dirs, files in os.walk(etc_final_path):
                for d in dirs:
                    os.chown(os.path.join(root, d), uid, gid)
                    os.system('chmod {1} {0}'.format(os.path.join(root, d), 750))
                for f in files:
                    os.chown(os.path.join(root, f), uid, gid)
                    os.system('chmod {1} {0}'.format(os.path.join(root, f), 640))
    except:
        hutil_log_info('Failed to set permissions for OMS directories, could potentially have issues uploading.')

    if exit_code is 0:
        # Create a marker file to denote the workspace that was
        # onboarded using the extension. This will allow supporting
        # multi-homing through the extension like Windows does
        extension_marker_path = os.path.join(EtcOMSAgentPath, workspaceId,
                                             'conf/.azure_extension_marker')
        if os.path.exists(extension_marker_path):
            hutil_log_info('Extension marker file {0} already ' \
                           'created'.format(extension_marker_path))
        else:
            try:
                open(extension_marker_path, 'w').close()
                hutil_log_info('Created extension marker file ' \
                               '{0}'.format(extension_marker_path))
            except IOError as e:
                try:
                    open(extension_marker_path, 'w+').close()
                    hutil_log_info('Created extension marker file ' \
                               '{0}'.format(extension_marker_path))
                except IOError as ex:
                    hutil_log_error('Error creating {0} with error: ' \
                                '{1}'.format(extension_marker_path, ex))
                    # we are having some kind of permissions issue creating the marker file
                    output = "Couldn't create marker file"
                    exit_code = 52 # since it is a missing dependency

        # Sleep to prevent bombarding the processes, then restart all processes
        # to resolve any issues with auto-started processes from --upgrade
        time.sleep(PostOnboardingSleepSeconds)
        run_command_and_log(RestartOMSAgentServiceCommand)

        #start telemetry process if enable is successful
        start_telemetry_process()

    return exit_code, output

def remove_workspace_configuration():
    """
    This is needed to distinguish between extension removal vs extension upgrade.
    Its a workaround for waagent upgrade routine calling 'remove' on an old version
    before calling 'upgrade' on new extension version issue.
    In upgrade case, we need workspace configuration to persist when in
    remove case we need all the files be removed.
    This method will remove all the files/folders from the workspace path in Etc and Var.
    """

    public_settings, _ = get_settings()
    workspaceId = public_settings.get('workspaceId')
    etc_remove_path = os.path.join(EtcOMSAgentPath, workspaceId)
    var_remove_path = os.path.join(VarOMSAgentPath, workspaceId)

    shutil.rmtree(etc_remove_path, True)
    shutil.rmtree(var_remove_path, True)
    hutil_log_info('Moved oms etc configuration directory and cleaned up var directory')
    
def is_arc_installed():
    """
    Check if the system is on an Arc machine
    """
    # Using systemctl to check this since Arc only supports VMs that have systemd
    check_arc = os.system('systemctl status himdsd 1>/dev/null 2>&1')
    return check_arc == 0

def get_arc_endpoint():
    """
    Find the endpoint for Arc Hybrid IMDS
    """
    endpoint_filepath = '/lib/systemd/system.conf.d/azcmagent.conf'
    endpoint = ''
    try:
        with open(endpoint_filepath, 'r') as f:
            data = f.read()
        endpoint = data.split("\"IMDS_ENDPOINT=")[1].split("\"\n")[0]
    except:
        hutil_log_error('Unable to load Arc IMDS endpoint from {0}'.format(endpoint_filepath))
    return endpoint

def get_imds_endpoint():
    """
    Find the endpoint for IMDS, whether Arc or not
    """
    azure_imds_endpoint = 'http://169.254.169.254/metadata/instance?api-version=2018-10-01'
    if (is_arc_installed()):
        hutil_log_info('Arc is installed, loading Arc-specific IMDS endpoint')
        imds_endpoint = get_arc_endpoint()
        if imds_endpoint:
            imds_endpoint += '/metadata/instance?api-version=2019-08-15'
        else: 
            # Fall back to the traditional IMDS endpoint; the cloud domain and VM
            # resource id detection logic are resilient to failed queries to IMDS
            imds_endpoint = azure_imds_endpoint
            hutil_log_info('Falling back to default Azure IMDS endpoint')
    else:
        imds_endpoint = azure_imds_endpoint
    
    hutil_log_info('Using IMDS endpoint "{0}"'.format(imds_endpoint))
    return imds_endpoint

def get_vmresourceid_from_metadata():
    imds_endpoint = get_imds_endpoint()
    req = urllib.request.Request(imds_endpoint)
    req.add_header('Metadata', 'True')

    try:
        response = json.loads(urllib.request.urlopen(req).read())

        if ('compute' not in response or response['compute'] is None):
            return None # classic vm

        if response['compute']['vmScaleSetName']:
            return '/subscriptions/{0}/resourceGroups/{1}/providers/Microsoft.Compute/virtualMachineScaleSets/{2}/virtualMachines/{3}'.format(response['compute']['subscriptionId'],response['compute']['resourceGroupName'],response['compute']['vmScaleSetName'],response['compute']['name'])
        else:
            return '/subscriptions/{0}/resourceGroups/{1}/providers/Microsoft.Compute/virtualMachines/{2}'.format(response['compute']['subscriptionId'],response['compute']['resourceGroupName'],response['compute']['name'])

    except urllib.error.HTTPError as e:
        hutil_log_error('Request to Metadata service URL ' \
                        'failed with an HTTPError: {0}'.format(e))
        hutil_log_info('Response from Metadata service: ' \
                       '{0}'.format(e.read()))
        return None
    except:
        hutil_log_error('Unexpected error from Metadata service')
        return None

def get_azure_environment_from_imds():
    imds_endpoint = get_imds_endpoint()
    req = urllib.request.Request(imds_endpoint)
    req.add_header('Metadata', 'True')

    try:
        response = json.loads(urllib.request.urlopen(req).read())

        if ('compute' not in response or response['compute'] is None):
            return None # classic vm

        if ('azEnvironment' not in response['compute'] or response['compute']['azEnvironment'] is None):
            return None # classic vm

        return response['compute']['azEnvironment']
    except urllib.error.HTTPError as e:
        hutil_log_error('Request to Metadata service URL ' \
                        'failed with an HTTPError: {0}'.format(e))
        hutil_log_info('Response from Metadata service: ' \
                       '{0}'.format(e.read()))
        return None
    except:
        hutil_log_error('Unexpected error from Metadata service')
        return None

def get_azure_cloud_domain():
    try:
        environment = get_azure_environment_from_imds()

        if environment:
            for cloud, domain in CloudDomainMap.items():
                if environment.lower() == cloud.lower():
                    hutil_log_info('Detected cloud environment "{0}" via IMDS. The domain "{1}" will be used.'.format(cloud, domain))
                    return domain

        hutil_log_info('Unknown cloud environment "{0}"'.format(environment))
    except Exception as e:
        hutil_log_error('Failed to detect cloud environment: {0}'.format(e))

    hutil_log_info('Falling back to default domain "{0}"'.format(CloudDomainMap[DefaultCloudName]))
    return CloudDomainMap[DefaultCloudName]

def retrieve_managed_workspace(vm_resource_id):
    """
    EnableAutomaticManagement has been set to true; the
    ManagedIdentity extension and the VM Resource ID are also
    required for the OneClick scenario
    Using these and the Metadata API, we will call the OMS service
    to determine what workspace ID and key to onboard to
    """
    # Check for OneClick scenario requirements:
    if not os.path.exists(ManagedIdentityExtListeningURLPath):
        raise ManagedIdentityExtMissingException

    # Determine the Tenant ID using the Metadata API
    tenant_id = get_tenant_id_from_metadata_api(vm_resource_id)

    # Retrieve an OAuth token using the ManagedIdentity extension
    if tenant_id is not None:
        hutil_log_info('Tenant ID from Metadata API is {0}'.format(tenant_id))
        access_token = get_access_token(tenant_id, OAuthTokenResource)
    else:
        return None

    # Query OMS service for the workspace info for onboarding
    if tenant_id is not None and access_token is not None:
        return get_workspace_info_from_oms(vm_resource_id, tenant_id,
                                           access_token)
    else:
        return None


def disable():
    """
    Disable all OMS workspace processes on the VM.
    Note: disable operation times out from WAAgent at 15 minutes
    """
    #stop the telemetry process
    stop_telemetry_process()

    # Check if the service control script is available
    if not os.path.exists(OMSAgentServiceScript):
        log_and_exit('Disable', 1, 'OMSAgent service control script {0} does' \
                                   'not exist. Disable cannot be called ' \
                                   'before install.'.format(OMSAgentServiceScript))
        return 1

    exit_code, output = run_command_and_log(DisableOMSAgentServiceCommand)
    return exit_code, output


# Dictionary of operations strings to methods
operations = {'Disable' : disable,
              'Uninstall' : uninstall,
              'Install' : install,
              'Enable' : enable,
              # For update call we will only prepare the update by taking some backup of the state
              #  since omsagent.py->install() will be called
              # everytime upgrade is done due to upgradeMode =
              # "UpgradeWithInstall" set in HandlerManifest
              'Update' : prepare_update,
              'Telemetry' : telemetry
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
            if (operation == 'Telemetry'):
                logFileName = 'watcher.log'

            hutil = HUtil.HandlerUtility(waagent.Log, waagent.Error, logFileName=logFileName)
            hutil.do_parse_context(operation)
        # parse_context may throw KeyError if necessary JSON key is not
        # present in settings
        except KeyError as e:
            waagent_log_error('Unable to parse context with error: ' \
                              '{0}'.format(e))
            raise ParameterMissingException
    return hutil


def is_vm_supported_for_extension():
    """
    Checks if the VM this extension is running on is supported by OMSAgent
    Returns for platform.linux_distribution() vary widely in format, such as
    '7.3.1611' returned for a VM with CentOS 7, so the first provided
    digits must match
    The supported distros of the OMSAgent-for-Linux are allowed to utilize
    this VM extension. All other distros will get error code 51
    """
    supported_dists = {'redhat' : ['6', '7', '8'], 'red hat' : ['6', '7', '8'], 'rhel' : ['6', '7', '8'], # Red Hat
                       'centos' : ['6', '7', '8'], # CentOS
                       'oracle' : ['6', '7', '8'], 'ol': ['6', '7', '8'], # Oracle
                       'debian' : ['8', '9'], # Debian
                       'ubuntu' : ['14.04', '16.04', '18.04', '20.04'], # Ubuntu
                       'suse' : ['12', '15'], 'sles' : ['12', '15'] # SLES
    }

    vm_dist, vm_ver, vm_supported = '', '', False

    try:
        vm_dist, vm_ver, vm_id = platform.linux_distribution()
    except AttributeError:
        try:
            vm_dist, vm_ver, vm_id = platform.dist()
        except AttributeError:
            hutil_log_info("Falling back to /etc/os-release distribution parsing")

    # Fallback if either of the above fail; on some (especially newer)
    # distros, linux_distribution() and dist() are unreliable or deprecated
    if not vm_dist and not vm_ver:
        try:
            with open('/etc/os-release', 'r') as fp:
                for line in fp:
                    if line.startswith('ID='):
                        vm_dist = line.split('=')[1]
                        vm_dist = vm_dist.split('-')[0]
                        vm_dist = vm_dist.replace('\"', '').replace('\n', '')
                    elif line.startswith('VERSION_ID='):
                        vm_ver = line.split('=')[1]
                        vm_ver = vm_ver.replace('\"', '').replace('\n', '')
        except:
            return vm_supported, 'Indeterminate operating system', ''

    # Find this VM distribution in the supported list
    for supported_dist in list(supported_dists.keys()):
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
    Check if this VM distro and version are supported by the OMSAgent.
    If this VM is not supported, log the proper error code and exit.
    """
    vm_supported, vm_dist, vm_ver = is_vm_supported_for_extension()
    if not vm_supported:
        log_and_exit(operation, UnsupportedOperatingSystem, 'Unsupported operating system: ' \
                                    '{0} {1}'.format(vm_dist, vm_ver))
    return 0


def exit_if_openssl_unavailable(operation):
    """
    Check if the openssl commandline interface is available to use
    If not, throw error to return UnsupportedOpenSSL error code
    """
    exit_code, output = run_get_output('which openssl', True, False)
    if exit_code is not 0:
        log_and_exit(operation, UnsupportedOpenSSL, 'OpenSSL is not available')
    return 0


def check_workspace_id_and_key(workspace_id, workspace_key):
    """
    Validate formats of workspace_id and workspace_key
    """
    check_workspace_id(workspace_id)

    # Validate that workspace_key is of the correct format (base64-encoded)
    if workspace_key is None:
        raise ParameterMissingException('Workspace key must be provided')

    try:
        encoded_key = base64.b64encode(base64.b64decode(workspace_key))
        if sys.version_info >= (3,): # in python 3, base64.b64encode will return bytes, so decode to str for comparison
            encoded_key = encoded_key.decode()

        if encoded_key != workspace_key:
            raise InvalidParameterError('Workspace key is invalid')
    except TypeError:
        raise InvalidParameterError('Workspace key is invalid')


def check_workspace_id(workspace_id):
    """
    Validate that workspace_id matches the GUID regex
    """
    if workspace_id is None:
        raise ParameterMissingException('Workspace ID must be provided')

    search = re.compile(GUIDOnlyRegex, re.M)
    if not search.match(workspace_id):
        raise InvalidParameterError('Workspace ID is invalid')


def detect_multiple_connections(workspace_id):
    """
    If the VM already has a workspace/SCOM configured, then we should
    disallow a new connection when stopOnMultipleConnections is used

    Throw an exception in these cases:
    - The workspace with the given workspace_id has not been onboarded
      to the VM, but at least one other workspace has been
    - The workspace with the given workspace_id has not been onboarded
      to the VM, and the VM is connected to SCOM

    If the extension operation is connecting to an already-configured
    workspace, it is not a stopping case
    """
    other_connection_exists = False
    if os.path.exists(OMSAdminPath):
        exit_code, utfoutput = run_get_output(WorkspaceCheckCommand,
                                           chk_err = False)

        # output may contain unicode characters not supported by ascii
        # for e.g., generates the following error if used without conversion: UnicodeDecodeError: 'ascii' codec can't decode byte 0xc3 in position 18: ordinal not in range(128)
        # default encoding in python is ascii in python < 3
        if sys.version_info < (3,):
            output = utfoutput.decode('utf8').encode('utf8')

        if output.strip().lower() != 'no workspace':
            for line in output.split('\n'):
                if workspace_id in line:
                    hutil_log_info('The workspace to be enabled has already ' \
                                   'been configured on the VM before; ' \
                                   'continuing despite ' \
                                   'stopOnMultipleConnections flag')
                    return
                else:
                    # Note: if scom workspace dir is created, a line containing
                    # "Workspace(SCOM Workspace): scom" will be here
                    # If any other line is here, it may start sending data later
                    other_connection_exists = True
    else:
        for dir_name, sub_dirs, files in os.walk(EtcOMSAgentPath):
            for sub_dir in sub_dirs:
                sub_dir_name = os.path.basename(sub_dir)
                workspace_search = re.compile(GUIDOnlyRegex, re.M)
                if sub_dir_name == workspace_id:
                    hutil_log_info('The workspace to be enabled has already ' \
                                   'been configured on the VM before; ' \
                                   'continuing despite ' \
                                   'stopOnMultipleConnections flag')
                    return
                elif (workspace_search.match(sub_dir_name)
                        or sub_dir_name == 'scom'):
                    other_connection_exists = True

    if other_connection_exists:
        err_msg = ('This machine is already connected to some other Log ' \
                   'Analytics workspace, please set ' \
                   'stopOnMultipleConnections to false in public ' \
                   'settings or remove this property, so this machine ' \
                   'can connect to new workspaces, also it means this ' \
                   'machine will get billed multiple times for each ' \
                   'workspace it report to. ' \
                   '(LINUXOMSAGENTEXTENSION_ERROR_MULTIPLECONNECTIONS)')
        # This exception will get caught by the main method
        raise UnwantedMultipleConnectionsException(err_msg)
    else:
        detect_scom_connection()


def detect_scom_connection():
    """
    If these two conditions are met, then we can assume the
    VM is monitored
    by SCOM:
    1. SCOMPort is open and omiserver is listening on it
    2. scx certificate is signed by SCOM server

    To determine it check for existence of below two
    conditions:
    1. SCOMPort is open and omiserver is listening on it:
       /etc/omi/conf/omiserver.conf can be parsed to
       determine it.
    2. scx certificate is signed by SCOM server: scom cert
       is present @ /etc/opt/omi/ssl/omi-host-<hostname>.pem
       (/etc/opt/microsoft/scx/ssl/scx.pem is a softlink to
       this). If the VM is monitored by SCOM then issuer
       field of the certificate will have a value like
       CN=SCX-Certificate/title=<GUID>, DC=<SCOM server hostname>
       (e.g CN=SCX-Certificate/title=SCX94a1f46d-2ced-4739-9b6a-1f06156ca4ac,
       DC=NEB-OM-1502733)

    Otherwise, if a scom configuration directory has been
    created, we assume SCOM is in use
    """
    scom_port_open = None # return when determine this is false
    cert_signed_by_scom = False

    if os.path.exists(OMSAdminPath):
        scom_port_open = detect_scom_using_omsadmin()
        if scom_port_open is False:
            return

    # If omsadmin.sh option is not available, use omiconfigeditor
    if (scom_port_open is None and os.path.exists(OMIConfigEditorPath)
            and os.path.exists(OMIServerConfPath)):
        scom_port_open = detect_scom_using_omiconfigeditor()
        if scom_port_open is False:
            return

    # If omiconfigeditor option is not available, directly parse omiserver.conf
    if scom_port_open is None and os.path.exists(OMIServerConfPath):
        scom_port_open = detect_scom_using_omiserver_conf()
        if scom_port_open is False:
            return

    if scom_port_open is None:
        hutil_log_info('SCOM port could not be determined to be open')
        return

    # Parse the certificate to determine if SCOM issued it
    if os.path.exists(SCOMCertPath):
        exit_if_openssl_unavailable('Install')
        cert_cmd = 'openssl x509 -in {0} -noout -text'.format(SCOMCertPath)
        cert_exit_code, cert_output = run_get_output(cert_cmd, chk_err = False,
                                                     log_cmd = False)
        if cert_exit_code is 0:
            issuer_re = re.compile(SCOMCertIssuerRegex, re.M)
            if issuer_re.search(cert_output):
                hutil_log_info('SCOM cert exists and is signed by SCOM server')
                cert_signed_by_scom = True
            else:
                hutil_log_info('SCOM cert exists but is not signed by SCOM ' \
                               'server')
        else:
            hutil_log_error('Error reading SCOM cert; cert could not be ' \
                            'determined to be signed by SCOM server')
    else:
        hutil_log_info('SCOM cert does not exist')

    if scom_port_open and cert_signed_by_scom:
        err_msg = ('This machine may already be connected to a System ' \
                   'Center Operations Manager server. Please set ' \
                   'stopOnMultipleConnections to false in public settings ' \
                   'or remove this property to allow connection to the Log ' \
                   'Analytics workspace. ' \
                   '(LINUXOMSAGENTEXTENSION_ERROR_MULTIPLECONNECTIONS)')
        raise UnwantedMultipleConnectionsException(err_msg)


def detect_scom_using_omsadmin():
    """
    This method assumes that OMSAdminPath exists; if packages have not
    been installed yet, this may not exist
    Returns True if omsadmin.sh indicates that SCOM port is open
    """
    omsadmin_cmd = '{0} -o'.format(OMSAdminPath)
    exit_code, output = run_get_output(omsadmin_cmd, False, False)
    # Guard against older omsadmin.sh versions
    if ('illegal option' not in output.lower()
            and 'unknown option' not in output.lower()):
        if exit_code is 0:
            hutil_log_info('According to {0}, SCOM port is ' \
                           'open'.format(omsadmin_cmd))
            return True
        elif exit_code is 1:
            hutil_log_info('According to {0}, SCOM port is not ' \
                           'open'.format(omsadmin_cmd))
    return False


def detect_scom_using_omiconfigeditor():
    """
    This method assumes that the relevant files exist
    Returns True if omiconfigeditor indicates that SCOM port is open
    """
    omi_cmd = '{0} httpsport -q {1} < {2}'.format(OMIConfigEditorPath,
                                                  SCOMPort, OMIServerConfPath)
    exit_code, output = run_get_output(omi_cmd, False, False)
    # Guard against older omiconfigeditor versions
    if ('illegal option' not in output.lower()
            and 'unknown option' not in output.lower()):
        if exit_code is 0:
            hutil_log_info('According to {0}, SCOM port is ' \
                           'open'.format(omi_cmd))
            return True
        elif exit_code is 1:
            hutil_log_info('According to {0}, SCOM port is not ' \
                           'open'.format(omi_cmd))
    return False


def detect_scom_using_omiserver_conf():
    """
    This method assumes that the relevant files exist
    Returns True if omiserver.conf indicates that SCOM port is open
    """
    with open(OMIServerConfPath, 'r') as omiserver_file:
        omiserver_txt = omiserver_file.read()

    httpsport_search = r'^[\s]*httpsport[\s]*=(.*)$'
    httpsport_re = re.compile(httpsport_search, re.M)
    httpsport_matches = httpsport_re.search(omiserver_txt)
    if (httpsport_matches is not None and
            httpsport_matches.group(1) is not None):
        ports = httpsport_matches.group(1)
        ports = ports.replace(',', ' ')
        ports_list = ports.split(' ')
        if str(SCOMPort) in ports_list:
            hutil_log_info('SCOM port is listed in ' \
                           '{0}'.format(OMIServerConfPath))
            return True
        else:
            hutil_log_info('SCOM port is not listed in ' \
                           '{0}'.format(OMIServerConfPath))
    else:
        hutil_log_info('SCOM port is not listed in ' \
                       '{0}'.format(OMIServerConfPath))
    return False


def run_command_and_log(cmd, check_error = True, log_cmd = True):
    """
    Run the provided shell command and log its output, including stdout and
    stderr.
    The output should not contain any PII, but the command might. In this case,
    log_cmd should be set to False.
    """
    exit_code, output = run_get_output(cmd, check_error, log_cmd)
    if log_cmd:
        hutil_log_info('Output of command "{0}": \n{1}'.format(cmd.rstrip(), output))
    else:
        hutil_log_info('Output: \n{0}'.format(output))

    # also write output to STDERR since WA agent uploads that to Azlinux Kusto DB
    # take only the last 100 characters as extension cuts off after that
    try:
        if exit_code is not 0:
            sys.stderr.write(output[-500:])

        # For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log
        if exit_code is 17:
            if "Failed dependencies:" in output:
                # 52 is the exit code for missing dependency
                # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
                exit_code = 52
                output = "Installation failed due to missing dependencies. For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log"
            elif "waiting for transaction lock" in output or "dpkg: error processing package systemd" in output or "dpkg-deb" in output or "dpkg:" in output:
                # 52 is the exit code for missing dependency
                # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
                exit_code = 52
                output = "There seems to be an issue in your package manager dpkg or rpm. For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log"
            elif "Errors were encountered while processing:" in output:
                # 52 is the exit code for missing dependency
                # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
                exit_code = 52
                output = "There seems to be an issue while processing triggers in systemd. For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log"
            elif "Cannot allocate memory" in output:
                # 52 is the exit code for missing dependency
                # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
                exit_code = 52
                output = "There seems to be insufficient memory for the installation. For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log"
        elif exit_code is 19:
            if "rpmdb" in output or "cannot open Packages database" in output or "dpkg (subprocess): cannot set security execution context for maintainer script" in output or "error: dpkg status database is locked by another process" in output:
                # OMI (19) happens to be the first package we install and if we get rpmdb failures, its a system issue
                # 52 is the exit code for missing dependency i.e. rpmdb, libc6 or libpam-runtime
                # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
                exit_code = 52
                output = "There seems to be an issue in your package manager dpkg or rpm. For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log"
            elif "libc6 is not installed" in output or "libpam-runtime is not installed" in output or "exited with status 52" in output or "/bin/sh is needed" in output:
                # OMI (19) happens to be the first package we install and if we get rpmdb failures, its a system issue
                # 52 is the exit code for missing dependency i.e. rpmdb, libc6 or libpam-runtime
                # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
                exit_code = 52
                output = "Installation failed due to missing dependencies. For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log"
        elif exit_code is 33:
            if "Permission denied" in output:
                # Enable failures
                # 52 is the exit code for missing dependency i.e. rpmdb, libc6 or libpam-runtime
                # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
                exit_code = 52
                output = "Installation failed due to insufficient permissions. Please ensure omsagent user is part of the sudoer file and has sufficient permissions to install. For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log"
        elif exit_code is 5:
            if "Reason: InvalidWorkspaceKey" in output or "Reason: MissingHeader" in output:
                # Enable failures
                # 53 is the exit code for configuration errors
                # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
                exit_code = 53
                output = "Installation failed due to incorrect workspace key. Please check if the workspace key is correct. For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log"
        elif exit_code is 8:
            if "Check the correctness of the workspace ID and shared key" in output:
                # Enable failures
                # 53 is the exit code for configuration errors
                # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
                exit_code = 53
                output = "Installation failed due to incorrect workspace key. Please check if the workspace key is correct. For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log"

        if exit_code is not 0 and exit_code is not 52:
            if "dpkg:" in output or "dpkg :" in output or "rpmdb:" in output or "rpm.lock" in output:
                # OMI (19) happens to be the first package we install and if we get rpmdb failures, its a system issue
                # 52 is the exit code for missing dependency i.e. rpmdb, libc6 or libpam-runtime
                # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
                exit_code = 52
                output = "There seems to be an issue in your package manager dpkg or rpm. For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log"
            if "conflicts with file from package" in output or "Failed dependencies:" in output or "Please install curl" in output or "is needed by" in output or "check_version_installable" in output or "Error: curl was not installed" in output or "Please install the ctypes package" in output or "gpg is not installed" in output:
                # OMI (19) happens to be the first package we install and if we get rpmdb failures, its a system issue
                # 52 is the exit code for missing dependency i.e. rpmdb, libc6 or libpam-runtime
                # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
                exit_code = 52
                output = "Installation failed due to missing dependencies. For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log"
            if "Permission denied" in output:
                # Enable failures
                # 52 is the exit code for missing dependency i.e. rpmdb, libc6 or libpam-runtime
                # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
                exit_code = 52
                output = "Installation failed due to insufficient permissions. Please ensure omsagent user is part of the sudoer file and has sufficient permissions to install. For details, check logs in /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/extension.log"
    except:
        hutil_log_info('Failed to write output to STDERR')

    return exit_code, output


def run_command_with_retries(cmd, retries, retry_check, final_check = None,
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
    If the retry_check returns True for retry_verbosely, we will try cmd with
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

    return exit_code

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


def was_curl_found(exit_code, output):
    """
    Returns false if exit_code indicates that curl was not installed; this can
    occur when package lists need to be updated, or when some archives are
    out-of-date
    """
    if exit_code is InstallErrorCurlNotInstalled:
        return False
    return True

def retry_skip(exit_code, output):
    """
    skip retires
    """
    return False, '', False

def retry_if_dpkg_locked_or_curl_is_not_found(exit_code, output):
    """
    Some commands fail because the package manager is locked (apt-get/dpkg
    only); this will allow retries on failing commands.
    Sometimes curl's dependencies (i.e. libcurl) are not installed; if this
    is the case on a VM with apt-get, 'apt-get -f install' should be run
    Sometimes curl is not installed and is also not found in the package list;
    if this is the case on a VM with apt-get, update the package list
    """
    retry_verbosely = False
    dpkg_locked = is_dpkg_locked(exit_code, output)
    curl_found = was_curl_found(exit_code, output)
    apt_get_exit_code, apt_get_output = run_get_output('which apt-get',
                                                       chk_err = False,
                                                       log_cmd = False)
    if dpkg_locked:
        return True, 'Retrying command because package manager is locked.', \
               retry_verbosely
    elif (not curl_found and apt_get_exit_code is 0 and
            ('apt-get -f install' in output
            or 'Unmet dependencies' in output.lower())):
        hutil_log_info('Installing all dependencies of curl:')
        run_command_and_log('apt-get -f install')
        return True, 'Retrying command because curl and its dependencies ' \
                     'needed to be installed', retry_verbosely
    elif not curl_found and apt_get_exit_code is 0:
        hutil_log_info('Updating package lists to make curl available')
        run_command_and_log('apt-get update')
        return True, 'Retrying command because package lists needed to be ' \
                     'updated', retry_verbosely
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


def retry_onboarding(exit_code, output):
    """
    Retry under any of these conditions:
    - If the onboarding request returns 403: this may indicate that the agent
      GUID and certificate should be re-generated
    - If the onboarding request returns a different non-200 code: the OMS
      service may be temporarily unavailable
    - If the onboarding curl command returns an unaccounted-for error code,
      we should retry with verbose logging
    """
    retry_verbosely = False

    if exit_code is EnableErrorOMSReturned403:
        return True, 'Retrying the onboarding command to attempt generating ' \
                     'a new agent ID and certificate.', retry_verbosely
    elif exit_code is EnableErrorOMSReturnedNon200:
        return True, 'Retrying; the OMS service may be temporarily ' \
                     'unavailable.', retry_verbosely
    elif exit_code is EnableErrorOnboarding:
        return True, 'Retrying with verbose logging.', True
    return False, '', False


def raise_if_no_internet(exit_code, output):
    """
    Raise the CannotConnectToOMSException exception if the onboarding
    script returns the error code to indicate that the OMS service can't be
    resolved
    """
    if exit_code is EnableErrorResolvingHost:
        raise CannotConnectToOMSException
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

        if ('protectedSettings' in h_settings
                and 'protectedSettingsCertThumbprint' in h_settings
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
            "name" : "Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux",
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
            output = output.decode('latin-1')
            exit_code = 0
        except subprocess.CalledProcessError as e:
            exit_code = e.returncode
            output = e.output.decode('latin-1')

    output = output.encode('utf-8', 'ignore')

    # On python 3, encode returns a byte object, so we must decode back to a string
    if sys.version_info >= (3,):
        output = output.decode()

    return exit_code, output.strip()


def get_tenant_id_from_metadata_api(vm_resource_id):
    """
    Retrieve the Tenant ID using the Metadata API of the VM resource ID
    Since we have not authenticated, the Metadata API will throw a 401, but
    the headers of the 401 response will contain the tenant ID
    """
    tenant_id = None
    metadata_endpoint = get_metadata_api_endpoint(vm_resource_id)
    metadata_request = urllib.request.Request(metadata_endpoint)
    try:
        # This request should fail with code 401
        metadata_response = urllib.request.urlopen(metadata_request)
        hutil_log_info('Request to Metadata API did not fail as expected; ' \
                       'attempting to use headers from response to ' \
                       'determine Tenant ID')
        metadata_headers = metadata_response.headers
    except urllib.error.HTTPError as e:
        metadata_headers = e.headers

    if metadata_headers is not None and 'WWW-Authenticate' in metadata_headers:
        auth_header = metadata_headers['WWW-Authenticate']
        auth_header_regex = r'authorization_uri=\"https:\/\/login\.windows\.net/(' + GUIDRegex + ')\"'
        auth_header_search = re.compile(auth_header_regex)
        auth_header_matches = auth_header_search.search(auth_header)
        if not auth_header_matches:
            raise MetadataAPIException('The WWW-Authenticate header in the ' \
                                       'response does not contain expected ' \
                                       'authorization_uri format')
        else:
            tenant_id = auth_header_matches.group(1)
    else:
        raise MetadataAPIException('Expected information from Metadata API ' \
                                   'is not present')

    return tenant_id


def get_metadata_api_endpoint(vm_resource_id):
    """
    Extrapolate Metadata API endpoint from VM Resource ID
    Example VM resource ID: /subscriptions/306ee7f1-3d0a-4605-9f39-ff253cc02708/resourceGroups/LinuxExtVMResourceGroup/providers/Microsoft.Compute/virtualMachines/lagalbraOCUb16C
    Corresponding example endpoint: https://management.azure.com/subscriptions/306ee7f1-3d0a-4605-9f39-ff253cc02708/resourceGroups/LinuxExtVMResourceGroup?api-version=2016-09-01
    """
    # Will match for ARM and Classic VMs, Availability Sets, VM Scale Sets
    vm_resource_id_regex = r'^\/subscriptions\/(' + GUIDRegex + ')\/' \
                            'resourceGroups\/([^\/]+)\/providers\/Microsoft' \
                            '\.(?:Classic){0,1}Compute\/(?:virtualMachines|' \
                            'availabilitySets|virtualMachineScaleSets)' \
                            '\/[^\/]+$'
    vm_resource_id_search = re.compile(vm_resource_id_regex, re.M)
    vm_resource_id_matches = vm_resource_id_search.search(vm_resource_id)
    if not vm_resource_id_matches:
        raise InvalidParameterError('VM Resource ID is invalid')
    else:
        subscription_id = vm_resource_id_matches.group(1)
        resource_group = vm_resource_id_matches.group(2)

    metadata_url = 'https://management.azure.com/subscriptions/{0}' \
                   '/resourceGroups/{1}'.format(subscription_id,
                                                resource_group)
    metadata_data = urllib.parse.urlencode({'api-version' : '2016-09-01'})
    metadata_endpoint = '{0}?{1}'.format(metadata_url, metadata_data)
    return metadata_endpoint


def get_access_token(tenant_id, resource):
    """
    Retrieve an OAuth token by sending an OAuth2 token exchange
    request to the local URL that the ManagedIdentity extension is
    listening to
    """
    # Extract the endpoint that the ManagedIdentity extension is listening on
    with open(ManagedIdentityExtListeningURLPath, 'r') as listening_file:
        listening_settings_txt = listening_file.read()
    try:
        listening_settings = json.loads(listening_settings_txt)
        listening_url = listening_settings['url']
    except:
        raise ManagedIdentityExtException('Could not extract listening URL ' \
                                          'from settings file')

    # Send an OAuth token exchange request
    oauth_data = {'authority' : 'https://login.microsoftonline.com/' \
                                '{0}'.format(tenant_id),
                  'resource' : resource
    }
    oauth_request = urllib.request.Request(listening_url + '/oauth2/token',
                                    urllib.parse.urlencode(oauth_data))
    oauth_request.add_header('Metadata', 'true')
    try:
        oauth_response = urllib.request.urlopen(oauth_request)
        oauth_response_txt = oauth_response.read()
    except urllib.error.HTTPError as e:
        hutil_log_error('Request to ManagedIdentity extension listening URL ' \
                        'failed with an HTTPError: {0}'.format(e))
        hutil_log_info('Response from ManagedIdentity extension: ' \
                       '{0}'.format(e.read()))
        raise ManagedIdentityExtException('Request to listening URL failed ' \
                                          'with HTTPError {0}'.format(e))
    except:
        raise ManagedIdentityExtException('Unexpected error from request to ' \
                                          'listening URL')

    try:
        oauth_response_json = json.loads(oauth_response_txt)
    except:
        raise ManagedIdentityExtException('Error parsing JSON from ' \
                                          'listening URL response')

    if (oauth_response_json is not None
            and 'access_token' in oauth_response_json):
        return oauth_response_json['access_token']
    else:
        raise ManagedIdentityExtException('Could not retrieve access token ' \
                                          'in the listening URL response')


def get_workspace_info_from_oms(vm_resource_id, tenant_id, access_token):
    """
    Send a request to the OMS service with the VM information to
    determine the workspace the OMSAgent should onboard to
    """
    oms_data = {'ResourceId' : vm_resource_id,
                'TenantId' : tenant_id,
                'JwtToken' : access_token
    }
    oms_request_json = json.dumps(oms_data)
    oms_request = urllib.request.Request(OMSServiceValidationEndpoint)
    oms_request.add_header('Content-Type', 'application/json')

    retries = 5
    initial_sleep_time = AutoManagedWorkspaceCreationSleepSeconds
    sleep_increase_factor = 1
    try_count = 0
    sleep_time = initial_sleep_time

    # Workspace may not be provisioned yet; sleep and retry if
    # provisioning has been accepted
    while try_count <= retries:
        try:
            oms_response = urllib.request.urlopen(oms_request, oms_request_json)
            oms_response_txt = oms_response.read()
        except urllib.error.HTTPError as e:
            hutil_log_error('Request to OMS threw HTTPError: {0}'.format(e))
            hutil_log_info('Response from OMS: {0}'.format(e.read()))
            raise OMSServiceOneClickException('ValidateMachineIdentity ' \
                                              'request returned an error ' \
                                              'HTTP code: {0}'.format(e))
        except:
            raise OMSServiceOneClickException('Unexpected error from ' \
                                              'ValidateMachineIdentity ' \
                                              'request')

        should_retry = retry_get_workspace_info_from_oms(oms_response)
        if not should_retry:
            # TESTED
            break
        elif try_count == retries:
            # TESTED
            hutil_log_error('Retries for ValidateMachineIdentity request ran ' \
                            'out: required workspace information cannot be ' \
                            'extracted')
            raise OneClickException('Workspace provisioning did not complete ' \
                                    'within the allotted time')

        # TESTED
        try_count += 1
        time.sleep(sleep_time)
        sleep_time *= sleep_increase_factor

    if not oms_response_txt:
        raise OMSServiceOneClickException('Body from ValidateMachineIdentity ' \
                                          'response is empty; required ' \
                                          'workspace information cannot be ' \
                                          'extracted')
    try:
        oms_response_json = json.loads(oms_response_txt)
    except:
        raise OMSServiceOneClickException('Error parsing JSON from ' \
                                          'ValidateMachineIdentity response')

    if (oms_response_json is not None and 'WorkspaceId' in oms_response_json
            and 'WorkspaceKey' in oms_response_json):
        return oms_response_json
    else:
        hutil_log_error('Could not retrieve both workspace ID and key from ' \
                        'the OMS service response {0}; cannot determine ' \
                        'workspace ID and key'.format(oms_response_json))
        raise OMSServiceOneClickException('Required workspace information ' \
                                          'was not found in the ' \
                                          'ValidateMachineIdentity response')


def retry_get_workspace_info_from_oms(oms_response):
    """
    Return True to retry if the response from OMS for the
    ValidateMachineIdentity request incidates that the request has
    been accepted, but the managed workspace is still being
    provisioned
    """
    try:
        oms_response_http_code = oms_response.getcode()
    except:
        hutil_log_error('Unable to get HTTP code from OMS repsonse')
        return False

    if (oms_response_http_code is 202 or oms_response_http_code is 204
                                      or oms_response_http_code is 404):
        hutil_log_info('Retrying ValidateMachineIdentity OMS request ' \
                       'because workspace is still being provisioned; HTTP ' \
                       'code from OMS is {0}'.format(oms_response_http_code))
        return True
    else:
        hutil_log_info('Workspace is provisioned; HTTP code from OMS is ' \
                       '{0}'.format(oms_response_http_code))
        return False


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

class OmsAgentForLinuxException(Exception):
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


class ParameterMissingException(OmsAgentForLinuxException):
    """
    There is a missing parameter for the OmsAgentForLinux Extension
    """
    error_code = MissingorInvalidParameterErrorCode
    def get_error_message(self, operation):
        return '{0} failed due to a missing parameter: {1}'.format(operation,
                                                                   self)


class InvalidParameterError(OmsAgentForLinuxException):
    """
    There is an invalid parameter for the OmsAgentForLinux Extension
    ex. Workspace ID does not match GUID regex
    """
    error_code = MissingorInvalidParameterErrorCode
    def get_error_message(self, operation):
        return '{0} failed due to an invalid parameter: {1}'.format(operation,
                                                                    self)


class UnwantedMultipleConnectionsException(OmsAgentForLinuxException):
    """
    This VM is already connected to a different Log Analytics workspace
    and stopOnMultipleConnections is set to true
    """
    error_code = UnwantedMultipleConnectionsErrorCode
    def get_error_message(self, operation):
        return '{0} failed due to multiple connections: {1}'.format(operation,
                                                                    self)


class CannotConnectToOMSException(OmsAgentForLinuxException):
    """
    The OMSAgent cannot connect to the OMS service
    """
    error_code = CannotConnectToOMSErrorCode # error code to indicate no internet access
    def get_error_message(self, operation):
        return 'The agent could not connect to the Microsoft Operations ' \
               'Management Suite service. Please check that the system ' \
               'either has Internet access, or that a valid HTTP proxy has ' \
               'been configured for the agent. Please also check the ' \
               'correctness of the workspace ID.'


class OneClickException(OmsAgentForLinuxException):
    """
    A generic exception for OneClick-related issues
    """
    error_code = OneClickErrorCode
    def get_error_message(self, operation):
        return 'Encountered an issue related to the OneClick scenario: ' \
               '{0}'.format(self)


class ManagedIdentityExtMissingException(OneClickException):
    """
    This extension being present is required for the OneClick scenario
    """
    error_code = ManagedIdentityExtMissingErrorCode
    def get_error_message(self, operation):
        return 'The ManagedIdentity extension is required to be installed ' \
               'for Automatic Management to be enabled. Please set ' \
               'EnableAutomaticManagement to false in public settings or ' \
               'install the ManagedIdentityExtensionForLinux Azure VM ' \
               'extension.'


class ManagedIdentityExtException(OneClickException):
    """
    Thrown when we encounter an issue with ManagedIdentityExtensionForLinux
    """
    error_code = ManagedIdentityExtErrorCode
    def get_error_message(self, operation):
        return 'Encountered an issue with the ManagedIdentity extension: ' \
               '{0}'.format(self)


class MetadataAPIException(OneClickException):
    """
    Thrown when we encounter an issue with Metadata API
    """
    error_code = MetadataAPIErrorCode
    def get_error_message(self, operation):
        return 'Encountered an issue with the Metadata API: {0}'.format(self)


class OMSServiceOneClickException(OneClickException):
    """
    Thrown when prerequisites were satisfied but could not retrieve the managed
    workspace information from OMS service
    """
    error_code = OMSServiceOneClickErrorCode
    def get_error_message(self, operation):
        return 'Encountered an issue with the OMS service: ' \
               '{0}'.format(self)


if __name__ == '__main__' :
    main()
