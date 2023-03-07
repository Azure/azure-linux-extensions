import os

from error_codes       import *
from errors            import error_info
from helpers           import geninfo_lookup, run_cmd_output

CONF_ACCESS_CMD = 'sudo -u syslog test -r {0}; echo "$?"'
SOCKET_ACCESS_CMD = 'sudo -u syslog test -{0} {1}; echo "$?"'
AMA_SOCKET = "/run/azuremonitoragent/default_syslog.socket"


def check_conf_files():
    # update syslog destination path with correct location
    syslog_dest = geninfo_lookup('SYSLOG_DEST')
    if (syslog_dest == None):
        return ERR_SYSLOG

    # verify syslog destination exists / not empty / accessible by syslog user
    if (not os.path.isfile(syslog_dest)):
        error_info.append(('file', syslog_dest))
        return ERR_FILE_MISSING
    if (os.stat(syslog_dest).st_size == 0):
        error_info.append((syslog_dest,))
        return ERR_FILE_EMPTY
    if (run_cmd_output(CONF_ACCESS_CMD.format(syslog_dest)) != "0"):
        error_info.append(('file', syslog_dest, 'read'))
        return ERR_CONF_FILE_PERMISSION
    
    return NO_ERROR

def check_socket():
    if (not os.path.exists(AMA_SOCKET)):
        error_info.append(('socket', AMA_SOCKET))
        return ERR_FILE_MISSING
    if (run_cmd_output(SOCKET_ACCESS_CMD.format('r', AMA_SOCKET)) != "0"):
        error_info.append(('socket', AMA_SOCKET, 'read'))
        return ERR_CONF_FILE_PERMISSION
    if (run_cmd_output(SOCKET_ACCESS_CMD.format('w', AMA_SOCKET)) != "0"):
        error_info.append(('socket', AMA_SOCKET, 'write'))
        return ERR_CONF_FILE_PERMISSION
    return NO_ERROR