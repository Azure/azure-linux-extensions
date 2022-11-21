import os
import json
import subprocess

from error_codes       import *
from errors            import error_info, is_error, print_errors
from helpers           import general_info, geninfo_lookup
from .check_endpts     import check_internet_connect, check_ama_endpts
from .check_imds       import check_imds_api

def check_parameters():
    global general_info
    try:
        with open('/etc/default/azuremonitoragent', 'r') as fp:
            for line in fp:
                line = line.split('export')[1].strip()
                key = line.split('=')[0]
                value = line.split('=')[1]
                general_info[key] = value
    except (FileNotFoundError, AttributeError) as e:
        error_info.append((e,))
        return ERR_AMA_PARAMETERS
    return NO_ERROR
   
def check_workspace():
    global general_info
    dir_path = '/etc/opt/microsoft/azuremonitoragent/config-cache/configchunks'
    dcr_workspace = set()
    dcr_region = set()
    me_region = set()
    general_info['URL_SUFFIX'] = '.com'
    try:
        for file in os.listdir(dir_path):
            file_path = dir_path + "/" + file
            with open(file_path) as f:
                result = json.load(f)
                channels = result['channels']
                for channel in channels:
                    if channel['protocol'] == 'ods':
                        # parse dcr workspace id
                        endpoint_url = channel['endpoint']
                        worspace_id = endpoint_url.split('https://')[1].split('.ods')[0]
                        dcr_workspace.add(worspace_id)
                        # parse dcr region
                        token_endpoint_uri = channel['tokenEndpointUri']
                        region = token_endpoint_uri.split('Location=')[1].split('&')[0]
                        dcr_region.add(region)
                        # parse url suffix
                        if '.us' in endpoint_url:
                            general_info['URL_SUFFIX'] = '.us'
                        if '.cn' in endpoint_url:
                            general_info['URL_SUFFIX'] = '.cn'                            
                    if channel['protocol'] == 'me':
                        # parse ME region
                        endpoint_url = channel['endpoint']
                        region = endpoint_url.split('https://')[1].split('.monitoring')[0]
                        me_region.add(region)
    except (FileNotFoundError, AttributeError) as e:
        error_info.append((e,))
        return ERR_NO_DCR

    general_info['DCR_WORKSPACE_ID'] = dcr_workspace
    general_info['DCR_REGION'] = dcr_region
    general_info['ME_REGION'] = me_region
    return NO_ERROR

def check_subcomponents(): 
    services = ['azuremonitoragent', 'azuremonitor-agentlauncher', 'azuremonitor-coreagent']
    if len(geninfo_lookup('ME_REGION')) > 0:
        services.append('metrics-sourcer')
        services.append('metrics-extension')
        
    for service in services:
        try:
            status = subprocess.check_output(['systemctl', 'status', service],\
                                    universal_newlines=True, stderr=subprocess.STDOUT)
            status_lines = status.split('\n')
            for line in status_lines:
                line = line.strip()
                if line.startswith('Active:'):
                    if not line.split()[1] == 'active':
                        error_info.append((service, status))
                        return ERR_SUBCOMPONENT_STATUS
        except subprocess.CalledProcessError as e:
            error_info.append((e,))
            return ERR_CHECK_STATUS
            
    return NO_ERROR

def check_connection(interactive, err_codes=True, prev_success=NO_ERROR):
    print("CHECKING CONNECTION...")

    success = prev_success
    
    # check /etc/default/azuremonitoragent file
    print("Checking AMA parameters in /etc/default/azuremonitoragent...")
    checked_parameters = check_parameters()
    if (is_error(checked_parameters)):
        return print_errors(checked_parameters)
    else:
        success = print_errors(checked_parameters)
        
    # check DCR
    print("Checking DCR...")
    checked_workspace = check_workspace()
    if (is_error(checked_workspace)):
        return print_errors(checked_workspace)
    else:
        success = print_errors(checked_workspace)

    # check general internet connectivity
    print("Checking if machine is connected to the internet...")
    checked_internet_connect = check_internet_connect()
    if (is_error(checked_internet_connect)):
        return print_errors(checked_internet_connect)
    else:
        success = print_errors(checked_internet_connect)


    # check if AMA endpoints connected
    print("Checking if machine can connect to Azure Monitor control-plane and data ingestion endpoints...")
    checked_ama_endpts = check_ama_endpts()
    if (is_error(checked_ama_endpts)):
        return print_errors(checked_ama_endpts)
    else:
        success = print_errors(checked_ama_endpts)

    # check if subcomponents are active (e.g. mdsd, telegraf, etc)
    print("Checking if subcomponents have been started...")
    checked_subcomponents = check_subcomponents()
    if (is_error(checked_subcomponents)):
        return print_errors(checked_subcomponents)
    else:
        success = print_errors(checked_subcomponents)
        
    print("Checking if IMDS metadata and MSI tokens are available...")
    checked_imds_api = check_imds_api()
    if (is_error(checked_imds_api)):
        return print_errors(checked_imds_api)
    else:
        success = print_errors(checked_imds_api)
    return success
