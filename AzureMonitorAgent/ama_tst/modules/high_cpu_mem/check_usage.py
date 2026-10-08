import time
import subprocess

from error_codes import *
from errors      import error_info
from helpers     import get_input, run_cmd_output

def find_mdsd_pid():
    try:
        status = run_cmd_output('systemctl status azuremonitoragent')
        status_lines = status.split('\n')
        for line in status_lines:
            line = line.strip()
            if line.startswith('Main PID:'):
                pid = line.split()[2]
                return (pid, None)
    except subprocess.CalledProcessError as e:
        return (None, e)
    
def check_usage(interactive):
    if interactive:
        print("Checking CPU/memory usage of AMA subcomponents...")
        result = get_input("Do you want to monitor the CPU/memory usage of AMA in 5 minutes? (YES/no)", \
                        (lambda x : x.lower() in ['y','yes','n','no', '']),\
                        "Please enter 'y'/'yes' to run this check, 'n'/'no' to skip this check. \n")
        if result.lower() in ['n', 'no']:
            return NO_ERROR
        
        mdsd_pid, e = find_mdsd_pid()
        if e != None:
            error_info.append((e,))
            return ERR_CHECK_STATUS
        cmd = "top -b -n1 | grep {0}".format(mdsd_pid)
        cpu = []
        mem = []
        # run 5 minutes to collect min/max/avg usage
        for i in range(0, 30):
            output = run_cmd_output(cmd)
            values = list(filter(None, output.strip().split(" ")))
            cpu.append(float(values[8]))
            mem.append(float(values[9]))
            time.sleep(10)
        
        max_cpu = max(cpu)
        min_cpu = min(cpu)
        avg_cpu = sum(cpu)/len(cpu)
        max_mem = max(mem)
        min_mem = min(mem)
        avg_mem = sum(mem)/len(mem)
        print("--------------------------------------------------------------------------------")
        print("CPU usage in the last 5 minutes (%CPU)")
        print("Max: ", max_cpu, "Min: ", min_cpu, "Avg: ", "%.1f" % avg_cpu)
        print("Memory usage in the last 5 minutes (%MEM)")
        print("Max: ", max_mem, "Min: ", min_mem, "Avg: ", "%.1f" % avg_mem)
    return NO_ERROR