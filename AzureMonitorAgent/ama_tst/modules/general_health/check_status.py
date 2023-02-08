import subprocess
import re

from error_codes import *
from errors      import error_info
from helpers     import run_cmd_output, get_input, is_metrics_configured

def check_restart_status(interactive):
    """
    check if the subcomponents restart in a given time interval
    """
    subcomponents = {'azuremonitoragent': 'azuremonitoragent', 
                     'azuremonitor-agentlauncher': 'agentlauncher',
                     'azuremonitor-coreagent': 'amacoreagent'}
    if is_metrics_configured():
        subcomponents['metrics-extension'] = 'MetricsExtension'
        subcomponents['metrics-sourcer'] = 'Telegraf'
    restart_logs = ""
    start = "yesterday"
    end = "now"
    since = "--since={0}".format(start)
    until = "--until={0}".format(end)
    
    if interactive:
        print("--------------------------------------------------------------------------------")
        print("Please enter a certain time range that you want to filter logs (default time range: from yesterday to now):\n")
        print("(e.g. Since: <yyyy-mm-dd hh:mm:ss>) or <yyyy-mm-dd>")
        start_input = get_input("Since: ")
        end_input = get_input("Until: ")
        print("--------------------------------------------------------------------------------")
        if start_input != "":
            since = '--since=\"{0}\"'.format(start_input)
            start = start_input
        if end_input != "":
            until = '--until=\"{0}\"'.format(end_input)
            end = end_input
    for key in subcomponents.keys():
        cmd = 'journalctl -n 100 --no-pager -u {0} {1} {2}'.format(key, since, until)
        output = run_cmd_output(cmd)
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
            restart_logs = restart_logs + "Possible restart loop in {0} detected ({1} restarts from {2} to {3}):\n{4}".format(key, len(process_logs), start, end, logs)
            restart_logs = restart_logs + "\n--------------------------------------------------------------------------------\n"
    
    if restart_logs:
        error_info.append((restart_logs,))
        return WARN_RESTART_LOOP
    return NO_ERROR
