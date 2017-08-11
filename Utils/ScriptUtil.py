# Script utilities
#
# Copyright 2014 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
import os.path
import time
import subprocess
import traceback
import string
import shlex

import LogUtil
from WAAgentUtil import waagent

DefaultStdoutFile = "stdout"
DefaultErroutFile = "errout"

def run_command(hutil, args, cwd, operation, extension_short_name, version, exit_after_run = True, interval = 30, std_out_file_name = DefaultStdoutFile, std_err_file_name = DefaultErroutFile):
    std_out_file = os.path.join(cwd, std_out_file_name)
    err_out_file = os.path.join(cwd, std_err_file_name)
    std_out = None
    err_out = None
    try:
        std_out = open(std_out_file, "w")
        err_out = open(err_out_file, "w")
        start_time = time.time()
        child = subprocess.Popen(args,
                                 cwd=cwd,
                                 stdout=std_out,
                                 stderr=err_out)
        time.sleep(1)
        while child.poll() is None:
            msg = LogUtil.get_formatted_log("Command is running...",
                                    LogUtil.tail(std_out_file), LogUtil.tail(err_out_file))
            hutil.log(msg)
            hutil.do_status_report(operation, 'transitioning', '0', msg)
            time.sleep(interval)

        exit_code = child.returncode
        if child.returncode and child.returncode != 0:
            msg = LogUtil.get_formatted_log("Command returned an error.",
                                    LogUtil.tail(std_out_file), LogUtil.tail(err_out_file))
            hutil.error(msg)
            waagent.AddExtensionEvent(name=extension_short_name,
                                      op=operation,
                                      isSuccess=False,
                                      version=version,
                                      message="(01302)"+msg)
        else:
            msg = LogUtil.get_formatted_log("Command is finished.",
                                    LogUtil.tail(std_out_file), LogUtil.tail(err_out_file))
            hutil.log(msg)
            waagent.AddExtensionEvent(name=extension_short_name,
                                      op=operation,
                                      isSuccess=True,
                                      version=version,
                                      message="(01302)"+msg)
            end_time = time.time()
            waagent.AddExtensionEvent(name=extension_short_name,
                                      op=operation,
                                      isSuccess=True,
                                      version=version,
                                      message=("(01304)Command execution time: "
                                      "{0}s").format(str(end_time-start_time)))
                                      
        log_or_exit(hutil, exit_after_run, exit_code, operation, msg)
    except Exception as e:
        error_msg = ("Failed to launch command with error: {0},"
                     "stacktrace: {1}").format(e, traceback.format_exc())
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=extension_short_name,
                                  op=operation,
                                  isSuccess=False,
                                  version=version,
                                  message="(01101)"+error_msg)
        exit_code = 1                                  
        msg = 'Lanch command failed: {0}'.format(e)
        
        log_or_exit(hutil, exit_after_run, exit_code, operation, msg)
    finally:        
        if std_out:
            std_out.close()
        if err_out:
            err_out.close()
    return exit_code


# do_exit calls sys.exit which raises an exception so we do not call it from the finally block
def log_or_exit(hutil, exit_after_run, exit_code, operation, msg):
    status = 'success' if exit_code == 0 else 'failed'
    if exit_after_run:
        hutil.do_exit(exit_code, operation, status, str(exit_code), msg)
    else:
        hutil.do_status_report(operation, status, str(exit_code), msg)


def parse_args(cmd):
    cmd = filter(lambda x : x in string.printable, cmd)
    cmd = cmd.decode("ascii", "ignore")
    args = shlex.split(cmd)
    # From python 2.6 to python 2.7.2, shlex.split output UCS-4 result like
    # '\x00\x00a'. Temp workaround is to replace \x00
    for idx, val in enumerate(args):
        if '\x00' in args[idx]:
            args[idx] = args[idx].replace('\x00', '')
    return args


