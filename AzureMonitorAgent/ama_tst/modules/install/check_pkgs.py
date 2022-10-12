import os

from error_codes import *
from errors      import error_info
from helpers     import get_package_version, find_ama_version



def check_packages():
    # check azuremonitoragent rpm/dpkg
    (ama_vers, e) = find_ama_version()
    if (ama_vers == None):
        error_info.append((e,))
        return ERR_AMA_INSTALL
    if (len(ama_vers) > 1):
        return ERR_MULTIPLE_AMA
    
    # find subcomponent binaries
    subcomponents = ['mdsd', 'telegraf', 'agentlauncher', 'amacoreagent', 'MetricsExtension', 'fluent-bit']
    missed_subcomponent = []
    for subcomponent in subcomponents:
        bin_file = '/opt/microsoft/azuremonitoragent/bin/{0}'.format(subcomponent)
        if (not os.path.isfile(bin_file)):
            missed_subcomponent.append(subcomponent)
    if len(missed_subcomponent) > 0:
        error_info.append((', '.join(missed_subcomponent),))
        return ERR_SUBCOMPONENT_INSTALL
    return NO_ERROR

def check_syslog():
    pkg_version, e = get_package_version('rsyslog')
    if (pkg_version != None):
        return NO_ERROR
    pkg_version, e = get_package_version('syslog-ng')
    if (pkg_version != None):
        return NO_ERROR
    pkg_version, e = get_package_version('syslog-ng-core')
    if (pkg_version != None):
        return NO_ERROR
    return ERR_LOG_DAEMON