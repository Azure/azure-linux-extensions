import os
import subprocess

from error_codes  import *
from errors       import error_info, is_error, print_errors
from .check_os    import check_os
from .check_pkgs  import check_packages, check_syslog
from .check_ama   import check_ama
from helpers      import find_package_manager

def check_space():
    """
    check space in MB for each main directory
    """
    dirnames = ["/etc", "/opt", "/var"]
    for dirname in dirnames:
        space = os.statvfs(dirname)
        free_space = space.f_bavail * space.f_frsize / 1024 / 1024
        if (free_space < 500):
            error_info.append((dirname, free_space))
            return ERR_FREE_SPACE
    return NO_ERROR


def check_pkg_manager():
    pkg_manager = find_package_manager()
    if (pkg_manager == ""):
        return ERR_PKG_MANAGER
    return NO_ERROR

def check_syslog_user():
    with open('/etc/passwd', 'r') as fp:
        for line in fp:
            if line.startswith('syslog:'):
                return NO_ERROR
    return ERR_SYSLOG_USER

def check_installation(interactive, err_codes=True, prev_success=NO_ERROR):
    """
    check all packages are installed
    """
    print("CHECKING INSTALLATION...")
    success = prev_success
    
    # check Supported OS / version
    print("Checking if running a supported OS version...")
    checked_os = check_os()
    if (is_error(checked_os)):
        return print_errors(checked_os)
    else:
        success = print_errors(checked_os)
    
    # check Available disk space
    print("Checking if enough disk space is available...")
    checked_space = check_space()
    if (is_error(checked_space)):
        return print_errors(checked_space)
    else:
        success = print_errors(checked_space)
        
    # check Package manager (dpkg/rpm)
    print("Checking if machine has a supported package manager...")
    checked_pkg_manager = check_pkg_manager()
    if (is_error(checked_pkg_manager)):
        return print_errors(checked_pkg_manager)
    else:
        success = print_errors(checked_pkg_manager)
    
    # check package + subcomponents installation states
    print("Checking if packages and subcomponents are installed correctly...")
    checked_packages = check_packages()
    if (is_error(checked_packages)):
        return print_errors(checked_packages)
    else:
        success = print_errors(checked_packages)
        
    # check AMA version installed
    print("Checking if running a supported version of AMA...")
    checked_ama = check_ama(interactive)
    if (is_error(checked_ama)):
        return print_errors(checked_ama)
    else:
        success = print_errors(checked_ama)
        
    # check Existence of rsyslog or syslog-ng
    print("Checking if rsyslog or syslog-ng exists...")
    checked_syslog = check_syslog()
    if (is_error(checked_syslog)):
        return print_errors(checked_syslog)
    else:
        success = print_errors(checked_syslog)

    # check Syslog user created successfully
    print("Checking if syslog user exists...")
    checked_syslog_user = check_syslog_user()
    if (is_error(checked_syslog_user)):
        return print_errors(checked_syslog_user)
    else:
        success = print_errors(checked_syslog_user)
    print("============================================")
    return success