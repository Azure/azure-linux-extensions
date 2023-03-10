import os

from error_codes import *
from errors      import error_info
from helpers     import general_info, geninfo_lookup, run_cmd_output

CLCONF_PATH = "/etc/opt/microsoft/azuremonitoragent/config-cache/fluentbit/td-agent.conf"

def check_customlog_input():
    cl_input = geninfo_lookup('CL_INPUT')
    if ( cl_input == None or len(cl_input) == 0):
        return ERR_CL_INPUT
    for path in cl_input:
        check_path = run_cmd_output('ls {0}'.format(path)).strip()
        if check_path.endswith('No such file or directory'):
            return ERR_CL_INPUT

    return NO_ERROR
        

def check_customlog_conf():
    global general_info
    # verify td-agent.conf exists / not empty
    if (not os.path.isfile(CLCONF_PATH)):
        error_info.append(('file', CLCONF_PATH))
        return ERR_FILE_MISSING
    if (os.stat(CLCONF_PATH).st_size == 0):
        error_info.append((CLCONF_PATH,))
        return ERR_FILE_EMPTY
    general_info['CL_INPUT'] = []
    try:    
        with open(CLCONF_PATH, 'r') as cl_file:
            cl_lines = cl_file.readlines()
            for cl_line in cl_lines: 
                if (cl_line.strip().startswith('log_file')):
                    cl_log_file = cl_line.strip().split('log_file')[1]
                    general_info['CL_LOG'] =  cl_log_file
                    
                if (cl_line.strip().startswith('Path')):
                    cl_input_path = cl_line.strip().split('Path')[1].strip()
                    general_info['CL_INPUT'].append(cl_input_path)
    except Exception as e:
        error_info.append((e,))
        return ERR_CL_CONF
    
    return NO_ERROR