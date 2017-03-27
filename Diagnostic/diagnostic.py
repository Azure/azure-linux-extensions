#!/usr/bin/env python
#
# Azure Linux extension
#
# Linux Azure Diagnostic Extension (Current version is specified in manifest.xml)
# Copyright (c) Microsoft Corporation All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the ""Software""), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following
# conditions: The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software. THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import datetime
import exceptions
import os
import os.path
import platform
import signal
import subprocess
import sys
import syslog
import threading
import time
import traceback
import xml.etree.ElementTree as ET

# Just wanted to be able to run 'python diagnostic.py ...' from a local dev box where there's no waagent.
# Also for any potential local imports that may throw, let's do try-except here on them.
try:
    # waagent, ext handler
    from Utils.WAAgentUtil import waagent
    import Utils.HandlerUtil as Util

    # Old LAD utils
    import Utils.ApplicationInsightsUtil as AIUtil
    import Utils.LadDiagnosticUtil as LadUtil
    import Utils.XmlUtil as XmlUtil

    # New LAD  utils
    import DistroSpecific
    import watcherutil
    from Utils.lad_ext_settings import LadExtSettings
    from misc_helpers import *
    from lad_config_all import *
    from Utils.imds_util import ImdsLogger
except Exception as e:
    print 'A local import (e.g., waagent) failed. Exception: {0}\n' \
          'Stacktrace: {1}'.format(e, traceback.format_exc())
    print "Can't proceed. Exiting with a special exit code 999."
    sys.exit(999)  # This is the only thing we can do, as all logging depends on waagent/hutil.


# Globals declaration/initialization (with const values only) for IDE
g_ext_settings = None  # LAD extension settings object
g_lad_log_helper = None  # LAD logging helper object
g_dist_config = None  # Distro config object
g_enable_syslog = True  # EnableSyslog flag
g_ext_dir = ''  # Extension directory (e.g., /var/lib/waagent/Microsoft.OSTCExtensions.LinuxDiagnostic-x.y.zzzz)
g_mdsd_file_resources_dir = '/var/run/mdsd'
g_mdsd_role_name = 'lad_mdsd'  # Different mdsd role name for multiple mdsd process instances
g_mdsd_file_resources_prefix = ''  # Eventually '/var/run/mdsd/lad_mdsd'
g_lad_pids_filepath = ''  # LAD process IDs (diagnostic.py, mdsd) file path. g_ext_dir + '/lad.pids'
g_ext_op_type = None  # Extension operation type (e.g., Install, Enable, HeartBeat, ...)
g_mdsd_bin_dir = ''  # mdsd binary directory. g_ext_dir + '/bin'
g_diagnostic_py_filepath = ''  # Full path of this script. g_ext_dir + '/diagnostic.py'
g_imfile_config_filename = ''  # Generated rsyslog imfile config file name (not full path)
# Only 2 globals not following 'g_...' naming convention, for legacy readability...
RunGetOutput = None  # External command executor callable
hutil = None  # Handler util object


def init_distro_specific_actions():
    """
    Identify the specific Linux distribution in use. Set the global distConfig to point to the corresponding
    implementation class. If the distribution isn't supported, set the extension status appropriately and exit.
    Expects the global hutil to already be initialized.
    """
    # TODO Exit immediately if distro is unknown
    global g_dist_config, RunGetOutput
    dist = platform.dist()
    distroNameAndVersion = dist[0] + ":" + dist[1]
    try:
        g_dist_config = DistroSpecific.get_distro_actions(dist[0], dist[1], hutil.log)
        RunGetOutput = g_dist_config.log_run_get_output
    except exceptions.LookupError as ex:
        hutil.error("os version:" + distroNameAndVersion + " not supported")
        # TODO Exit immediately if distro is unknown. This is currently done in main().
        g_dist_config = None


def init_extension_settings():
    """Initialize extension's public & private settings. hutil must be already initialized prior to calling this."""
    global g_ext_settings

    # Need to read/parse the Json extension settings (context) first.
    hutil.try_parse_context()
    hutil.set_verbose_log(False)  # This is default, but this choice will be made explicit and logged.

    g_ext_settings = LadExtSettings(hutil.get_handler_settings())


def init_globals():
    """Initialize all the globals in a function so that we can catch any exceptions that might be raised."""
    global hutil, g_ext_dir, g_mdsd_file_resources_prefix, g_lad_pids_filepath
    global g_mdsd_bin_dir, g_diagnostic_py_filepath, g_imfile_config_filename
    global g_lad_log_helper

    waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
    waagent.Log("LinuxAzureDiagnostic started to handle.")
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    init_extension_settings()
    init_distro_specific_actions()

    g_ext_dir = os.getcwd()
    g_mdsd_file_resources_prefix = os.path.join(g_mdsd_file_resources_dir, g_mdsd_role_name)
    g_lad_pids_filepath = os.path.join(g_ext_dir, 'lad.pids')
    g_mdsd_bin_dir = os.path.join(g_ext_dir, 'bin')
    g_diagnostic_py_filepath = os.path.join(os.getcwd(), __file__)
    g_imfile_config_filename = os.path.join(g_ext_dir, 'imfileconfig')
    g_lad_log_helper = LadLogHelper(hutil.log, hutil.error, waagent.AddExtensionEvent, hutil.do_status_report,
                                    hutil.get_name(), hutil.get_extension_version())


def setup_dependencies_and_mdsd():
    """
    Set up dependencies for mdsd, such as following:
    1) Distro-specific packages (see DistroSpecific.py)
    2) Set up rsyslog for mdsd
    3) Set up OMI
    :return: Status code and message
    """
    install_package_error = ""
    retry = 3
    while retry > 0:
        error, msg = g_dist_config.install_required_packages()
        hutil.log(msg)
        if error == 0:
            break
        else:
            retry -= 1
            hutil.log("Sleep 60 retry " + str(retry))
            install_package_error = msg
            time.sleep(60)
    if install_package_error:
        if len(install_package_error) > 1024:
            install_package_error = install_package_error[0:512] + install_package_error[-512:-1]
        hutil.error(install_package_error)
        return 2, install_package_error

    error, msg = setup_rsyslog_for_mdsd()
    if error != 0:
        hutil.error(msg)
        return 3, msg

    # Run mdsd prep commands
    g_dist_config.prepare_for_mdsd_install()

    # Install/start OMI
    omi_err, omi_msg = setup_omi()
    if omi_err is not 0:
        return 4, omi_msg

    return 0, 'success'


def install_lad_as_systemd_service():
    """
    Install LAD as a systemd service on systemd-enabled distros/versions (e.g., Ubuntu 16.04)
    :return: None
    """
    RunGetOutput('sed s#{WORKDIR}#' + g_ext_dir + '# ' +
                 g_ext_dir + '/services/mdsd-lde.service > /lib/systemd/system/mdsd-lde.service')
    RunGetOutput('systemctl daemon-reload')


def create_core_components_configs():
    """
    Entry point to creating all configs of LAD's core components (mdsd, omsagent, rsyslog/syslog-ng, ...).
    This function shouldn't be called on Install/Enable. Only Daemon op needs to call this.
    :rtype: bool
    :return: True if and only if all configs are created correctly.
    """
    global g_enable_syslog

    g_enable_syslog = g_ext_settings.is_syslog_enabled()

    deployment_id = get_deployment_id_from_hosting_env_cfg(waagent.LibDir, hutil.log, hutil.error)
    mdsd_rsyslog_configurator = LadConfigAll(g_ext_settings, g_ext_dir, waagent.LibDir, deployment_id,
                                             RunGetOutput, hutil.log, hutil.error)
    config_valid, config_invalid_reason = mdsd_rsyslog_configurator.generate_mdsd_omsagent_syslog_configs()
    if not config_valid:
        config_invalid_log = "Invalid config settings given: " + config_invalid_reason + \
                             ". Can't proceed, but this will be still considered a success as it's an external error."
        hutil.log(config_invalid_log)
        hutil.do_status_report(g_ext_op_type, "success", '0', config_invalid_log)
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=g_ext_op_type,
                                  isSuccess=True,
                                  version=hutil.get_extension_version(),
                                  message=config_invalid_log)
    return config_valid


def check_for_supported_waagent_and_distro_version():
    """
    Checks & returns if the installed waagent and the Linux distro/version are supported by this LAD.
    :rtype: bool
    :return: True iff so.
    """
    for notsupport in ('WALinuxAgent-2.0.5', 'WALinuxAgent-2.0.4', 'WALinuxAgent-1'):
        code, str_ret = waagent.RunGetOutput("grep 'GuestAgentVersion.*" + notsupport + "' /usr/sbin/waagent",
                                             chk_err=False)
        if code == 0 and str_ret.find(notsupport) > -1:
            hutil.log("cannot run this extension on  " + notsupport)
            hutil.do_status_report(g_ext_op_type, "error", '1', "cannot run this extension on  " + notsupport)
            return False

    if g_dist_config is None:
        msg = ("LAD does not support distro/version ({0}); not installed. This extension install/enable operation is "
               "still considered a success as it's an external error.").format(str(platform.dist()))
        hutil.log(msg)
        hutil.do_status_report(g_ext_op_type, "success", '0', msg)
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=g_ext_op_type,
                                  isSuccess=True,
                                  version=hutil.get_extension_version(),
                                  message="Can't be installed on this OS " + str(platform.dist()))
        return False

    return True


def main(command):
    init_globals()

    global g_ext_op_type

    g_ext_op_type = get_extension_operation_type(command)

    if not check_for_supported_waagent_and_distro_version():
        return

    try:
        hutil.log("Dispatching command:" + command)

        if g_ext_op_type is waagent.WALAEventOperation.Disable:
            if g_dist_config.use_systemd():
                RunGetOutput('systemctl stop mdsd-lde && systemctl disable mdsd-lde')
            else:
                stop_mdsd()
            hutil.do_status_report(g_ext_op_type, "success", '0', "Disable succeeded")

        elif g_ext_op_type is waagent.WALAEventOperation.Uninstall:
            if g_dist_config.use_systemd():
                RunGetOutput('systemctl stop mdsd-lde && systemctl disable mdsd-lde ' +
                             '&& rm /lib/systemd/system/mdsd-lde.service')
            else:
                stop_mdsd()
            tear_down_omi()
            tear_down_mdsd_rsyslog_setup(condition=g_enable_syslog)
            hutil.do_status_report(g_ext_op_type, "success", '0', "Uninstall succeeded")

        elif g_ext_op_type is waagent.WALAEventOperation.Install:
            if g_dist_config.use_systemd():
                install_lad_as_systemd_service()
            hutil.do_status_report(g_ext_op_type, "success", '0', "Install succeeded")

        elif g_ext_op_type is waagent.WALAEventOperation.Enable:
            if g_dist_config.use_systemd():
                install_lad_as_systemd_service()
                RunGetOutput('systemctl enable mdsd-lde')
                mdsd_lde_active = RunGetOutput('systemctl status mdsd-lde')[0] is 0
                if not mdsd_lde_active or hutil.is_current_config_seq_greater_inused():
                    RunGetOutput('systemctl restart mdsd-lde')
            else:
                # if daemon process not runs
                lad_pids = get_lad_pids()
                hutil.log("get pids:" + str(lad_pids))
                if len(lad_pids) != 2 or hutil.is_current_config_seq_greater_inused():
                    stop_mdsd()
                    start_daemon()
            hutil.set_inused_config_seq(hutil.get_seq_no())
            hutil.do_status_report(g_ext_op_type, "success", '0', "Enable succeeded")

        elif g_ext_op_type is "Daemon":
            if create_core_components_configs():
                start_mdsd()

        elif g_ext_op_type is waagent.WALAEventOperation.Update:
            hutil.do_status_report(g_ext_op_type, "success", '0', "Update succeeded")

    except Exception as e:
        hutil.error("Failed to perform extension operation {0} with error:{1}, {2}".format(g_ext_op_type, e,
                                                                                           traceback.format_exc()))
        hutil.do_status_report(g_ext_op_type, 'error', '0',
                               'Extension operation {0} failed:{1}'.format(g_ext_op_type, e))


def start_daemon():
    """
    Start diagnostic.py as a daemon for long running mdsd and its monitoring
    :return: None
    """
    args = ['python', g_diagnostic_py_filepath, "-daemon"]
    log = open(os.path.join(os.getcwd(), 'daemon.log'), 'w')
    hutil.log('start daemon ' + str(args))
    subprocess.Popen(args, stdout=log, stderr=log)
    wait_n = 20
    while len(get_lad_pids()) == 0 and wait_n > 0:
        time.sleep(5)
        wait_n -= 1
    if wait_n <= 0:
        hutil.error("wait daemon start time out")


def start_watcher_thread():
    """
    Start watcher thread that performs periodic monitoring activities (other than mdsd)
    :return: None
    """
    # Create monitor object that encapsulates monitoring activities
    watcher = watcherutil.Watcher(hutil.error, hutil.log, log_to_console=True)
    # Create an IMDS data logger and set it to the monitor object
    imds_logger = ImdsLogger(hutil.get_name(), hutil.get_extension_version(),
                             waagent.WALAEventOperation.HeartBeat, waagent.AddExtensionEvent)
    watcher.set_imds_logger(imds_logger)
    # Start a thread to perform periodic monitoring activity (e.g., /etc/fstab watcher, IMDS data logging)
    thread_obj = threading.Thread(target=watcher.watch)
    thread_obj.daemon = True
    thread_obj.start()


def start_mdsd():
    """
    Start mdsd and monitor its activities. Report if it crashes or emits error logs.
    :return: None
    """

    # Need 'HeartBeat' instead of 'Daemon'
    waagent_ext_event_type = wala_event_type_for_telemetry(g_ext_op_type)

    # We first validate the mdsd config and proceed only when it succeeds.
    xml_file = os.path.join(g_ext_dir, './xmlCfg.xml')
    config_validate_cmd = '{0} -v -c {1}'.format(os.path.join(g_mdsd_bin_dir, "mdsd"), xml_file)
    config_validate_cmd_status, config_validate_cmd_msg = RunGetOutput(config_validate_cmd)
    if config_validate_cmd_status is not 0:
        # Invalid config. Log error and report success.
        message = "Invalid mdsd config given. Can't enable. This extension install/enable operation is reported as " \
            "successful so the VM can complete successful startup. Linux Diagnostic Extension will exit. " \
            "Config validation message: {0}.".format(config_validate_cmd_msg)
        hutil.log(message)
        hutil.do_status_report(waagent_ext_event_type, "success", '0', message)
        return

    write_lad_pids_to_file(g_lad_pids_filepath, os.getpid())

    dependencies_err, dependencies_msg = setup_dependencies_and_mdsd()
    if dependencies_err != 0:
        g_lad_log_helper.report_mdsd_dependency_setup_failure(waagent_ext_event_type, dependencies_msg)
        return

    # Start OMI if it's not running.
    # This shouldn't happen, but this measure is put in place just in case (e.g., Ubuntu 16.04 systemd).
    # Don't check if starting succeeded, as it'll be done in the loop below anyway.
    omi_running = RunGetOutput("/opt/omi/bin/service_control is-running")[0] is 1
    if not omi_running:
        RunGetOutput("/opt/omi/bin/service_control restart")

    tear_down_mdsd_rsyslog_setup(condition=not g_enable_syslog)

    log_dir = hutil.get_log_dir()
    err_file_path = os.path.join(log_dir, 'mdsd.err')
    info_file_path = os.path.join(log_dir, 'mdsd.info')
    warn_file_path = os.path.join(log_dir, 'mdsd.warn')

    update_selinux_settings_for_rsyslogomazuremds(RunGetOutput, g_ext_dir)

    mdsd_stdout_redirect_path = os.path.join(g_ext_dir, "mdsd.log")
    mdsd_stdout_stream = None
    copy_env = os.environ
    copy_env['LD_LIBRARY_PATH'] = g_mdsd_bin_dir
    g_dist_config.extend_environment(copy_env)

    # mdsd http proxy setting
    proxy_config = get_mdsd_proxy_config(waagent.HttpProxyConfigString, g_ext_settings, hutil.log)
    if proxy_config:
        copy_env['MDSD_http_proxy'] = proxy_config

    # Now prepare actual mdsd cmdline.
    command = '{0} -A -C -c {1} -R -r {2} -e {3} -w {4} -o {5}'.format(
        os.path.join(g_mdsd_bin_dir, "mdsd"),
        xml_file,
        g_mdsd_role_name,
        err_file_path,
        warn_file_path,
        info_file_path).split(" ")

    try:
        start_watcher_thread()

        num_quick_consecutive_crashes = 0
        mdsd_crash_msg = ''

        while num_quick_consecutive_crashes < 3:  # We consider only quick & consecutive crashes for retries

            RunGetOutput('rm -f ' + g_mdsd_file_resources_prefix + '.pidport')  # Must delete any existing port num file
            mdsd_stdout_stream = open(mdsd_stdout_redirect_path, "w")
            hutil.log("Start mdsd " + str(command))
            mdsd = subprocess.Popen(command,
                                    cwd=g_ext_dir,
                                    stdout=mdsd_stdout_stream,
                                    stderr=mdsd_stdout_stream,
                                    env=copy_env)

            write_lad_pids_to_file(g_lad_pids_filepath, os.getpid(), mdsd.pid)

            last_mdsd_start_time = datetime.datetime.now()
            last_error_time = last_mdsd_start_time
            omi_installed = True  # Remembers if OMI is installed at each iteration
            # Continuously monitors mdsd process
            while True:
                time.sleep(30)
                if " ".join(get_lad_pids()).find(str(mdsd.pid)) < 0 and len(get_lad_pids()) >= 2:
                    mdsd.kill()
                    hutil.log("Another process is started, now exit")
                    return
                if mdsd.poll() is not None:  # if mdsd has terminated
                    time.sleep(60)
                    mdsd_stdout_stream.flush()
                    break

                # mdsd is now up for at least 30 seconds. Do some monitoring activities.
                # 1. Mitigate if memory leak is suspected.
                mdsd_memory_leak_suspected, mdsd_memory_usage_in_KB = check_suspected_memory_leak(mdsd.pid, hutil.error)
                if mdsd_memory_leak_suspected:
                    g_lad_log_helper.log_suspected_memory_leak_and_kill_mdsd(mdsd_memory_usage_in_KB, mdsd,
                                                                             waagent_ext_event_type)
                    break
                # 2. Restart OMI if it crashed (Issue #128)
                omi_installed = restart_omi_if_crashed(omi_installed, mdsd)
                # 3. Check if there's any new logs in mdsd.err and report
                last_error_time = report_new_mdsd_errors(err_file_path, last_error_time)

            # Out of the inner while loop: mdsd terminated.
            if mdsd_stdout_stream:
                mdsd_stdout_stream.close()
                mdsd_stdout_stream = None

            # Check if this is NOT a quick crash -- we consider a crash quick
            # if it's within 30 minutes from the start time. If it's not quick,
            # we just continue by restarting mdsd.
            mdsd_up_time = datetime.datetime.now() - last_mdsd_start_time
            if mdsd_up_time > datetime.timedelta(minutes=30):
                mdsd_terminated_msg = "MDSD terminated after " + str(mdsd_up_time) + ". "\
                                      + tail(mdsd_stdout_redirect_path) + tail(err_file_path)
                hutil.log(mdsd_terminated_msg)
                num_quick_consecutive_crashes = 0
                continue

            # It's a quick crash. Log error and add an extension event.
            num_quick_consecutive_crashes += 1

            mdsd_crash_msg = "MDSD crash(uptime=" + str(mdsd_up_time) + "):" + tail(mdsd_stdout_redirect_path) + tail(err_file_path)
            hutil.error("MDSD crashed:" + mdsd_crash_msg)

            # Need to reset rsyslog omazurelinuxmds config before retrying mdsd if it was set up earlier
            setup_rsyslog_for_mdsd()

        # mdsd all 3 allowed quick/consecutive crashes exhausted
        hutil.do_status_report(waagent_ext_event_type, "error", '1', "mdsd stopped:" + mdsd_crash_msg)
        # Also need to tear down rsyslog-mdsd OM before returning/exiting if it was set up earlier
        tear_down_mdsd_rsyslog_setup(condition=g_enable_syslog)
        try:
            waagent.AddExtensionEvent(name=hutil.get_name(),
                                      op=waagent_ext_event_type,
                                      isSuccess=False,
                                      version=hutil.get_extension_version(),
                                      message=mdsd_crash_msg)
        except Exception:
            pass

    except Exception as e:
        if mdsd_stdout_stream:
            hutil.error("Error :" + tail(mdsd_stdout_redirect_path))
        hutil.error(("Failed to launch mdsd with error:{0},"
                     "stacktrace:{1}").format(e, traceback.format_exc()))
        hutil.do_status_report(waagent_ext_event_type, 'error', '1', 'Launch script failed:{0}'.format(e))
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=waagent_ext_event_type,
                                  isSuccess=False,
                                  version=hutil.get_extension_version(),
                                  message="Launch script failed:" + str(e))
    finally:
        if mdsd_stdout_stream:
            mdsd_stdout_stream.close()


def report_new_mdsd_errors(err_file_path, last_error_time):
    """
    Monitors if there's any new stuff in mdsd.err and report it if any through the agent/ext status report mechanism.
    :param err_file_path: Path of the mdsd.err file
    :param last_error_time: Time when last error was reported.
    :return: Time when the last error was reported. Same as the argument if there's no error reported in this call.
             A new time (error file ctime) if a new error is reported.
    """
    if not os.path.exists(err_file_path):
        return last_error_time
    err_file_ctime = datetime.datetime.strptime(time.ctime(int(os.path.getctime(err_file_path))), "%a %b %d %H:%M:%S %Y")
    if last_error_time >= err_file_ctime:
        return last_error_time
    # No new error above. A new error below.
    last_error_time = err_file_ctime
    last_error = tail(err_file_path)
    if len(last_error) > 0 and (datetime.datetime.now() - last_error_time) < datetime.timedelta(minutes=30):
        # Only recent error logs (within 30 minutes) are reported.
        hutil.log("Error in MDSD:" + last_error)
        hutil.do_status_report(g_ext_op_type, "success", '1',
                               "message in mdsd.err:" + str(last_error_time) + ":" + last_error)
    return last_error_time


def stop_mdsd():
    """
    Stop mdsd process
    :return: None
    """
    pids = get_lad_pids()
    if not pids:
        return 0, "Already stopped"

    kill_cmd = "kill " + " ".join(pids)
    hutil.log(kill_cmd)
    RunGetOutput(kill_cmd)

    terminated = False
    num_checked = 0
    while not terminated and num_checked < 10:
        time.sleep(2)
        num_checked += 1
        pids = get_lad_pids()
        if not pids:
            hutil.log("stop_mdsd(): All processes successfully terminated")
            terminated = True
        else:
            hutil.log("stop_mdsd() terminate check #{0}: Processes not terminated yet, rechecking in 2 seconds".format(
                num_checked))

    if not terminated:
        kill_cmd = "kill -9 " + " ".join(get_lad_pids())
        hutil.log("stop_mdsd(): Processes not terminated in 20 seconds. Sending SIGKILL (" + kill_cmd + ")")
        RunGetOutput(kill_cmd)

    RunGetOutput("rm " + g_lad_pids_filepath)

    return 0, "Terminated" if terminated else "SIGKILL'ed"


def get_lad_pids():
    """
    Get LAD PIDs from the previously written file
    :return: List of 2 PIDs. One for diagnostic.py, the other for mdsd
    """
    lad_pids = []
    if not os.path.exists(g_lad_pids_filepath):
        return lad_pids

    with open(g_lad_pids_filepath, "r") as f:
        for pid in f.readlines():
            is_still_alive = waagent.RunGetOutput("cat /proc/" + pid.strip() + "/cmdline", chk_err=False)[1]
            if is_still_alive.find('/waagent/') > 0:
                lad_pids.append(pid.strip())
            else:
                hutil.log("return not alive " + is_still_alive.strip())
    return lad_pids


def setup_omi():
    """
    Set up OMI. Install necessary components, configure them as needed, and start OMI
    :return: Pair of status code and message. 0 status code for success. Non-zero status code
            for a failure and the associated failure message.
    """
    need_fresh_install_omi = not os.path.exists('/opt/omi/bin/omiserver')

    isMysqlInstalled = RunGetOutput("which mysql")[0] is 0
    isApacheInstalled = RunGetOutput("which apache2 || which httpd || which httpd2")[0] is 0

    # Explicitly uninstall apache-cimprov & mysql-cimprov on rpm-based distros
    # to avoid hitting the scx upgrade issue (from 1.6.2-241 to 1.6.2-337)
    omi_version = RunGetOutput('/opt/omi/bin/omiserver -v', should_log=False)[1]
    if 'OMI-1.0.8-4' in omi_version and g_dist_config.is_package_handler('rpm'):
        RunGetOutput('rpm --erase apache-cimprov', should_log=False)
        RunGetOutput('rpm --erase mysql-cimprov', should_log=False)

    need_install_omi = ('OMI-1.0.8-6' not in omi_version) \
        or (isMysqlInstalled and not os.path.exists("/opt/microsoft/mysql-cimprov")) \
        or (isApacheInstalled and not os.path.exists("/opt/microsoft/apache-cimprov"))

    if need_install_omi:
        hutil.log("Begin omi installation.")
        is_omi_installed_correctly = False
        maxTries = 5  # Try up to 5 times to install OMI
        for trialNum in range(1, maxTries + 1):
            is_omi_installed_correctly = g_dist_config.install_omi() is 0
            if is_omi_installed_correctly:
                break
            hutil.error("OMI install failed (trial #" + str(trialNum) + ").")
            if trialNum < maxTries:
                hutil.error("Retrying in 30 seconds...")
                time.sleep(30)
        if not is_omi_installed_correctly:
            hutil.error("OMI install failed " + str(maxTries) + " times. Giving up...")
            return 1, "OMI install failed " + str(maxTries) + " times"

    shouldRestartOmi = False

    # Issue #265. OMI httpsport shouldn't be reconfigured when LAD is re-enabled or just upgraded.
    # In other words, OMI httpsport config should be updated only on a fresh OMI install.
    if need_fresh_install_omi:
        # Check if OMI is configured to listen to any non-zero port and reconfigure if so.
        omi_listens_to_nonzero_port = RunGetOutput(
            r"grep '^\s*httpsport\s*=' /etc/opt/omi/conf/omiserver.conf | grep -v '^\s*httpsport\s*=\s*0\s*$'")[0] is 0
        if omi_listens_to_nonzero_port:
            RunGetOutput(
                "/opt/omi/bin/omiconfigeditor httpsport -s 0 < /etc/opt/omi/conf/omiserver.conf > /etc/opt/omi/conf/omiserver.conf_temp")
            RunGetOutput("mv /etc/opt/omi/conf/omiserver.conf_temp /etc/opt/omi/conf/omiserver.conf")
            shouldRestartOmi = True

    # Quick and dirty way of checking if mysql/apache process is running
    isMysqlRunning = RunGetOutput("ps -ef | grep mysql | grep -v grep")[0] is 0
    isApacheRunning = RunGetOutput("ps -ef | grep -E 'httpd|apache2' | grep -v grep")[0] is 0

    if os.path.exists("/opt/microsoft/mysql-cimprov/bin/mycimprovauth") and isMysqlRunning:
        mysqladdress = g_ext_settings.read_protected_config("mysqladdress")
        mysqlusername = g_ext_settings.read_protected_config("mysqlusername")
        mysqlpassword = g_ext_settings.read_protected_config("mysqlpassword")
        RunGetOutput(
            "/opt/microsoft/mysql-cimprov/bin/mycimprovauth default " + mysqladdress + " " + mysqlusername + " '" + mysqlpassword + "'",
            should_log=False)
        shouldRestartOmi = True

    if os.path.exists("/opt/microsoft/apache-cimprov/bin/apache_config.sh") and isApacheRunning:
        RunGetOutput("/opt/microsoft/apache-cimprov/bin/apache_config.sh -c")
        shouldRestartOmi = True

    if shouldRestartOmi:
        RunGetOutput("/opt/omi/bin/service_control restart")

    return 0, "omi installed"


def tear_down_omi():
    """
    Tear down OMI. We currently don't uninstall OMI, but just uninstalls Apache CIM provider if it's installed.
    Later, we may want to at least stop OMI server, if not uninstalling OMI.
    :return: status code (0 for success), and message
    """
    isApacheRunning = RunGetOutput("ps -ef | grep -E 'httpd|apache' | grep -v grep")[0] is 0
    if os.path.exists("/opt/microsoft/apache-cimprov/bin/apache_config.sh") and isApacheRunning:
        RunGetOutput("/opt/microsoft/apache-cimprov/bin/apache_config.sh -u")
    hutil.log("omi will not be uninstalled")
    return 0, "do nothing"


# Issue #128 LAD should restart OMI if it crashes
def restart_omi_if_crashed(omi_installed, mdsd):
    """
    Restart OMI if it crashed. Called from the main monitoring loop.
    :param omi_installed: bool indicating whether OMI was installed at the previous iteration.
    :param mdsd: Python Process object for the mdsd process, because it might need to be signaled.
    :return: bool indicating whether OMI was installed at this iteration (from this call)
    """
    omicli_path = "/opt/omi/bin/omicli"
    omicli_noop_query_cmd = omicli_path + " noop"
    omi_was_installed = omi_installed  # Remember the OMI install status from the last iteration
    omi_installed = os.path.isfile(omicli_path)

    if omi_was_installed and not omi_installed:
        hutil.log("OMI is uninstalled. This must have been intentional and externally done. "
                  "Will no longer check if OMI is up and running.")

    omi_reinstalled = not omi_was_installed and omi_installed
    if omi_reinstalled:
        hutil.log("OMI is reinstalled. Will resume checking if OMI is up and running.")

    should_restart_omi = False
    if omi_installed:
        cmd_exit_status, cmd_output = RunGetOutput(cmd=omicli_noop_query_cmd, should_log=False)
        should_restart_omi = cmd_exit_status is not 0
        if should_restart_omi:
            hutil.error("OMI noop query failed. Output: " + cmd_output + ". OMI crash suspected. "
                        "Restarting OMI and sending SIGHUP to mdsd after 5 seconds.")
            omi_restart_msg = RunGetOutput("/opt/omi/bin/service_control restart")[1]
            hutil.log("OMI restart result: " + omi_restart_msg)
            time.sleep(5)

    # mdsd needs to be signaled if OMI was restarted or reinstalled because mdsd used to give up connecting to OMI
    # if it fails first time, and never retried until signaled. mdsd was fixed to retry now, but it's still
    # limited (stops retrying beyond 30 minutes or so) and backoff-ed exponentially
    # so it's still better to signal anyway.
    should_signal_mdsd = should_restart_omi or omi_reinstalled
    if should_signal_mdsd:
        omi_up_and_running = RunGetOutput(omicli_noop_query_cmd)[0] is 0
        if omi_up_and_running:
            mdsd.send_signal(signal.SIGHUP)
            hutil.log("SIGHUP sent to mdsd")
        else:  # OMI restarted but not staying up...
            log_msg = "OMI restarted but not staying up. Will be restarted in the next iteration."
            hutil.error(log_msg)
            # Also log this issue on syslog as well
            syslog.openlog('diagnostic.py', syslog.LOG_PID,
                           syslog.LOG_DAEMON)  # syslog.openlog(ident, logoption, facility) -- not taking kw args in Python 2.6
            syslog.syslog(syslog.LOG_ALERT,
                          log_msg)  # syslog.syslog(priority, message) -- not taking kw args
            syslog.closelog()

    return omi_installed


# Rsyslog config-related globals (config file paths)
g_rsyslog_om_mdsd_conf_path = "/etc/rsyslog.d/10-omazurelinuxmds.conf"
g_rsyslog_im_file_conf_path = "/etc/rsyslog.d/10-omazurelinuxmds-imfile.conf"


def setup_rsyslog_for_mdsd():
    """
    Set up rsyslog for mdsd by doing the following:
    1) Install rsyslog mdsd output module
    2) Configure rsyslog mdsd output module (Update __MDSD_SOCKET_FILE_PTAH__ in the config template)
    3) Configure rsyslog imfile module (By copying the already-cooked imfileconfig to rsyslog.d)
    4) Restart rsyslog
    :return: Status code (0 for success, non-zero for failure), message
    """

    # Don't bother to set up rsyslog for mdsd if syslog is not enabled.
    if not g_enable_syslog:
        return 0, 'syslog is not enabled'

    rsyslog_om_path, rsyslog_version = g_dist_config.get_rsyslog_info()
    if rsyslog_om_path is None:
        return 1, "rsyslog not installed"

    if rsyslog_version == '':
        return 1, "rsyslog version can't be detected"
    elif rsyslog_version not in ('5', '7', '8'):
        return 1, "Unsupported rsyslog version ({0})".format(rsyslog_version)

    rsyslog_om_folder = 'rsyslog' + rsyslog_version
    mdsd_socket_path = g_mdsd_file_resources_prefix + "_json.socket"

    script = """\
cp -f {0}/omazuremds.so {1};\
rm -f /etc/rsyslog.d/omazurelinuxmds.conf /etc/rsyslog.d/omazurelinuxmds_fileom.conf {2};\
cp -f {3} {4};\
sed 's#__MDSD_SOCKET_FILE_PATH__#{5}#g' {0}/omazurelinuxmds.conf > {2}"""
    cmd = script.format(rsyslog_om_folder, rsyslog_om_path, g_rsyslog_om_mdsd_conf_path,
                        g_imfile_config_filename, g_rsyslog_im_file_conf_path, mdsd_socket_path)
    RunGetOutput(cmd)

    g_dist_config.restart_rsyslog()
    return 0, "Setting up rsyslog for mdsd completed"


def tear_down_mdsd_rsyslog_setup(condition):
    """
    Tear down mdsd-related rsyslog setup by doing the following:
    1) Remove mdsd rsyslog output module binary, config, and imfile config for mdsd destination
    2) Restart rsyslog
    :return: Status code and message
    """
    # Don't bother to proceed if the passed condition is not met
    if not condition:
        return 0, 'rsyslog OM uninstall condition is not met. Not proceeding.'

    rsyslog_om_path, rsyslog_version = g_dist_config.get_rsyslog_info()
    if os.path.exists(g_rsyslog_om_mdsd_conf_path):
        cmd = "rm -f {0}/omazuremds.so {1} {2}".format(rsyslog_om_path, g_rsyslog_om_mdsd_conf_path,
                                                       g_rsyslog_im_file_conf_path)
        RunGetOutput(cmd)
    g_dist_config.restart_rsyslog()
    return 0, "rm omazurelinuxmds done"


if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print('No command line argument was specified.\nYou must be executing this program manually for testing.\n'
              'In that case, one of "install", "enable", "disable", "uninstall", or "update" should be given.')
    else:
        try:
            main(sys.argv[1])
        except Exception as e:
            ext_version = ET.parse('manifest.xml').find('{http://schemas.microsoft.com/windowsazure}Version').text
            msg = "Unknown exception thrown from diagnostic.py.\n" \
                  "Error: {0}\nStackTrace: {1}".format(e, traceback.format_exc())
            wala_event_type = wala_event_type_for_telemetry(get_extension_operation_type(sys.argv[1]))
            if len(sys.argv) == 2:
                # Add a telemetry only if this is executed through waagent (in which
                # we are guaranteed to have just one cmdline arg './diagnostic -xxx').
                waagent.AddExtensionEvent(name="Microsoft.OSTCExtension.LinuxDiagnostic",
                                          op=wala_event_type,
                                          isSuccess=False,
                                          version=ext_version,
                                          message=msg)
            else:
                # Trick to print backtrace in case we execute './diagnostic.py -xxx yyy' from a terminal for testing.
                # By just adding one more cmdline arg with any content, the above if condition becomes false,\
                # thus allowing us to run code here, printing the exception message with the stack trace.
                print msg
            # Need to exit with an error code, so that this situation can be detected by waagent and also
            # reported to customer through agent/extension status blob.
            hutil.do_exit(42, wala_event_type, 'Error', '42', msg)  # What's 42? Ask Abhi.
