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
import re
import socket
import time

from Utils.misc_helpers import append_string_to_file

# op is either '--upgrade' or '--remove'
omsagent_universal_sh_cmd_template = 'sh omsagent-*.universal.x64.sh {op}'
# args is either '-w LAD' or '-x LAD' or '-l'
omsagent_lad_workspace_cmd_template = 'sh /opt/microsoft/omsagent/bin/omsadmin.sh {args}'
omsagent_lad_dir = '/etc/opt/microsoft/omsagent/LAD/'
# args is either 'install fluent-plugin-mdsd-*.gem' or 'uninstall fluent-plugin-mdsd -a'
fluentd_ruby_gem_cmd_template = '/opt/microsoft/omsagent/ruby/bin/fluent-gem {args}'


def setup_omsagent_for_lad(run_command):
    """
    Install omsagent by executing the universal shell bundle. Also onboard omsagent for LAD.
    Also install the out_mdsd fluentd plugin.
    :param run_command: External command execution function (e.g., RunGetOutput)
    :rtype: int, str
    :return: 2-tuple of process exit code and output (run_command's return values as is)
    """
    # 1. Install omsagent. It's a noop if it's already installed.
    cmd_exit_code, cmd_output = run_command(omsagent_universal_sh_cmd_template.format(op='--upgrade'))
    if cmd_exit_code != 0:
        return 1, 'setup_omsagent_for_lad(): omsagent universal installer shell execution failed. ' \
                  'Output: {0}'.format(cmd_output)

    # 1.1. Modify configure_syslog.sh to work around on a SLES 11 anomaly: No "syslog-ng" service, but "syslog"
    #      even though syslog-ng is installed, causing configure_syslog.sh to fail. Strange is that even though
    #      the configure_syslog.sh fails, it seems syslog collection works, so it's not really a bug, though
    #      it's just not very clean.
    run_command(r'sed -i "s/RestartService syslog-ng\\s*$/RestartService syslog-ng || RestartService syslog/g" /opt/microsoft/omsagent/bin/configure_syslog.sh')

    # 2. Onboard to LAD workspace. Should be a noop if it's already done.
    if not os.path.isdir(omsagent_lad_dir):
        cmd_exit_code, cmd_output = run_command(omsagent_lad_workspace_cmd_template.format(args='-w LAD'))
        if cmd_exit_code != 0:
            return 2, 'setup_omsagent_for_lad(): LAD workspace onboarding failed. Output: {0}'.format(cmd_output)

    # 3. Install fluentd out_mdsd plugin (uninstall existing ones first)
    run_command(fluentd_ruby_gem_cmd_template.format(args='uninstall fluent-plugin-mdsd -a'))
    cmd_exit_code, cmd_output = run_command(fluentd_ruby_gem_cmd_template.format(args='install fluent-plugin-mdsd-*.gem'))
    if cmd_exit_code != 0:
        return 3, 'setup_omsagent_for_lad(): fluentd out_mdsd plugin install failed. Output: {0}'.format(cmd_output)

    # All succeeded
    return 0, 'setup_omsagent_for_lad() succeeded'


omsagent_control_cmd_template = '/opt/microsoft/omsagent/bin/service_control {op} LAD'


def control_omsagent(op, run_command):
    """
    Start/stop/restart omsagent service using omsagent service_control script.
    :param op: Operation type. Must be 'start', 'stop', or 'restart'
    :param run_command: External command execution function (e.g., RunGetOutput)
    :rtype: int, str
    :return: 2-tuple of process exit code and output (run_command's return values as is)
    """
    cmd_exit_code, cmd_output = run_command(omsagent_control_cmd_template.format(op=op))
    if cmd_exit_code != 0:
        return 1, 'control_omsagent({0}) failed. Output: {1}'.format(op, cmd_output)
    return 0, 'control_omsagent({0}) succeeded'.format(op)


def tear_down_omsagent_for_lad(run_command, remove_omsagent):
    """
    Remove omsagent by executing the universal shell bundle. Remove LAD workspace before that.
    Don't remove omsagent if OMSAgentForLinux extension is installed (i.e., if any other omsagent workspace exists).
    :param run_command: External command execution function (e.g., RunGetOutput)
    :param remove_omsagent: A boolean indicating whether to remove omsagent bundle or not.
    :rtype: int, str
    :return: 2-tuple of process exit code and output (run_command's return values)
    """
    return_msg = ''
    # 1. Unconfigure syslog. Ignore failure (just collect failure output).
    cmd_exit_code, cmd_output = unconfigure_syslog(run_command)
    if cmd_exit_code != 0:
        return_msg += 'remove_omsagent_for_lad(): unconfigure_syslog() failed. ' \
                      'Exit code={0}, Output={1}'.format(cmd_exit_code, cmd_output)

    # 2. Remove LAD workspace. Ignore failure.
    cmd_exit_code, cmd_output = run_command(omsagent_lad_workspace_cmd_template.format(args='-x LAD'))
    if cmd_exit_code != 0:
        return_msg += 'remove_omsagent_for_lad(): LAD workspace removal failed. ' \
                      'Exit code={0}, Output={1}'.format(cmd_exit_code, cmd_output)

    if remove_omsagent:
        # 3. Uninstall omsagent when specified. Do this only if there's no other omsagent workspace.
        cmd_exit_code, cmd_output = run_command(omsagent_lad_workspace_cmd_template.format(args='-l'))
        if cmd_output.strip().lower() == 'no workspace':
            cmd_exit_code, cmd_output = run_command(omsagent_universal_sh_cmd_template.format(op='--remove'))
            if cmd_exit_code != 0:
                return_msg += 'remove_omsagent_for_lad(): remove-omsagent failed. ' \
                              'Exit code={0}, Output={1}'.format(cmd_exit_code, cmd_output)
        else:
            return_msg += 'remove_omsagent_for_lad(): omsagent workspace listing failed. ' \
                          'Exit code={0}, Output={1}'.format(cmd_exit_code, cmd_output)

    # Done
    return 0, return_msg if return_msg else 'remove_omsagent_for_lad() succeeded'


rsyslog_top_conf_path = '/etc/rsyslog.conf'
rsyslog_d_path = '/etc/rsyslog.d/'
rsyslog_d_omsagent_conf_path = '/etc/rsyslog.d/95-omsagent.conf'  # hard-coded by omsagent
syslog_ng_conf_path = '/etc/syslog-ng/syslog-ng.conf'


def is_rsyslog_installed():
    """
    Returns true iff rsyslog is installed on the machine.
    :rtype: bool
    :return: True if rsyslog is installed. False otherwise.
    """
    return os.path.exists(rsyslog_top_conf_path)


def is_new_rsyslog_installed():
    """
    Returns true iff newer version of rsyslog (that has /etc/rsyslog.d/) is installed on the machine.
    :rtype: bool
    :return: True if /etc/rsyslog.d/ exists. False otherwise.
    """
    return os.path.exists(rsyslog_d_path)


def is_syslog_ng_installed():
    """
    Returns true iff syslog-ng is installed on the machine.
    :rtype: bool
    :return: True if syslog-ng is installed. False otherwise.
    """
    return os.path.exists(syslog_ng_conf_path)


def get_syslog_ng_src_name():
    """
    Some syslog-ng distributions use different source name ("s_src" vs "src"), causing syslog-ng restarts
    to fail when we provide a non-existent source name. Need to search the syslog-ng.conf file and retrieve
    the source name as below.
    :rtype: str
    :return: syslog-ng source name retrieved from syslog-ng.conf. 'src' if none available.
    """
    syslog_ng_src_name = 'src'
    try:
        with open(syslog_ng_conf_path, 'r') as f:
            syslog_ng_cfg = f.read()
        src_match = re.search(r'\n\s*source\s+([^\s]+)\s*{', syslog_ng_cfg)
        if src_match:
            syslog_ng_src_name = src_match.group(1)
    except Exception as e:
        pass  # Ignore any errors, because the default ('src') will do.

    return syslog_ng_src_name

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


def run_omsagent_config_syslog_sh(run_command, op, port=''):
    """
    Run omsagent's configure_syslog.sh script for LAD.
    :param run_command: External command execution function (e.g., RunGetOutput)
    :param op: Type of operation. Must be one of 'configure', 'unconfigure', and 'restart'
    :param port: TCP/UDP port number to supply as fluentd in_syslog plugin listen port
    :rtype: int, str
    :return: 2-tuple of the process exit code and the resulting output string (basically run_command's return values)
    """
    return run_command(omsagent_config_syslog_sh_cmd_template.format(op=op, port=port))


fluentd_syslog_src_cfg_path = '/etc/opt/microsoft/omsagent/LAD/conf/omsagent.d/syslog.conf'
syslog_port_pattern_marker = '%SYSLOG_PORT%'


def configure_syslog(run_command, port, in_syslog_cfg, rsyslog_cfg, syslog_ng_cfg):
    """
    Configure rsyslog/syslog-ng and fluentd's in_syslog with the given TCP port.
    rsyslog/syslog-ng config is done by omsagent's configure_syslog.sh. We also try to unconfigure first,
    to avoid duplicate entries in the related config files.
    :param run_command: External command execution function (e.g., RunGetOutput)
    :param port: TCP/UDP port number to be used for rsyslog/syslog-ng and fluentd's in_syslog
    :param in_syslog_cfg: Fluentd's in_syslog config string. Should be overwritten to omsagent.d/syslog.conf
    :param rsyslog_cfg: rsyslog config that's generated by LAD syslog configurator, that should be appended to
                        /etc/rsyslog.d/95-omsagent.conf or /etc/rsyslog.conf
    :param syslog_ng_cfg: syslog-ng config that's generated by LAD syslog configurator, that should be appended to
                          /etc/syslog-ng/syslog-ng.conf
    :rtype: int, str
    :return: 2-tuple of the process exit code and the resulting output string (run_command's return values)
    """
    if not is_rsyslog_installed() and not is_syslog_ng_installed():
        return 0, 'configure_syslog(): Nothing to do: Neither rsyslog nor syslog-ng is installed on the system'

    # 1. Unconfigure existing syslog instance (if any) to avoid duplicates
    #    Continue even if this step fails (not critical)
    cmd_exit_code, cmd_output = unconfigure_syslog(run_command)
    extra_msg = ''
    if cmd_exit_code != 0:
        extra_msg = 'configure_syslog(): configure_syslog.sh unconfigure failed (still proceeding): ' + cmd_output

    # 2. Configure new syslog instance with port number.
    #    Ordering is very tricky. This must be done before modifying /etc/syslog-ng/syslog-ng.conf
    #    or /etc/rsyslog.d/95-omsagent.conf below!
    cmd_exit_code, cmd_output = run_omsagent_config_syslog_sh(run_command, 'configure', port)
    if cmd_exit_code != 0:
        return 2, 'configure_syslog(): configure_syslog.sh configure failed: ' + cmd_output

    # 2.5. Replace '%SYSLOG_PORT%' in all passed syslog configs with the obtained port number
    in_syslog_cfg = in_syslog_cfg.replace(syslog_port_pattern_marker, str(port))
    rsyslog_cfg = rsyslog_cfg.replace(syslog_port_pattern_marker, str(port))
    syslog_ng_cfg = syslog_ng_cfg.replace(syslog_port_pattern_marker, str(port))

    # 3. Configure fluentd in_syslog plugin (write the fluentd plugin config file)
    try:
        with open(fluentd_syslog_src_cfg_path, 'w') as f:
            f.write(in_syslog_cfg)
    except Exception as e:
        return 3, 'configure_syslog(): Writing to omsagent.d/syslog.conf failed: {0}'.format(e)

    # 4. Update (add facilities/levels) rsyslog or syslog-ng config
    try:
        if is_syslog_ng_installed():
            append_string_to_file(syslog_ng_cfg, syslog_ng_conf_path)
        elif is_new_rsyslog_installed():
            append_string_to_file(rsyslog_cfg, rsyslog_d_omsagent_conf_path)
        else:  # old rsyslog, so append to rsyslog_top_conf_path
            append_string_to_file(rsyslog_cfg, rsyslog_top_conf_path)
    except Exception as e:
        return 4, 'configure_syslog(): Adding facilities/levels to rsyslog/syslog-ng conf failed: {0}'.format(e)

    # 5. Restart syslog
    cmd_exit_code, cmd_output = restart_syslog(run_command)
    if cmd_exit_code != 0:
        return 5, 'configure_syslog(): Failed at restarting syslog (rsyslog or syslog-ng). ' \
                  'Exit code={0}, Output={1}'.format(cmd_exit_code, cmd_output)

    # All succeeded
    return 0, 'configure_syslog(): Succeeded. Extra message: {0}'.format(extra_msg if extra_msg else 'None')


fluentd_tail_src_cfg_path = '/etc/opt/microsoft/omsagent/LAD/conf/omsagent.d/tail.conf'


def configure_filelog(in_tail_cfg):
    """
    Configure fluentd's in_tail plugin for LAD file logging.
    :param in_tail_cfg: Fluentd's in_tail plugin cfg for LAD filelog setting (obtained from LadConfigAll obj)
    :rtype: str, int
    :return: A 2-tuple of process exit code and output
    """
    # Just needs to write to the omsagent.d/tail.conf file
    try:
        with open(fluentd_tail_src_cfg_path, 'w') as f:
            f.write(in_tail_cfg)
    except Exception as e:
        return 1, 'configure_filelog(): Failed writing fluentd in_tail config file'
    return 0, 'configure_filelog(): Succeeded writing fluentd in_tail config file'


fluentd_out_mdsd_cfg_path = '/etc/opt/microsoft/omsagent/LAD/conf/omsagent.d/z_out_mdsd.conf'


def configure_out_mdsd(out_mdsd_cfg):
    """
    Configure fluentd's out_mdsd plugin for LAD file logging.
    :param out_mdsd_cfg: Fluentd's out_mdsd plugin cfg for the entire LAD setting (obtained from LadConfigAll obj)
    :rtype: str, int
    :return: A 2-tuple of process exit code and output
    """
    # Just needs to write to the omsagent.d/tail.conf file
    try:
        with open(fluentd_out_mdsd_cfg_path, 'w') as f:
            f.write(out_mdsd_cfg)
    except Exception as e:
        return 1, 'configure_out_mdsd(): Failed writing fluentd out_mdsd config file'
    return 0, 'configure_out_mdsd(): Succeeded writing fluentd out_mdsd config file'


def unconfigure_syslog(run_command):
    """
    Unconfigure rsyslog/syslog-ng and fluentd's in_syslog for LAD. rsyslog/syslog-ng unconfig is done
    by omsagent's configure_syslog.sh.
    :param run_command: External command execution function (e.g., RunGetOutput)
    :rtype: int, str
    :return: 2-tuple of the process exit code and the resulting output string (run_command's return values)
    """
    # 1. Find the port number in fluentd's in_syslog conf..
    if not os.path.isfile(fluentd_syslog_src_cfg_path):
        return 0, "unconfigure_syslog(): Nothing to unconfigure: omsagent fluentd's in_syslog is not configured"

    # 2. Read fluentd's in_syslog config
    try:
        with open(fluentd_syslog_src_cfg_path) as f:
            fluentd_syslog_src_cfg = f.read()
    except Exception as e:
        return 1, "unconfigure_syslog(): Failed reading fluentd's in_syslog config: {0}".format(e)

    # 3. Extract the port number and run omsagent's configure_syslog.sh to unconfigure
    port_match = re.search(r'port\s+(\d+)', fluentd_syslog_src_cfg)
    if not port_match:
        return 2, 'unconfigure_syslog(): Invalid fluentd in_syslog config: port number setting not found'
    port = int(port_match.group(1))
    cmd_exit_code, cmd_output = run_omsagent_config_syslog_sh(run_command, 'unconfigure', port)
    if cmd_exit_code != 0:
        return 3, 'unconfigure_syslog(): configure_syslog.sh failed: ' + cmd_output

    # 4. Remove fluentd's in_syslog conf file
    try:
        os.remove(fluentd_syslog_src_cfg_path)
    except Exception as e:
        return 4, 'unconfigure_syslog(): Removing omsagent.d/syslog.conf failed: {0}'.format(e)

    #5. All succeeded
    return 0, 'unconfigure_syslog(): Succeeded'


def restart_syslog(run_command):
    """
    Restart rsyslog/syslog-ng (so that any new config will be applied)
    :param run_command: External command execution function (e.g., RunGetOutput)
    :rtype: int, str
    :return: 2-tuple of the process exit code and the resulting output string (run_command's return values)
    """
    return run_omsagent_config_syslog_sh(run_command, 'restart')  # port param is dummy here.


def restart_omiserver(run_command):
    """
    Restart omiserver as needed (it crashes sometimes, and doesn't restart automatically yet)
    :param run_command: External command execution function (e.g., RunGetOutput)
    :rtype: int, str
    :return: 2-tuple of the process exit code and the resulting output string (run_command's return values)
    """
    return run_command('/opt/omi/bin/service_control restart')


def setup_omsagent(configurator, run_command, logger_log, logger_error):
    """
    Set up omsagent. Install necessary components, configure them as needed, and start the agent.
    :param configurator: A LadConfigAll object that's obtained from a valid LAD JSON settings config.
                         This is needed to retrieve the syslog (rsyslog/syslog-ng) and the fluentd configs.
    :param run_command: External command executor (e.g., RunGetOutput)
    :param logger_log: Logger for normal logging messages (e.g., hutil.log)
    :param logger_error: Logger for error loggin messages (e.g., hutil.error)
    :return: Pair of status code and message. 0 status code for success. Non-zero status code
            for a failure and the associated failure message.
    """
    # Remember whether OMI (not omsagent) needs to be freshly installed.
    # This is needed later to determine whether to reconfigure the omiserver.conf or not for security purpose.
    need_fresh_install_omi = not os.path.exists('/opt/omi/bin/omiserver')

    logger_log("Begin omsagent setup.")

    # 1. Install omsagent, onboard to LAD workspace, and install fluentd out_mdsd plugin
    # We now try to install/setup all the time. If it's already installed. Any additional install is a no-op.
    is_omsagent_setup_correctly = False
    maxTries = 5  # Try up to 5 times to install omsagent
    for trialNum in range(1, maxTries + 1):
        cmd_exit_code, cmd_output = setup_omsagent_for_lad(run_command)
        if cmd_exit_code == 0:  # Successfully set up
            is_omsagent_setup_correctly = True
            break
        logger_error("omsagent setup failed (trial #" + str(trialNum) + ").")
        if trialNum < maxTries:
            logger_error("Retrying in 30 seconds...")
            time.sleep(30)
    if not is_omsagent_setup_correctly:
        logger_error("omsagent setup failed " + str(maxTries) + " times. Giving up...")
        return 1, "omsagent setup failed {0} times. " \
                  "Last exit code={1}, Output={2}".format(maxTries, cmd_exit_code, cmd_output)

    # Issue #265. OMI httpsport shouldn't be reconfigured when LAD is re-enabled or just upgraded.
    # In other words, OMI httpsport config should be updated only on a fresh OMI install.
    if need_fresh_install_omi:
        # Check if OMI is configured to listen to any non-zero port and reconfigure if so.
        omi_listens_to_nonzero_port = run_command(r"grep '^\s*httpsport\s*=' /etc/opt/omi/conf/omiserver.conf "
                                                  r"| grep -v '^\s*httpsport\s*=\s*0\s*$'")[0] is 0
        if omi_listens_to_nonzero_port:
            run_command("/opt/omi/bin/omiconfigeditor httpsport -s 0 < /etc/opt/omi/conf/omiserver.conf "
                        "> /etc/opt/omi/conf/omiserver.conf_temp")
            run_command("mv /etc/opt/omi/conf/omiserver.conf_temp /etc/opt/omi/conf/omiserver.conf")

    # 2. Configure all fluentd plugins (in_syslog, in_tail, out_mdsd)
    # 2.1. First get a free TCP/UDP port for fluentd in_syslog plugin.
    port = get_fluentd_syslog_src_port()
    if port < 0:
        return 3, 'setup_omsagent(): Failed at getting a free TCP/UDP port for fluentd in_syslog'
    # 2.2. Configure syslog
    cmd_exit_code, cmd_output = configure_syslog(run_command, port,
                                                 configurator.get_fluentd_syslog_src_config(),
                                                 configurator.get_rsyslog_config(),
                                                 configurator.get_syslog_ng_config())
    if cmd_exit_code != 0:
        return 4, 'setup_omsagent(): Failed at configuring in_syslog. Exit code={0}, Output={1}'.format(cmd_exit_code,
                                                                                                        cmd_output)
    # 2.3. Configure filelog
    cmd_exit_code, cmd_output = configure_filelog(configurator.get_fluentd_tail_src_config())
    if cmd_exit_code != 0:
        return 5, 'setup_omsagent(): Failed at configuring in_tail. Exit code={0}, Output={1}'.format(cmd_exit_code,
                                                                                                      cmd_output)
    # 2.4. Configure out_mdsd
    cmd_exit_code, cmd_output = configure_out_mdsd(configurator.get_fluentd_out_mdsd_config())
    if cmd_exit_code != 0:
        return 6, 'setup_omsagent(): Failed at configuring out_mdsd. Exit code={0}, Output={1}'.format(cmd_exit_code,
                                                                                                       cmd_output)

    # 3. Restart omsagent
    cmd_exit_code, cmd_output = control_omsagent('restart', run_command)
    if cmd_exit_code != 0:
        return 8, 'setup_omsagent(): Failed at restarting omsagent (fluentd). ' \
                  'Exit code={0}, Output={1}'.format(cmd_exit_code, cmd_output)

    # All done...
    return 0, "setup_omsagent(): Succeeded"
