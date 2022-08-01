import os

from error_codes import *
from errors      import error_info
from helpers     import get_package_version, find_ama_version



def check_packages():
    # check azuremonitoragent rpm/dpkg
    ama_vers = find_ama_version()
    if (ama_vers == None):
        return ERR_AMA_INSTALL
    if (len(ama_vers) > 1):
        return ERR_MULTIPLE_AMA
    
    # find submodule binaries
    submodules = ['mdsd', 'telegraf', 'agentlauncher', 'amacoreagent', 'MetricsExtension', 'fluent-bit']
    missed_submodule = []
    for submodule in submodules:
        bin_file = '/opt/microsoft/azuremonitoragent/bin/{0}'.format(submodule)
        if (not os.path.isfile(bin_file)):
            missed_submodule.append(submodule)
    if len(missed_submodule) > 0:
        error_info.append((', '.join(missed_submodule),))
        return ERR_SUBMODULE_INSTALL
    return NO_ERROR

def check_syslog():
    pkg_version = get_package_version('rsyslog')
    if (pkg_version != None):
        return NO_ERROR
    pkg_version = get_package_version('syslog-ng')
    if (pkg_version != None):
        return NO_ERROR
    pkg_version = get_package_version('syslog-ng-core')
    if (pkg_version != None):
        return NO_ERROR
    return ERR_LOG_DAEMON