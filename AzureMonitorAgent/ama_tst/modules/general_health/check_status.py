import subprocess
import re

from error_codes import *
from errors      import error_info

# check if the subcomponents restart in a given time interval
def check_restart_status():
    subcomponents = {'azuremonitoragent': 'azuremonitoragent', 
                     'metrics-sourcer': 'telegraf',
                     'azuremonitor-agentlauncher': 'agentlauncher',
                     'azuremonitor-coreagent': 'amacoreagent',
                     'metrics-extension': 'MetricsExtension'}
    restart_logs = ""
    for key in subcomponents.keys():
        output = subprocess.check_output(['journalctl', '-n', '100', '--no-pager', '-u', key], universal_newlines=True,\
                                            stderr=subprocess.STDOUT)
        # split log message (e.g. <time> <VM name> azuremonitoragent[25670]:  * Starting Azure Monitor Agent Daemon:)
        lines = output.split('\n')
        process_logs = {}
        for line in lines:
            match = re.findall(".*{0}\[.*\].*".format(subcomponents[key]), line)
            if len(match) == 0:
                continue
            log = match[0]
            pid = log.split('[')[1].split(']')[0]
            if pid not in process_logs:
                process_logs[pid] = log
        
        # add to warning if restart more than 10 times recently
        if len(process_logs) > 10:
            logs = '\n'.join(process_logs.values())
            restart_logs = restart_logs + "{0} restarts multiple times recently:\n\n{1}".format(key, logs)
            restart_logs = restart_logs + "\n--------------------------------------------------------------------------------\n"
    
    if not restart_logs == "":
        error_info.append((restart_logs,))
        return WARN_RESTART_LOOP
    return NO_ERROR
