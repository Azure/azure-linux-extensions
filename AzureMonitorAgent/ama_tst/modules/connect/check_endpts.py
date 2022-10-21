import os
import subprocess
import re

from error_codes import *
from errors      import error_info
from helpers     import geninfo_lookup

OMSADMIN_PATH = "/etc/opt/microsoft/omsagent/conf/omsadmin.conf"
CERT_PATH = "/etc/opt/microsoft/omsagent/certs/oms.crt"
KEY_PATH = "/etc/opt/microsoft/omsagent/certs/oms.key"
SSL_CMD = "echo | openssl s_client -connect {0}:443 -brief"

GLOBAL_HANDLER_URL = "global.handler.control.monitor.azure.com"
REGION_HANDLER_URL = "{0}.handler.control.monitor.azure.com"
ODS_URL = "{0}.ods.opinsights.azure.com"
ME_URL = "management.azure.com"
ME_REGION_URL = "{0}.monitoring.azure.com"

# openssl connect to specific endpoint
def check_endpt_ssl(ssl_cmd, endpoint):
    try:
        ssl_output = subprocess.check_output(ssl_cmd.format(endpoint), shell=True,\
                     stderr=subprocess.STDOUT, universal_newlines=True)
        ssl_output_lines = ssl_output.split('\n')
        
        (connected, verified) = (False, False)
        for line in ssl_output_lines:
            if (line == "CONNECTION ESTABLISHED"):
                connected = True
                continue
            if (line == "Verification: OK"):
                verified = True
                continue

        return (connected, verified)
    except Exception:
        return (False, False)



# check general internet connectivity
def check_internet_connect():
    (connected_docs, verified_docs) = check_endpt_ssl(SSL_CMD, "docs.microsoft.com")
    if (connected_docs and verified_docs):
        return NO_ERROR
    elif (connected_docs and not verified_docs):
        error_info.append((SSL_CMD.format("docs.microsoft.com"),))
        return WARN_INTERNET
    else:
        error_info.append((SSL_CMD.format("docs.microsoft.com"),))
        return WARN_INTERNET_CONN


# check AMA endpoints
def check_ama_endpts():    
    # compose URLs to check
    endpoints = [GLOBAL_HANDLER_URL]
    regions = geninfo_lookup('DCR_REGION')
    workspace_ids = geninfo_lookup('DCR_WORKSPACE_ID')
    
    if regions == None or workspace_ids == None:
        return ERR_INFO_MISSING
    for region in regions:
        endpoints.append(REGION_HANDLER_URL.format(region))
    for id in workspace_ids:
        endpoints.append(ODS_URL.format(id))
    
    if (geninfo_lookup['ME_REGION'] != None):
        endpoints.append(ME_URL)
    for me_region in geninfo_lookup['ME_REGION']:
        endpoints.append(ME_REGION_URL.format(me_region))

    # modify URLs if URL suffix is .us(Azure Government) or .cn(Azure China)
    url_suffix = geninfo_lookup('URL_SUFFIX')
    endpoint.replace('.com', url_suffix)
    
    for endpoint in endpoints:
        (connected, verified) = check_endpt_ssl(SSL_CMD, endpoint)
        if not connected:
            error_info.append((endpoint, SSL_CMD.format(endpoint)))
            return ERR_ENDPT
        
    return NO_ERROR