import subprocess
import json

from error_codes    import *
from errors         import error_info
from helpers        import geninfo_lookup
from logcollector   import is_arc_installed

METADATA_CMD = 'curl -s -H Metadata:true --noproxy "*" "http://{0}/metadata/instance/compute?api-version=2020-06-01"'
AZURE_IP = "169.254.169.254"
ARC_IP = "127.0.0.1:40342"

AZURE_TOKEN_CMD = "curl 'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https%3A%2F%2Fmanagement.azure.com%2F' -H Metadata:true -s"
ARC_TOKEN_CMD = 'ChallengeTokenPath=$(curl -s -D - -H Metadata:true "http://127.0.0.1:40342/metadata/identity/oauth2/token?api-version=2019-11-01&resource=https%3A%2F%2Fmanagement.azure.com"'\
                    '| grep Www-Authenticate | cut -d "=" -f 2 | tr -d "[:cntrl:]") ; ' \
                    'ChallengeToken=$(cat $ChallengeTokenPath) ; ' \
                    'curl -s -H Metadata:true -H "Authorization: Basic $ChallengeToken" "http://127.0.0.1:40342/metadata/identity/oauth2/token?api-version=2019-11-01&resource=https%3A%2F%2Fmanagement.azure.com"'


def check_metadata():
    type = "Azure"
    if is_arc_installed():
        command = METADATA_CMD.format(ARC_IP)
        type = "Hybrid"
    else: 
        command = METADATA_CMD.format(AZURE_IP)
    try:
        output = subprocess.check_output(command, shell=True,\
                     stderr=subprocess.STDOUT, universal_newlines=True)
        output_json = json.loads(output)
        attributes = ['azEnvironment', 'resourceId', 'location']
        for attr in attributes:
            if not attr in output_json:
                error_info.append((type, command, output))
                return ERR_IMDS_METADATA
    except Exception as e:
        error_info.append((type, command, e))
        return ERR_IMDS_METADATA
    return NO_ERROR


def check_token():
    if is_arc_installed():
        command = ARC_TOKEN_CMD
    else: 
        command = AZURE_TOKEN_CMD
    try:
        # check AMA use UAI
        managed_identity = geninfo_lookup('MANAGED_IDENTITY')
        if not managed_identity == None:
            managed_identity = managed_identity.replace('mi_res_id#', 'mi_res_id=')
            command = command.replace('token?', 'token?{0}&'.format(managed_identity))
        
        output = subprocess.check_output(command, shell=True,\
                     stderr=subprocess.STDOUT, universal_newlines=True)
        output_json = json.loads(output)
        if not 'access_token' in output_json:
            error_info.append((command, output))
            return ERR_ACCESS_TOKEN
    except Exception as e:
        error_info.append((command, e))
        return ERR_ACCESS_TOKEN
    return NO_ERROR
     
     
def check_imds_api():
    # check metadata
    checked_metadata = check_metadata()
    if not checked_metadata == NO_ERROR:
        return checked_metadata
    
    # check access token
    checked_token = check_token()
    if not checked_token == NO_ERROR:
        return checked_token
    return NO_ERROR