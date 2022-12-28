import subprocess
import re

from error_codes import *
from errors      import error_info

def check_restart_status(interactive):
    """
    check if the subcomponents restart in a given time interval
    """
    subcomponents = {'azuremonitoragent': 'azuremonitoragent', 
                     'azuremonitor-agentlauncher': 'agentlauncher',
                     'azuremonitor-coreagent': 'amacoreagent',
                     'metrics-extension': 'MetricsExtension',
                     'metrics-sourcer': 'Telegraf'}
    restart_logs = ""
    for key in subcomponents.keys():
        start_time = "yesterday"
        end_time = "now"
        if interactive:
            print("--------------------------------------------------------------------------------")
            print("Please enter a certain time range that you want to filter logs:\n")
            print("(e.g. Since: <yyyy-mm-dd hh:mm:ss>) or <yyyy-mm-dd>")
            since = input("Since: ")
            until = input("Until: ")
            if since != "":
                start_time = since
            if until != "":
                end_time = until
            output = subprocess.check_output(['journalctl', '-n', '100', '--no-pager', '-u', key, '--since', '"{0}"'.format(start_time), '--until', '"{0}"'.format(end_time)], 
                                             universal_newlines=True, stderr=subprocess.STDOUT)

        else:
            output = subprocess.check_output(['journalctl', '-n', '100', '--no-pager', '-u', key, '--since=yesterday'], universal_newlines=True,\
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
            restart_logs = restart_logs + "Possible restart loop in {0} detected ({1} restarts from {2} to {3}):{4}".format(key, len(process_logs),start_time, end_time, logs)
            restart_logs = restart_logs + "\n--------------------------------------------------------------------------------\n"
    
    if restart_logs:
        error_info.append((restart_logs,))
        return WARN_RESTART_LOOP
    return NO_ERROR
