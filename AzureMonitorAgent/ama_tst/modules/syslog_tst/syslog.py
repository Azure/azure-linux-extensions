from error_codes          import *
from errors               import is_error, print_errors
from .check_conf          import check_conf_files, check_socket
from .check_rsysng        import check_services

def check_syslog(interactive, prev_success=NO_ERROR):
    print("CHECKING FOR SYSLOG ISSUES...")

    success = prev_success

    # check rsyslog / syslogng running
    print("Checking if machine has rsyslog or syslog-ng running...")
    checked_services = check_services()
    if (is_error(checked_services)):
        return print_errors(checked_services)
    else:
        success = print_errors(checked_services)

    # check for rsyslog / syslog-ng configuration files
    print("Checking for syslog configuration files...")
    checked_conf_files = check_conf_files()
    if (is_error(checked_conf_files)):
        return print_errors(checked_conf_files)
    else:
        success = print_errors(checked_conf_files)

    # check for syslog socket existence and permissions
    print("Checking for syslog socket...")
    checked_socket = check_socket()
    if (is_error(checked_socket)):
        return print_errors(checked_socket)
    else:
        success = print_errors(checked_socket)
    return success