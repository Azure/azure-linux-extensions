import subprocess

from error_codes import *
from errors      import error_info
from helpers     import geninfo_lookup

SSL_CMD = "echo | openssl s_client -connect {0}:443 -brief"
CURL_CMD = "curl -s -S -k https://{0}/ping"

GLOBAL_HANDLER_URL = "global.handler.control.monitor.azure.com"
REGION_HANDLER_URL = "{0}.handler.control.monitor.azure.com"
ODS_URL = "{0}.ods.opinsights.azure.com"
ME_URL = "management.azure.com"
ME_REGION_URL = "{0}.monitoring.azure.com"


def check_endpt_ssl(ssl_cmd, endpoint):
    """
    openssl connect to specific endpoint
    """
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

        return (connected, verified, ssl_output)
    except Exception as e:
        return (False, False, e)


def check_internet_connect():
    """
    check general internet connectivity
    """
    (connected_docs, verified_docs, e) = check_endpt_ssl(SSL_CMD, "docs.microsoft.com")
    if (connected_docs and verified_docs):
        return NO_ERROR
    elif (connected_docs and not verified_docs):
        error_info.append((SSL_CMD.format("docs.microsoft.com"),))
        return WARN_INTERNET
    else:
        error_info.append((SSL_CMD.format("docs.microsoft.com"),))
        return WARN_INTERNET_CONN


def resolve_ip(endpoint):
    try:
        result = subprocess.call(['nslookup', endpoint], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if not result == 0:
            return False, "nslookup {0}".format(endpoint)
        else:
            return (True, None)
    except Exception as e:
        return (False, e)


def check_endpt_curl(endpoint):
    command = CURL_CMD.format(endpoint)
    try:
        # check proxy
        proxy = geninfo_lookup('MDSD_PROXY_ADDRESS')
        username = geninfo_lookup('MDSD_PROXY_USERNAME')
        if not proxy == None:
            command = command + ' -x {0}'.format(proxy)
        if not username == None:
            password = geninfo_lookup('MDSD_PROXY_PASSWORD')
            command = command + ' -U {0}:{1}'.format(username, password)
        output = subprocess.check_output(command, shell=True,\
                     stderr=subprocess.STDOUT, universal_newlines=True)
        if output == "Healthy":
            return NO_ERROR
        else:
            if proxy == None:
                error_info.append((endpoint, command, output))
                return ERR_ENDPT
            else:
                error_info.append((endpoint, command, output))
                return ERR_ENDPT_PROXY
    except Exception as e:
        error_info.append((endpoint, command, e))
        return ERR_ENDPT
    
    
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
    
    if not geninfo_lookup('ME_REGION') == None:
        endpoints.append(ME_URL)
    for me_region in geninfo_lookup('ME_REGION'):
        endpoints.append(ME_REGION_URL.format(me_region))

    # modify URLs if URL suffix is .us(Azure Government) or .cn(Azure China)
    url_suffix = geninfo_lookup('URL_SUFFIX')
    if not url_suffix == '.com':
        for endpoint in endpoints:
            endpoint.replace('.com', url_suffix)

    for endpoint in endpoints:
        # check if IP address can be resolved using nslookup
        resolved, e = resolve_ip(endpoint)
        if not resolved:
            error_info.append((endpoint,e))
            return ERR_RESOLVE_IP
        
        # check ssl handshake
        command = SSL_CMD
        
        # skip openssl check with authenticated proxy
        if not geninfo_lookup('MDSD_PROXY_USERNAME') == None:
            return WARN_OPENSSL_PROXY
        proxy = geninfo_lookup('MDSD_PROXY_ADDRESS')
        if not proxy == None:
            proxy = proxy.replace('http://', '')
            command = command + ' -proxy {0}'.format(proxy)
        if not geninfo_lookup('SSL_CERT_DIR') == None:
            command = command + " -CApath " + geninfo_lookup('SSL_CERT_DIR')
        if not geninfo_lookup('SSL_CERT_FILE') == None:
            command = command + " -CAfile " + geninfo_lookup('SSL_CERT_FILE')
        (connected, verified, e) = check_endpt_ssl(command, endpoint)
        if not connected or not verified:
            error_info.append((endpoint, command.format(endpoint), e))
            return ERR_ENDPT
        
        # check AMCS ping results
        if "handler.control.monitor" in endpoint:
            checked_curl = check_endpt_curl(endpoint)
            if checked_curl != NO_ERROR:
                return checked_curl
    return NO_ERROR