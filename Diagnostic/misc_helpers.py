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
import xml.dom.minidom

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
    """
    Check suspected memory leak of a process, by inspecting /proc/<pid>/status's VmRSS value.
    :param pid: ID of the process we are checking.
    :param logger_err: Error logging function (e.g., hutil.error)
    :return (bool, int): Bool indicating whether memory leak is suspected. Int for memory usage in KB in true case.
    """
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


class LadLogHelper(object):
    """
    Various LAD log helper functions encapsulated here, so that we don't have to tag along all the parameters.
    """

    def __init__(self, logger_log, logger_error, waagent_event_adder, ext_name, ext_ver):
        """
        Constructor
        :param logger_log: Normal logging function (e.g., hutil.log)
        :param logger_error: Error logging function (e.g., hutil.error)
        :param waagent_event_adder: waagent event add function (waagent.AddExtensionEvent)
        :param ext_name: Extension name (hutil.get_name())
        :param ext_ver: Extension version (hutil.get_extension_version())
        """
        self._logger_log = logger_log
        self._logger_error = logger_error
        self._waagent_event_adder = waagent_event_adder
        self._ext_name = ext_name
        self._ext_ver = ext_ver

    def log_suspected_memory_leak_and_kill_mdsd(self, memory_usage_in_KB, mdsd_process, ext_op):
        """
        Log suspected-memory-leak message both in ext logs and as a waagent event.
        :param memory_usage_in_KB: Memory usage in KB (to be included in the log)
        :param mdsd_process: Python Process object for the mdsd process to kill
        :param ext_op: Extension operation type to use for waagent event (waagent.waagent.WALAEventOperation.HeartBeat)
        :return: None
        """
        memory_leak_msg = "Suspected mdsd memory leak (Virtual memory usage: {0}MB). " \
                          "Recycling mdsd to self-mitigate.".format(int((memory_usage_in_KB + 1023) / 1024))
        self._logger_log(memory_leak_msg)
        # Add a telemetry for a possible statistical analysis
        self._waagent_event_add(name=self._ext_name,
                                op=ext_op,
                                isSuccess=True,
                                version=self._ext_ver,
                                message=memory_leak_msg)
        mdsd_process.kill()


def read_uuid(run_command):
    code, str_ret = run_command("dmidecode |grep UUID |awk '{print $2}'", chk_err=False)
    return str_ret.strip()


def tail(log_file, output_size=1024):
    if not os.path.exists(log_file):
        return ""
    pos = min(output_size, os.path.getsize(log_file))
    with open(log_file, "r") as log:
        log.seek(-pos, 2)
        buf = log.read(output_size)
        buf = filter(lambda x: x in string.printable, buf)
        return buf.decode("ascii", "ignore")


def update_selinux_settings_for_rsyslogomazuremds(run_command, ext_dir):
    # This is still needed for Redhat-based distros, which still require SELinux to be allowed
    # for even Unix domain sockets.
    # Anyway, we no longer use 'semanage' (so no need to install policycoreutils-python).
    # We instead compile from the bundled SELinux module def for lad_mdsd
    # TODO Either check the output of these commands or run without capturing output
    if os.path.exists("/usr/sbin/semodule") or os.path.exists("/sbin/semodule"):
        run_command('checkmodule -M -m -o {0}/lad_mdsd.mod {1}/lad_mdsd.te'.format(ext_dir, ext_dir))
        run_command('semodule_package -o {0}/lad_mdsd.pp -m {1}/lad_mdsd.mod'.format(ext_dir, ext_dir))
        run_command('semodule -u {0}/lad_mdsd.pp'.format(ext_dir))


def get_mdsd_proxy_config(waagent_setting, ext_settings, logger):
    # mdsd http proxy setting
    proxy_setting_name = 'mdsdHttpProxy'
    proxy_config = waagent_setting  # waagent.HttpProxyConfigString from /etc/waagent.conf has highest priority
    if not proxy_config:
        proxy_config = ext_settings.read_protected_config(proxy_setting_name)  # Protected setting has next priority
    if not proxy_config:
        proxy_config = ext_settings.read_public_config(proxy_setting_name)
    if not isinstance(proxy_config, basestring):
        logger('Error: mdsdHttpProxy config is not a string. Ignored.')
    else:
        proxy_config = proxy_config.strip()
        if proxy_config:
            logger("mdsdHttpProxy setting was given and will be passed to mdsd, "
                   "but not logged here in case there's a password in it")
            return proxy_config
    return ''


def escape_nonalphanumerics(data):
    return ''.join([ch if ch.isalnum() else ":{0:04X}".format(ord(ch)) for ch in data])


# TODO Should this be placed in WAAgentUtil.py?
def get_deployment_id_from_hosting_env_cfg(waagent_dir, logger_log, logger_error):
    """
    Get deployment ID from waagent dir's HostingEnvironmentConfig.xml.

    :param waagent_dir: Waagent dir path (/var/lib/waagent)
    :param logger_log: Normal logging function (hutil.log)
    :param logger_error: Error logging function (hutil.error)
    :return: Obtained deployment ID string if the hosting env cfg xml exists & deployment ID is found.
             "unknown" if the xml exists, but deployment ID can't be found.
             None if the xml does not exist.
    """
    identity = "unknown"
    env_cfg_path = os.path.join(waagent_dir, "HostingEnvironmentConfig.xml")
    if not os.path.exists(env_cfg_path):
        logger_log("No Deployment ID (not running in a hosted environment")
        return None

    try:
        with open(env_cfg_path, 'r') as env_cfg_file:
            xml_text = env_cfg_file.read()
        dom = xml.dom.minidom.parseString(xml_text)
        deployment = dom.getElementsByTagName("Deployment")
        name = deployment[0].getAttribute("name")
        if name:
            identity = name
            logger_log("Deployment ID found: {0}.".format(identity))
    except Exception as e:
        # use fallback identity
        logger_error("Failed to retrieve deployment ID. Error:{0}\nStacktrace: {1}".format(e, traceback.format_exc()))

    return identity
