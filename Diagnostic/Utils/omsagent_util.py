#!/usr/bin/env python
#
# Azure Linux extension
#
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the ""Software""), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above
# copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software. THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
#  CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

import os
import socket


def is_rsyslog_installed():
    """
    Returns true iff rsyslog is installed on the machine.
    :rtype: bool
    :return: True if rsyslog is installed. False otherwise.
    """
    return os.path.exists('/etc/rsyslog.conf')


def is_syslog_ng_installed():
    """
    Returns true iff syslog-ng is installed on the machine.
    :rtype: bool
    :return: True if syslog-ng is installed. False otherwise.
    """
    return os.path.exists('/etc/syslog-ng/syslog-ng.conf')


def get_fluentd_syslog_src_port():
    """
    Returns a TCP/UDP port number that'll be supplied to the fluentd syslog src plugin (for it to listen to for
    syslog events from rsyslog/syslog-ng). Ports from 25224 to 25423 will be tried for bind() and the first available
    one will be returned. 25224 is the default port number that's picked by omsagent.
    
    This is definitely not 100% correct with potential races. The correct solution would be to let fluentd syslog
    src plugin bind to 0 and write the resulting bound port number to a file, so that we can get the port number
    from the file. However, the current fluentd in_syslog.rb doesn't write to a file, so that method won't
    work. And yet we still want to minimize possibility of binding to an already-in-use port, so here's a workaround.
    :rtype: int
    :return: A successfully bound (& closed) TCP/UDP port number. -1 if all failed.
    """
    for port in range(25224, 25424):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('', port))
            s.close()
            return port
        except Exception as e:
            pass
    return -1


omsagent_config_syslog_sh_cmd_template = 'sh /opt/microsoft/omsagent/bin/configure_syslog.sh {op} LAD {port}'


def run_omsagent_config_syslog_sh(run_command, op, port):
    """
    Run omsagent's configure_syslog.sh script for LAD.
    :param run_command: External command execution function (e.g., RunGetOutput)
    :param op: Type of operation. Must be one of 'configure', 'unconfigure', and 'restart'
    :param port: TCP/UDP port number to supply as fluentd in_syslog plugin listen port
    :rtype: int, str
    :return: 2-tuple of the process exit code and the resulting output string (basically run_command's return value)
    """
    return run_command(omsagent_config_syslog_sh_cmd_template.format(op=op, port=port))


# Convenience wrappers for run_omsagent_config_syslog_sh()
def configure_syslog(run_command, port):
    return run_omsagent_config_syslog_sh(run_command, 'configure', port)


def unconfigure_syslog(run_command, port):
    # TODO port here should be automatically obtained by checking /etc/opt/microsoft/omsagent/LAD/conf/omsagent.d/syslog.conf
    # (extract the port number from '  port <...>' line)
    return run_omsagent_config_syslog_sh(run_command, 'unconfigure', port)


def restart_syslog(run_command):
    return run_omsagent_config_syslog_sh(run_command, 'restart')