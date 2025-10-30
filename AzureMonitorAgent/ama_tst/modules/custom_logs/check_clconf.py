import os

from error_codes import *
from errors      import error_info
from helpers     import general_info, geninfo_lookup, run_cmd_output

CLCONF_PATH = "/etc/opt/microsoft/azuremonitoragent/config-cache/fluentbit/td-agent.conf"

def check_customlog_input():
    cl_input = geninfo_lookup('CL_INPUT')
    if (cl_input == None or len(cl_input) == 0):
        error_info.append(("No custom logs file path",))
        return ERR_CL_INPUT
    # cl_input is a list, not a dictionary - iterate over the paths directly
    for path in cl_input:
        # Skip malformed entries that don't look like valid file paths
        if not path or not path.startswith('/'):
            continue
        try: 
            check_path = run_cmd_output('ls {0}'.format(path)).strip()
            if check_path.endswith('No such file or directory'):
                error_info.append((check_path,))
                return ERR_CL_INPUT
        except Exception as e:
            error_info.append((e,))
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
                    
                # Only match exact "Path" lines (not "Path_Key" or other variants)
                if (cl_line.strip().startswith('Path ') or cl_line.strip().startswith('Path\t')):
                    # Extract the path value after the whitespace
                    parts = cl_line.strip().split(None, 1)  # Split on any whitespace, max 1 split
                    if len(parts) > 1:
                        cl_input_path = parts[1].strip()
                        # Only add valid file paths (should start with /)
                        if cl_input_path.startswith('/'):
                            general_info['CL_INPUT'].append(cl_input_path)

    except Exception as e:
        error_info.append((e,))
        return ERR_CL_CONF

    print('cl_input value: {0}'.format(general_info['CL_INPUT']))

    return NO_ERROR