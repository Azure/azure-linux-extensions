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

import os
import os.path
import re
import sys
import traceback
import time
import platform
import subprocess
import json
import base64

try:
    from Utils.WAAgentUtil import waagent
    import Utils.HandlerUtil as HUtil
except Exception as e:
    # These utils have checks around the use of them; this is not an exit case
    print('Importing utils failed with error: {0}'.format(e))

# Global Variables
PackagesDirectory = 'packages'
BundleFileName = 'omsagent-1.3.4-127.universal.x64.sh'

# Always use upgrade - will handle install if scx, omi are not installed or
# upgrade if they are
InstallCommandTemplate = '{0} --upgrade'
UninstallCommandTemplate = '{0} --remove'
OmsAdminPath = '/opt/microsoft/omsagent/bin/omsadmin.sh'
WorkspaceCheckCommandTemplate = '{0} -l'
OnboardCommandWithOptionalParamsTemplate = '{0} -w {1} -s {2} {3}'
OmsAgentServiceScript = '/opt/microsoft/omsagent/bin/service_control'
DisableOmsAgentServiceCommandTemplate = '{0} disable'
InstallPythonCtypesErrorCode = 61
InstallTarErrorCode = 62

# Configuration
SettingsSequenceNumber = None
HandlerEnvironment = None
SettingsDict = None

# Change permission of log path
ext_log_path = '/var/log/azure/'
if os.path.exists(ext_log_path):
    os.chmod(ext_log_path, 700)


def main():
    """
    Main method
    Parse out operation from argument, invoke the operation, and finish.
    """
    init_waagent_logger()
    waagent_log_info('OmsAgentForLinux started to handle.')

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
        waagent_log_error(e.message)

    if operation is None:
        log_and_exit(None, 'Unknown', 1, 'No valid operation provided')

    # Set up for exit code and any error messages
    exit_code = 0
    message = '{0} succeeded'.format(operation)

    # Invoke operation
    try:
        hutil = parse_context(operation)
        exit_code = operations[operation](hutil)

        # For common problems, provide a more descriptive message
        if exit_code is 1 and operation == 'Install':
            message = 'Install failed with exit code 1. Please make sure ' \
                      'curl, libcurl, and python-ctypes are installed'
        elif exit_code is InstallTarErrorCode and operation == 'Install':
            message = 'Install failed with exit code {0}: please install ' \
                      'tar'.format(InstallTarErrorCode)
        elif (exit_code is InstallPythonCtypesErrorCode
                and operation == 'Install'):
            message = 'Install failed with exit code {0}: please install ' \
                      'the Python ctypes library or package (python-' \
                      'ctypes)'.format(InstallPythonCtypesErrorCode)
        elif exit_code is not 0:
            message = '{0} failed with exit code {1}'.format(operation,
                                                             exit_code)

    except OmsAgentParameterMissingError as e:
        exit_code = 11
        message = '{0} failed due to a missing parameter: ' \
                  '{1}'.format(operation, e.message)
    except OmsAgentInvalidParameterError as e:
        exit_code = 11
        message = '{0} failed due to an invalid parameter: ' \
                  '{1}'.format(operation, e.message)
    except OmsAgentUnwantedMultipleConnectionsException as e:
        exit_code = 10
        message = '{0} failed due to multiple connections: ' \
                  '{1}'.format(operation, e.message)
    except Exception as e:
        exit_code = 1
        message = '{0} failed with error: {1}\n' \
                  'Stacktrace: {2}'.format(operation, e,
                                           traceback.format_exc())

    # Finish up and log messages
    log_and_exit(hutil, operation, exit_code, message)


def dummy_command(hutil):
    """
    Do nothing and return 0
    """
    return 0


def install(hutil):
    """
    Ensure that this VM distro and version are supported.
    Install the OMSAgent shell bundle, using retries.
    """
    exit_if_vm_not_supported(hutil, 'Install')

    file_directory = os.path.join(os.getcwd(), PackagesDirectory)
    file_path = os.path.join(file_directory, BundleFileName)

    os.chmod(file_path, 100)
    cmd = InstallCommandTemplate.format(file_path)
    hutil_log_info(hutil, 'Running command "{0}"'.format(cmd))

    # Retry, since install can fail due to concurrent package operations
    exit_code = run_command_with_retries(hutil, cmd, retries = 10)
    return exit_code


def uninstall(hutil):
    """
    Uninstall the OMSAgent shell bundle.
    This is a somewhat soft uninstall. It is not a purge.
    """
    file_directory = os.path.join(os.getcwd(), PackagesDirectory)
    file_path = os.path.join(file_directory, BundleFileName)

    os.chmod(file_path, 100)
    cmd = UninstallCommandTemplate.format(file_path)
    hutil_log_info(hutil, 'Running command "{0}"'.format(cmd))

    # Retry, since uninstall can fail due to concurrent package operations
    exit_code = run_command_with_retries(hutil, cmd, retries = 10)
    return exit_code


def enable(hutil):
    """
    Onboard the OMSAgent to the specified OMS workspace.
    This includes enabling the OMS process on the machine.
    This call will return non-zero if the settings provided are incomplete or
    incorrect.
    """
    exit_if_vm_not_supported(hutil, 'Enable')

    public_settings, protected_settings = get_settings(hutil)
    if public_settings is None:
        raise OmsAgentParameterMissingError('Public configuration must be ' \
                                            'provided')
    if protected_settings is None:
        raise OmsAgentParameterMissingError('Private configuration must be ' \
                                            'provided')

    workspaceId = public_settings.get('workspaceId')
    workspaceKey = protected_settings.get('workspaceKey')
    proxy = protected_settings.get('proxy')
    vmResourceId = protected_settings.get('vmResourceId')
    stopOnMultipleConnections = public_settings.get('stopOnMultipleConnections')
    if workspaceId is None:
        raise OmsAgentParameterMissingError('Workspace ID must be provided')
    if workspaceKey is None:
        raise OmsAgentParameterMissingError('Workspace key must be provided')

    check_workspace_id_and_key(workspaceId, workspaceKey)

    if (stopOnMultipleConnections is not None
            and stopOnMultipleConnections is True):
        check_wkspc_cmd = WorkspaceCheckCommandTemplate.format(OmsAdminPath)
        list_exit_code, output = run_get_output(check_wkspc_cmd,
                                                chk_err = False)

        # If this enable was called a workspace already saved on the machine,
        # then we should continue; if this workspace is not saved on the
        # machine, but another workspace service is running, then we should
        # stop and warn
        this_wksp_saved = False
        connection_exists = False
        for line in output.split('\n'):
            if workspaceId in line:
                this_wksp_saved = True
            if 'Onboarded(OMSAgent Running)' in line:
                connection_exists = True

        if not this_wksp_saved and connection_exists:
            err_msg = ('This machine is already connected to some other Log ' \
                       'Analytics workspace, please set ' \
                       'stopOnMultipleConnections to false in public ' \
                       'settings or remove this property, so this machine ' \
                       'can connect to new workspaces, also it means this ' \
                       'machine will get billed multiple times for each ' \
                       'workspace it report to. ' \
                       '(LINUXOMSAGENTEXTENSION_ERROR_MULTIPLECONNECTIONS)')
            # This exception will get caught by the main method
            raise OmsAgentUnwantedMultipleConnectionsException(err_msg)

    # Check if omsadmin script is available
    if not os.path.exists(OmsAdminPath):
        log_and_exit(hutil, 'Enable', 1, 'OMSAgent onboarding script {0} not ' \
                                         'exist. Enable cannot be called ' \
                                         'before install.'.format(OmsAdminPath))

    proxyParam = ''
    if proxy is not None:
        proxyParam = '-p {0}'.format(proxy)

    vmResourceIdParam = ''
    if vmResourceId is not None:
        vmResourceIdParam = '-a {0}'.format(vmResourceId)

    optionalParams = '{0} {1}'.format(proxyParam, vmResourceIdParam)
    onboard_cmd = OnboardCommandWithOptionalParamsTemplate.format(OmsAdminPath,
                                                                  workspaceId,
                                                                  workspaceKey,
                                                                  optionalParams)

    hutil_log_info(hutil, 'Handler initiating onboarding.')
    exit_code, output = run_get_output(onboard_cmd)
    # To avoid exposing the shared key, print output separately
    hutil_log_info(hutil, 'Output of onboarding command: \n{0}'.format(output))
    return exit_code


def disable(hutil):
    """
    Disable all OMS workspace processes on the machine.
    """
    # Check if the service control script is available
    if not os.path.exists(OmsAgentServiceScript):
        log_and_exit(hutil, 'Disable', 1, 'OMSAgent service control script ' \
                                          '{0} does not exist. Disable ' \
                                          'cannot be called before ' \
                                          'install.'.format(
                                                     OmsAgentServiceScript))
        return 1

    cmd = DisableOmsAgentServiceCommandTemplate.format(OmsAgentServiceScript)
    exit_code, output = run_command_and_log(hutil, cmd)
    return exit_code


# Dictionary of operations strings to methods
operations = {'Disable' : disable,
              'Uninstall' : uninstall,
              'Install' : install,
              'Enable' : enable,
              # Upgrade is noop since omsagent.py->install() will be called
              # everytime upgrade is done due to upgradeMode =
              # "UpgradeWithInstall" set in HandlerManifest
              'Update' : dummy_command
}


def parse_context(operation):
    """
    Initialize a HandlerUtil object for this operation.
    If the required modules have not been imported, this will return None.
    """
    hutil = None
    if 'Utils.WAAgentUtil' in sys.modules and 'Utils.HandlerUtil' in sys.modules:
        try:
            hutil = HUtil.HandlerUtility(waagent.Log, waagent.Error)
            hutil.do_parse_context(operation)
        # parse_context may throw KeyError if necessary JSON key is not
        # present in settings
        except KeyError as e:
            waagent_log_error('Unable to parse context with error: ' \
                              '{0}'.format(e.message))
            raise OmsAgentParameterMissingError
    return hutil


def is_vm_supported_for_extension():
    """
    Checks if the VM this extension is running on is supported by OMSAgent
    Returns for platform.linux_distribution() vary widely in format, such as
    '7.3.1611' returned for a machine with CentOS 7, so the first provided
    digits must match
    Though Ubuntu 16.10 is not officially supported, we will allow it to
    install and onboard through the VM extension
    """
    supported_dists = {'redhat' : ('5', '6', '7'), # CentOS
                       'centos' : ('5', '6', '7'), # CentOS
                       'red hat' : ('5', '6', '7'), # Oracle, RHEL
                       'oracle' : ('5', '6', '7'), # Oracle
                       'debian' : ('6', '7', '8'), # Debian
                       'ubuntu' : ('12.04', '14.04', '15.04', '15.10',
                                   '16.04', '16.10'), # Ubuntu
                       'suse' : ('11', '12') #SLES
    }

    try:
        vm_dist, vm_ver, vm_id = platform.linux_distribution()
    except AttributeError:
        vm_dist, vm_ver, vm_id = platform.dist()

    vm_supported = False

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


def exit_if_vm_not_supported(hutil, operation):
    """
    Check if this VM distro and version are supported by the OMSAgent.
    If this VM is not supported, log the proper error code and exit.
    """
    vm_supported, vm_dist, vm_ver = is_vm_supported_for_extension()
    if not vm_supported:
        log_and_exit(hutil, operation, 51, 'Unsupported operation system: ' \
                                           '{0} {1}'.format(vm_dist, vm_ver))
    return 0


def check_workspace_id_and_key(workspace_id, workspace_key):
    """
    Validate formats of workspace_id and workspace_key
    """
    # Validate that workspace_id matches the GUID regex
    guid_regex = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    search = re.compile(guid_regex, re.M)
    if not search.match(workspace_id):
        raise OmsAgentInvalidParameterError('Workspace ID is invalid')

    # Validate that workspace_key is of the correct format (base64-encoded)
    try:
        encoded_key = base64.b64encode(base64.b64decode(workspace_key))
        if encoded_key != workspace_key:
            raise OmsAgentInvalidParameterError('Workspace key is invalid')
    except TypeError:
        raise OmsAgentInvalidParameterError('Workspace key is invalid')


def run_command_and_log(hutil, cmd, check_error = True, log_cmd = True):
    """
    Run the provided shell command and log its output, including stdout and
    stderr.
    """
    exit_code, output = run_get_output(cmd, check_error, log_cmd)
    hutil_log_info(hutil, 'Output of command "{0}": \n{1}'.format(cmd,
                                                                  output))
    return exit_code, output


def run_command_with_retries(hutil, cmd, retries, check_error = True,
                             log_cmd = True, initial_sleep_time = 30,
                             sleep_increase_factor = 1):
    """
    Some commands fail because the package manager is locked (apt-get/dpkg
    only); this will allow retries on failing commands.
    Logic used: will retry up to retries times with initial_sleep_time in
    between tries
    Note: install operation times out from WAAgent at 15 minutes, so do not
    wait longer.
    """
    try_count = 0
    sleep_time = initial_sleep_time # seconds
    while try_count <= retries:
        exit_code, output = run_command_and_log(hutil, cmd, check_error, log_cmd)
        if exit_code is 0:
            break
        elif not re.match('^.*dpkg.+lock.*$', output):
            break
        try_count += 1
        hutil_log_info(hutil, 'Retrying command "{0}" because package manager ' \
                              'is locked. Command failed with exit code ' \
                              '{1}'.format(cmd, exit_code))
        time.sleep(sleep_time)
        sleep_time *= sleep_increase_factor

    return exit_code


def get_settings(hutil):
    """
    Retrieve the configuration for this extension operation
    """
    global SettingsDict
    public_settings = None
    protected_settings = None

    if hutil is not None:
        public_settings = hutil.get_public_settings()
        protected_settings = hutil.get_protected_settings()
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
            hutil_log_error(hutil, 'Unable to load handler settings from ' \
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
            except OSError, e:
                pass
            protected_settings_str = output[0]

            if protected_settings_str is None:
                log_and_exit(hutil, 'Enable', 1, 'Failed decrypting ' \
                                                 'protectedSettings')
            protected_settings = ''
            try:
                protected_settings = json.loads(protected_settings_str)
            except:
                hutil_log_error(hutil, 'JSON exception decoding protected ' \
                                       'settings')
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
        config_dir = str(handler_env['handlerEnvironment']['configFolder'])
        status_dir = str(handler_env['handlerEnvironment']['statusFolder'])
    except:
        extension_version = "1.0"
        config_dir = os.path.join(os.getcwd(), 'config')
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
            handler_env=json.loads(handler_env_txt)
            if type(handler_env) == list:
                handler_env = handler_env[0]
            HandlerEnvironment = handler_env
        except Exception as e:
            waagent_log_error(e.message)
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
            for dir_name, sub_dirs, files in os.walk(config_dir):
                for file in files:
                    file_basename = os.path.basename(file)
                    match = re.match(r'[0-9]{1,10}\.settings', file_basename)
                    if match is None:
                        continue
                    cur_seq_no = int(file_basename.split('.')[0])
                    file_path = os.path.join(config_dir, file)
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
        waagent.LoggerInit('/var/log/waagent.log','/dev/stdout', True)
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


def hutil_log_info(hutil, message):
    """
    Log informational message, being cautious of possibility that hutil may
    not be imported and configured
    """
    if hutil is not None:
        hutil.log(message)
    else:
        print('Info: {0}'.format(message))


def hutil_log_error(hutil, message):
    """
    Log error message, being cautious of possibility that hutil may not be
    imported and configured
    """
    if hutil is not None:
        hutil.error(message)
    else:
        print('Error: {0}'.format(message))


def log_and_exit(hutil, operation, exit_code = 1, message = ''):
    """
    Log the exit message and perform the exit
    """
    if exit_code is 0:
        waagent_log_info(message)
        hutil_log_info(hutil, message)
        exit_status = 'success'
    else:
        waagent_log_error(message)
        hutil_log_error(hutil, message)
        exit_status = 'failed'

    if hutil is not None:
        hutil.do_exit(exit_code, operation, exit_status, str(exit_code), message)
    else:
        update_status_file(operation, exit_code, exit_status, message)
        sys.exit(exit_code)


class OmsAgentParameterMissingError(ValueError):
    """
    There is a missing parameter for the OmsAgentForLinux Extension
    """
    pass


class OmsAgentInvalidParameterError(ValueError):
    """
    There is an invalid parameter for the OmsAgentForLinux Extension
    ex. Workspace ID does not match GUID regex
    """
    pass


class OmsAgentUnwantedMultipleConnectionsException(Exception):
    """
    This machine is already connected to a different Log Analytics workspace
    and stopOnMultipleConnections is set to true
    """
    pass


if __name__ == '__main__' :
    main()
