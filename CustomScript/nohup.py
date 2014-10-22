#!/usr/bin/env python
#
#CustomScript extension
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
#
# Requires Python 2.6+

import os
import string
import subprocess
import time
import sys
import traceback
from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as util

ExtensionShortName = 'CustomScript'
StdoutFile = "stdout"
ErroutFile = "errout"
OutputSize = 4 * 1024

def start_task(hutil, args, interval = 30):
    log_dir = hutil.get_log_dir()
    std_out_file = os.path.join(log_dir, StdoutFile)
    err_out_file = os.path.join(log_dir, ErroutFile)
    std_out = None
    err_out = None
    try:
        std_out = open(std_out_file, "w")
        err_out = open(err_out_file, "w")
        download_dir = os.path.join(os.getcwd(), 'download', hutil.get_seq_no())
        child = subprocess.Popen(args,
                                 cwd = download_dir,
                                 stdout=std_out, 
                                 stderr=err_out)
        time.sleep(1)
        while child.poll() == None:
            msg = get_formatted_log("Script is running...", 
                                    tail(std_out_file), tail(err_out_file))
            hutil.do_status_report('Enable', 'success', '0', msg)
            time.sleep(interval)

        if child.returncode and child.returncode != 0:
            msg = get_formatted_log("Script returned an error.", 
                                    tail(std_out_file), tail(err_out_file))
            hutil.do_exit(1, 'Enable', 'failed', '1', msg)
        else:
            msg = get_formatted_log("Script is finished.", 
                                    tail(std_out_file), tail(err_out_file))
            hutil.do_exit(0, 'Enable', 'success','0', msg)
    except Exception, e:
        hutil.error(("Failed to launch script with error:{0},"
                     "stacktrace:{1}").format(e, traceback.format_exc()))
        hutil.do_exit(1, 'Enable', 'failed', '1', 
                      'Lanch script failed:{0}'.format(e))
    finally:
        if std_out:
            std_out.close()
        if err_out:
            err_out.close()

def tail(log_file, output_size = OutputSize):
    pos = min(output_size, os.path.getsize(log_file))
    with open(log_file, "r") as log:
        log.seek(-pos, 2)
        buf = log.read(output_size)
        buf = filter(lambda x: x in string.printable, buf)
        return buf.decode("ascii", "ignore")

def get_formatted_log(summary, stdout, stderr):
    msg_format = ("{0}\n"
                  "---stdout---\n"
                  "{1}\n"
                  "---errout---\n"
                  "{2}\n")
    return msg_format.format(summary, stdout, stderr)

if __name__ == '__main__':
    waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
    hutil = util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context("Enable")
    start_task(hutil, sys.argv[1:])
