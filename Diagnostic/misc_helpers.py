#!/usr/bin/env python
#
# Azure Linux extension
#
# Linux Azure Diagnostic Extension (Current version is specified in manifest.xml)
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import re
import string
import traceback

from Utils.WAAgentUtil import waagent


def get_extension_operation_type(command):
    if re.match("^([-/]*)(enable)", command):
        return waagent.WALAEventOperation.Enable
    if re.match("^([-/]*)(daemon)", command):   # LAD-specific extension operation (invoked from "./diagnostic.py -enable")
        return "Daemon"
    if re.match("^([-/]*)(install)", command):
        return waagent.WALAEventOperation.Install
    if re.match("^([-/]*)(disable)", command):
        return waagent.WALAEventOperation.Disable
    if re.match("^([-/]*)(uninstall)", command):
        return waagent.WALAEventOperation.Uninstall
    if re.match("^([-/]*)(update)", command):
        return waagent.WALAEventOperation.Update


def wala_event_type_for_telemetry(ext_op_type):
    return "HeartBeat" if ext_op_type == "Daemon" else ext_op_type


def get_storage_endpoint_with_account(account, endpoint_without_account):
    endpoint = endpoint_without_account
    if endpoint:
        parts = endpoint.split('//', 1)
        if len(parts) > 1:
            endpoint = parts[0]+'//'+account+".table."+parts[1]
        else:
            endpoint = 'https://'+account+".table."+parts[0]
    else:
        endpoint = 'https://'+account+'.table.core.windows.net'
    return endpoint


def check_suspected_memory_leak(pid, logger_err):
    memory_leak_threshold_in_KB = 2000000  # Roughly 2GB. TODO: Make it configurable or automatically calculated
    memory_usage_in_KB = 0
    memory_leak_suspected = False

    try:
        # Check /proc/[pid]/status file for "VmRSS" to find out the process's virtual memory usage
        # Note: "VmSize" for some reason starts out very high (>2000000) at this moment, so can't use that.
        with open("/proc/{0}/status".format(pid)) as proc_file:
            for line in proc_file:
                if line.startswith("VmRSS:"):  # Example line: "VmRSS:   33904 kB"
                    memory_usage_in_KB = int(line.split()[1])
                    memory_leak_suspected = memory_usage_in_KB > memory_leak_threshold_in_KB
                    break
    except Exception as e:
        # Not to throw in case any statement above fails (e.g., invalid pid). Just log.
        logger_err("Failed to check memory usage of pid={0}.\nError: {1}\nTrace:\n{2}".format(pid, e, traceback.format_exc()))

    return memory_leak_suspected, memory_usage_in_KB


def read_uuid(run_command):
    code, str_ret = run_command("dmidecode |grep UUID |awk '{print $2}'", chk_err=False)
    return str_ret.strip()


def log_private_settings_keys(private_settings, logger_log, logger_err):
    try:
        msg = "Keys in privateSettings (and some non-secret values): "
        first = True
        for key in private_settings:
            if first:
                first = False
            else:
                msg += ", "
            msg += key
            if key == 'storageAccountEndPoint':
                msg += ":" + private_settings[key]
        logger_log(msg)
    except Exception as e:
        logger_err("Failed to log keys in privateSettings. error:{0} {1}".format(e, traceback.format_exc()))


def tail(log_file, output_size=1024):
    if not os.path.exists(log_file):
        return ""
    pos = min(output_size, os.path.getsize(log_file))
    with open(log_file, "r") as log:
        log.seek(-pos, 2)
        buf = log.read(output_size)
        buf = filter(lambda x: x in string.printable, buf)
        return buf.decode("ascii", "ignore")


def escape_nonalphanumerics(data):
    s_build = ''
    for c in data:
        if c.isalnum():
            s_build += c
        else:
            s_build += ":{0:04X}".format(ord(c))
    return s_build