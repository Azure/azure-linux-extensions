import os

from error_codes  import *
from errors       import error_info, is_error, print_errors
from .check_status import check_restart_status

ERR_FILE_PATH = "/var/opt/microsoft/azuremonitoragent/log/mdsd.err"

def check_err_file():
    """
    output mdsd.err contents if the file is not empty
    """
    tail_size = -50
    pattern = ' [DAEMON] '
    err_logs = []
    with open(ERR_FILE_PATH) as f:
        lines = f.readlines()
        lines = lines[tail_size:]
        for line in lines:
            line = line.rstrip('\n')
            # skip empty lines, daemon start/exit logs
            if line == '':
                continue
            elif pattern in line:
                continue
            else:
                err_logs.append(line)
                
    if len(err_logs) > 0:
        err_logs_str = '\n' + ('\n'.join(err_logs))
        error_info.append((ERR_FILE_PATH, err_logs_str))
        return WARN_MDSD_ERR_FILE
    return NO_ERROR


def ask_restart_ama():
    ama_dir = filter((lambda x : x.startswith("Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-")), os.listdir("/var/lib/waagent"))
    ama_dir = list(ama_dir)
    if len(ama_dir) > 1:
        return ERR_MULTIPLE_AMA
    print("If you need to restart Azure Monitor Agent on this machine, please execute the following commands:\n")
    print("$ cd /var/lib/waagent/{0}".format(ama_dir[0]))
    print("$ ./shim.sh -disable")
    print("$ ./shim.sh -enable")
    return NO_ERROR

def check_general_health(interactive, err_codes=True, prev_success=NO_ERROR):
    print("CHECKING IF THE AGENT IS HEALTHY...")
    success = prev_success

    print("Checking status of subcomponents")
    checked_restart_status = check_restart_status()
    if (is_error(checked_restart_status)):
        return print_errors(checked_restart_status)
    else:
        success = print_errors(checked_restart_status)
    
    print("Checking mdsd.err file")
    checked_err_file = check_err_file()
    if (is_error(checked_err_file)):
        return print_errors(checked_err_file)
    else:
        success = print_errors(checked_err_file)
    
    asked_restart_ama = ask_restart_ama()
    if (is_error(asked_restart_ama)):
        return print_errors(asked_restart_ama)
    else:
        success = print_errors(asked_restart_ama)
    
    print("============================================")
    return success