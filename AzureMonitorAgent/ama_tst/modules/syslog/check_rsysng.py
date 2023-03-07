import subprocess

from error_codes import *
from errors      import error_info
from helpers     import add_geninfo

RSYSLOG_CONF = "/etc/rsyslog.d/10-azuremonitoragent.conf"
SYSLOG_NG_CONF = "/etc/syslog-ng/conf.d/azuremonitoragent.conf"



# check syslog with systemctl
def check_sys_systemctl(service): 
    try:
        sys_status = subprocess.check_output(['systemctl', 'status', service], \
                        universal_newlines=True, stderr=subprocess.STDOUT)
        sys_lines = sys_status.split('\n')
        for line in sys_lines:
            line = line.strip()
            if line.startswith('Active: '):
                stripped_line = line.lstrip('Active: ')
                # exists and running correctly
                if stripped_line.startswith('active (running) since '):
                    return NO_ERROR
                # exists but not running correctly
                else:
                    error_info.append((service, stripped_line, 'systemctl'))
                    return ERR_SERVICE_STATUS
    except subprocess.CalledProcessError as e:
        # service not on machine
        if (e.returncode == 4):
            return ERR_SYSLOG
        else:
            error_info.append((service, e.output, 'systemctl'))
            return ERR_SERVICE_STATUS

def check_services():
    checked_rsyslog = check_sys_systemctl('rsyslog')
    # rsyslog successful
    if (checked_rsyslog == NO_ERROR):
        add_geninfo('SYSLOG_DEST', RSYSLOG_CONF)
        return NO_ERROR

    checked_syslog_ng = check_sys_systemctl('syslog-ng')
    # syslog-ng successful
    if (checked_syslog_ng == NO_ERROR):
        add_geninfo('SYSLOG_DEST', SYSLOG_NG_CONF)
        return NO_ERROR

    # ran into error trying to get syslog
    if ((checked_rsyslog==ERR_SERVICE_STATUS) or (checked_syslog_ng==ERR_SERVICE_STATUS)):
        return ERR_SERVICE_STATUS

    return ERR_SYSLOG