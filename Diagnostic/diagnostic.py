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
import json

# Just wanted to be able to run 'python diagnostic.py ...' from a local dev box where there's no waagent.
# Actually waagent import can succeed even on a Linux machine without waagent installed,
# by setting PYTHONPATH env var to the azure-linux-extensions/Common/WALinuxAgent-2.0.16,
# but let's just keep this try-except here on them for any potential local imports that may throw.
try:
    # waagent, ext handler
    from Utils.WAAgentUtil import waagent
    import Utils.HandlerUtil as Util

    # Old LAD utils
    import Utils.LadDiagnosticUtil as LadUtil
    import Utils.XmlUtil as XmlUtil

    # New LAD  utils
    import DistroSpecific
    import watcherutil
    from Utils.lad_ext_settings import LadExtSettings
    from Utils.misc_helpers import *
    import lad_config_all as lad_cfg
    from Utils.imds_util import ImdsLogger
    import Utils.omsagent_util as oms
    import telegraf_utils.telegraf_config_handler as telhandler
    import metrics_ext_utils.metrics_ext_handler as me_handler
    import metrics_ext_utils.metrics_constants as metrics_constants



except Exception as e:
    print 'A local import (e.g., waagent) failed. Exception: {0}\n' \
          'Stacktrace: {1}'.format(e, traceback.format_exc())
    print "Can't proceed. Exiting with a special exit code 119."
    sys.exit(119)  # This is the only thing we can do, as all logging depends on waagent/hutil.


# Globals declaration/initialization (with const values only) for IDE
g_ext_settings = None  # LAD extension settings object
g_lad_log_helper = None  # LAD logging helper object
g_dist_config = None  # Distro config object
g_ext_dir = ''  # Extension directory (e.g., /var/lib/waagent/Microsoft.OSTCExtensions.LinuxDiagnostic-x.y.zzzz)
g_mdsd_file_resources_dir = '/var/run/mdsd'
g_mdsd_role_name = 'lad_mdsd'  # Different mdsd role name for multiple mdsd process instances
g_mdsd_file_resources_prefix = ''  # Eventually '/var/run/mdsd/lad_mdsd'
g_lad_pids_filepath = ''  # LAD process IDs (diagnostic.py, mdsd) file path. g_ext_dir + '/lad.pids'
g_ext_op_type = None  # Extension operation type (e.g., Install, Enable, HeartBeat, ...)
g_mdsd_bin_path = '/usr/local/lad/bin/mdsd'  # mdsd binary path. Fixed w/ lad-mdsd-*.{deb,rpm} pkgs
g_diagnostic_py_filepath = ''  # Full path of this script. g_ext_dir + '/diagnostic.py'
# Only 2 globals not following 'g_...' naming convention, for legacy readability...
RunGetOutput = None  # External command executor callable
hutil = None  # Handler util object
enable_metrics_ext = False #Flag to enable/disable MetricsExtension
me_msi_token_expiry_epoch = None



def init_distro_specific_actions():
    """
    Identify the specific Linux distribution in use. Set the global distConfig to point to the corresponding
    implementation class. If the distribution isn't supported, set the extension status appropriately and exit.
    Expects the global hutil to already be initialized.
    """
    # TODO Exit immediately if distro is unknown
    global g_dist_config, RunGetOutput
    dist = platform.dist()
    name = ''
    version = ''
    try:
        if dist[0] != '':
            name = dist[0]
            version = dist[1]
        else:
            try:
                # platform.dist() in python 2.7.15 does not recognize SLES/OpenSUSE 15.
                with open("/etc/os-release", "r") as fp:
                    for line in fp:
                        if line.startswith("ID="):
                            name = line.split("=")[1]
                            name = name.split("-")[0]
                            name = name.replace("\"", "").replace("\n", "")
                        elif line.startswith("VERSION_ID="):
                            version = line.split("=")[1]
                            version = version.split(".")[0]
                            version = version.replace("\"", "").replace("\n", "")
            except:
                raise

        g_dist_config = DistroSpecific.get_distro_actions(name.lower(), version, hutil.log)
        RunGetOutput = g_dist_config.log_run_get_output
    except exceptions.LookupError as ex:
        hutil.error("os version: {0}:{1} not supported".format(dist[0], dist[1]))
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
    global g_diagnostic_py_filepath, g_lad_log_helper

    waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
    waagent.Log("LinuxDiagnostic started to handle.")
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    init_extension_settings()
    init_distro_specific_actions()

    g_ext_dir = os.getcwd()
    g_mdsd_file_resources_prefix = os.path.join(g_mdsd_file_resources_dir, g_mdsd_role_name)
    g_lad_pids_filepath = os.path.join(g_ext_dir, 'lad.pids')
    g_diagnostic_py_filepath = os.path.join(os.getcwd(), __file__)
    g_lad_log_helper = LadLogHelper(hutil.log, hutil.error, waagent.AddExtensionEvent, hutil.do_status_report,
                                    hutil.get_name(), hutil.get_extension_version())


def setup_dependencies_and_mdsd(configurator):
    """
    Set up dependencies for mdsd, such as following:
    1) Distro-specific packages (see DistroSpecific.py)
    2) Set up omsagent (fluentd), syslog (rsyslog or syslog-ng) for mdsd
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

    # Run mdsd prep commands
    g_dist_config.prepare_for_mdsd_install()

    # Set up omsagent
    omsagent_setup_exit_code, omsagent_setup_output = oms.setup_omsagent(configurator, RunGetOutput,
                                                                         hutil.log, hutil.error)
    if omsagent_setup_exit_code is not 0:
        return 3, omsagent_setup_output

    # Install lad-mdsd pkg (/usr/local/lad/bin/mdsd). Must be done after omsagent install because of dependencies
    cmd_exit_code, cmd_output = g_dist_config.install_lad_mdsd()
    if cmd_exit_code != 0:
        return 4, 'lad-mdsd pkg install failed. Exit code={0}, Output={1}'.format(cmd_exit_code, cmd_output)

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
    :rtype: LadConfigAll
    :return: A valid LadConfigAll object if config is valid. None otherwise.
    """
    deployment_id = get_deployment_id_from_hosting_env_cfg(waagent.LibDir, hutil.log, hutil.error)

    # Define wrappers around a couple misc_helpers. These can easily be mocked out in tests. PEP-8 says use
    # def, don't assign a lambda to a variable. *shrug*
    def encrypt_string(cert, secret):
        return encrypt_secret_with_cert(RunGetOutput, hutil.error, cert, secret)

    configurator = lad_cfg.LadConfigAll(g_ext_settings, g_ext_dir, waagent.LibDir, deployment_id,
                                        read_uuid, encrypt_string, hutil.log, hutil.error)
    try:
        config_valid, config_invalid_reason = configurator.generate_all_configs()
    except Exception as e:
        config_invalid_reason =\
            'Exception while generating configs: {0}. Traceback: {1}'.format(e, traceback.format_exc())
        hutil.error(config_invalid_reason)
        config_valid = False

    if not config_valid:
        g_lad_log_helper.log_and_report_failed_config_generation(
            g_ext_op_type, config_invalid_reason,
            g_ext_settings.redacted_handler_settings())
        return None

    global enable_metrics_ext
    ladconfig = configurator._ladCfg()
    sink = configurator._sink_configs_public.get_sink_by_name("AzMonSink")
    if sink is not None:
        if sink['name'] == 'AzMonSink':
            enable_metrics_ext = True

    return configurator


def check_for_supported_waagent_and_distro_version():
    """
    Checks & returns if the installed waagent and the Linux distro/version are supported by this LAD.
    :rtype: bool
    :return: True iff so.
    """
    for notsupport in ('WALinuxAgent-2.0.5', 'WALinuxAgent-2.0.4', 'WALinuxAgent-1'):
        code, str_ret = RunGetOutput("grep 'GuestAgentVersion.*" + notsupport + "' /usr/sbin/waagent",
                                             should_log=False)
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
    global me_msi_token_expiry_epoch

    g_ext_op_type = get_extension_operation_type(command)
    waagent_ext_event_type = wala_event_type_for_telemetry(g_ext_op_type)

    if not check_for_supported_waagent_and_distro_version():
        return

    try:
        hutil.log("Dispatching command:" + command)

        if g_ext_op_type is waagent.WALAEventOperation.Disable:
            if g_dist_config.use_systemd():
                RunGetOutput('systemctl stop mdsd-lde && systemctl disable mdsd-lde')
            else:
                stop_mdsd()
            oms.tear_down_omsagent_for_lad(RunGetOutput, False)

            #Stop the telegraf and ME services
            tel_out, tel_msg = telhandler.stop_telegraf_service(is_lad=True)
            if tel_out:
                hutil.log(tel_msg)
            else:
                hutil.error(tel_msg)

            me_out, me_msg = me_handler.stop_metrics_service(is_lad=True)
            if me_out:
                hutil.log(me_msg)
            else:
                hutil.error(me_msg)

            hutil.do_status_report(g_ext_op_type, "success", '0', "Disable succeeded")

        elif g_ext_op_type is waagent.WALAEventOperation.Uninstall:
            if g_dist_config.use_systemd():
                RunGetOutput('systemctl stop mdsd-lde && systemctl disable mdsd-lde ' +
                             '&& rm /lib/systemd/system/mdsd-lde.service')
            else:
                stop_mdsd()
            # Must remove lad-mdsd package first because of the dependencies
            cmd_exit_code, cmd_output = g_dist_config.remove_lad_mdsd()
            if cmd_exit_code != 0:
                hutil.error('lad-mdsd remove failed. Still proceeding to uninstall. '
                            'Exit code={0}, Output={1}'.format(cmd_exit_code, cmd_output))
            oms.tear_down_omsagent_for_lad(RunGetOutput, True)

            #Stop the telegraf and ME services
            tel_out, tel_msg = telhandler.stop_telegraf_service(is_lad=True)
            if tel_out:
                hutil.log(tel_msg)
            else:
                hutil.error(tel_msg)

            me_out, me_msg = me_handler.stop_metrics_service(is_lad=True)
            if me_out:
                hutil.log(me_msg)
            else:
                hutil.error(me_msg)

            #Delete the telegraf and ME services
            tel_rm_out, tel_rm_msg = telhandler.remove_telegraf_service()
            if tel_rm_out:
                hutil.log(tel_rm_msg)
            else:
                hutil.error(tel_rm_msg)

            me_rm_out, me_rm_msg = me_handler.remove_metrics_service(is_lad=True)
            if me_rm_out:
                hutil.log(me_rm_msg)
            else:
                hutil.error(me_rm_msg)

            hutil.do_status_report(g_ext_op_type, "success", '0', "Uninstall succeeded")

        elif g_ext_op_type is waagent.WALAEventOperation.Install:
            # Install dependencies (omsagent, which includes omi, scx).
            configurator = create_core_components_configs()
            dependencies_err, dependencies_msg = setup_dependencies_and_mdsd(configurator)
            if dependencies_err != 0:
                g_lad_log_helper.report_mdsd_dependency_setup_failure(waagent_ext_event_type, dependencies_msg)
                hutil.do_status_report(g_ext_op_type, "error", '-1', "Install failed")
                return

            #Start the Telegraf and ME services on Enable after installation is complete
            start_telegraf_out, log_messages = telhandler.start_telegraf(is_lad=True)
            if start_telegraf_out:
                hutil.log("Successfully started metrics-sourcer.")
            else:
                hutil.error(log_messages)

            if enable_metrics_ext:
                # Generate/regenerate MSI Token required by ME
                msi_token_generated, me_msi_token_expiry_epoch, log_messages = me_handler.generate_MSI_token()
                if msi_token_generated:
                    hutil.log("Successfully generated metrics-extension MSI Auth token.")
                else:
                    hutil.error(log_messages)

                start_metrics_out, log_messages = me_handler.start_metrics(is_lad=True)
                if start_metrics_out:
                    hutil.log("Successfully started metrics-extension.")
                else:
                    hutil.error(log_messages)

            if g_dist_config.use_systemd():
                install_lad_as_systemd_service()
            hutil.do_status_report(g_ext_op_type, "success", '0', "Install succeeded")

        elif g_ext_op_type is waagent.WALAEventOperation.Enable:
            if hutil.is_current_config_seq_greater_inused():
                configurator = create_core_components_configs()
                dependencies_err, dependencies_msg = setup_dependencies_and_mdsd(configurator)
                if dependencies_err != 0:
                    g_lad_log_helper.report_mdsd_dependency_setup_failure(waagent_ext_event_type, dependencies_msg)
                    hutil.do_status_report(g_ext_op_type, "error", '-1', "Enabled failed")
                    return

                #Start the Telegraf and ME services on Enable after installation is complete
                start_telegraf_out, log_messages = telhandler.start_telegraf(is_lad=True)
                if start_telegraf_out:
                    hutil.log("Successfully started metrics-sourcer.")
                else:
                    hutil.error(log_messages)

                if enable_metrics_ext:
                    # Generate/regenerate MSI Token required by ME
                    generate_token = False
                    me_token_path = g_ext_dir + "/metrics_configs/AuthToken-MSI.json"

                    if me_msi_token_expiry_epoch is None or me_msi_token_expiry_epoch == "":
                        if os.path.isfile(me_token_path):
                            with open(me_token_path, "r") as f:
                                authtoken_content = f.read()
                                if authtoken_content and "expires_on" in authtoken_content:
                                    me_msi_token_expiry_epoch = authtoken_content["expires_on"]
                                else:
                                    generate_token = True
                        else:
                            generate_token = True

                    if me_msi_token_expiry_epoch:
                        currentTime = datetime.datetime.now()
                        token_expiry_time = datetime.datetime.fromtimestamp(me_msi_token_expiry_epoch)
                        if token_expiry_time - currentTime < datetime.timedelta(minutes=30):
                            # The MSI Token will expire within 30 minutes. We need to refresh the token
                            generate_token = True

                    if generate_token:
                        generate_token = False
                        msi_token_generated, me_msi_token_expiry_epoch, log_messages = me_handler.generate_MSI_token()
                        if msi_token_generated:
                            hutil.log("Successfully refreshed metrics-extension MSI Auth token.")
                        else:
                            hutil.error(log_messages)

                    start_metrics_out, log_messages = me_handler.start_metrics(is_lad=True)
                    if start_metrics_out:
                        hutil.log("Successfully started metrics-extension.")
                    else:
                        hutil.error(log_messages)

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
            hutil.do_status_report(g_ext_op_type, "success", '0', "Enable succeeded, extension daemon started")
            # If the -daemon detects a problem, e.g. bad configuration, it will overwrite this status with a more
            # informative one. If it succeeds, all is well.

        elif g_ext_op_type is "Daemon":
            configurator = create_core_components_configs()
            if configurator:
                start_mdsd(configurator)

        elif g_ext_op_type is waagent.WALAEventOperation.Update:
            hutil.do_status_report(g_ext_op_type, "success", '0', "Update succeeded")

    except Exception as e:
        hutil.error("Failed to perform extension operation {0} with error:{1}, {2}".format(g_ext_op_type, e,
                                                                                           traceback.format_exc()))
        hutil.do_status_report(g_ext_op_type, 'error', '0',
                               'Extension operation {0} failed:{1}'.format(g_ext_op_type, e))


def start_daemon():
    """
    Start diagnostic.py as a daemon for scheduled tasks and to monitor mdsd daemon. If Popen() has a problem it will
    raise an exception (often OSError)
    :return: None
    """
    args = ['python', g_diagnostic_py_filepath, "-daemon"]
    log = open(os.path.join(os.getcwd(), 'daemon.log'), 'w')
    hutil.log('start daemon ' + str(args))
    subprocess.Popen(args, stdout=log, stderr=log)


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


def start_mdsd(configurator):
    """
    Start mdsd and monitor its activities. Report if it crashes or emits error logs.
    :param configurator: A valid LadConfigAll object that was obtained by create_core_components_config().
                         This will be used for configuring rsyslog/syslog-ng/fluentd/in_syslog/out_mdsd components
    :return: None
    """
    # This must be done first, so that extension enable completion doesn't get delayed.
    write_lad_pids_to_file(g_lad_pids_filepath, os.getpid())

    # Need 'HeartBeat' instead of 'Daemon'
    waagent_ext_event_type = wala_event_type_for_telemetry(g_ext_op_type)

    copy_env = os.environ
    # Add MDSD_CONFIG_DIR  as an env variable since new mdsd master branch LAD doesnt create this dir
    mdsd_config_cache_dir = os.path.join(g_ext_dir, "config")
    copy_env["MDSD_CONFIG_DIR"] = mdsd_config_cache_dir


    # We then validate the mdsd config and proceed only when it succeeds.
    xml_file = os.path.join(g_ext_dir, 'xmlCfg.xml')
    tmp_env_dict = {}  # Need to get the additionally needed env vars (SSL_CERT_*) for this mdsd run as well...
    g_dist_config.extend_environment(tmp_env_dict)
    added_env_str = ' '.join('{0}={1}'.format(k, tmp_env_dict[k]) for k in tmp_env_dict)
    config_validate_cmd = '{0}{1}{2} -v -c {3} -r {4}'.format(added_env_str, ' ' if added_env_str else '',
                                                       g_mdsd_bin_path, xml_file, g_ext_dir)
    config_validate_cmd_status, config_validate_cmd_msg = RunGetOutput(config_validate_cmd)
    if config_validate_cmd_status is not 0:
        # Invalid config. Log error and report success.
        g_lad_log_helper.log_and_report_invalid_mdsd_cfg(g_ext_op_type,
                                                         config_validate_cmd_msg, read_file_to_string(xml_file))
        return

    # Start OMI if it's not running.
    # This shouldn't happen, but this measure is put in place just in case (e.g., Ubuntu 16.04 systemd).
    # Don't check if starting succeeded, as it'll be done in the loop below anyway.
    omi_running = RunGetOutput("/opt/omi/bin/service_control is-running", should_log=False)[0] is 1
    if not omi_running:
        hutil.log("OMI is not running. Restarting it.")
        RunGetOutput("/opt/omi/bin/service_control restart")

    log_dir = hutil.get_log_dir()
    err_file_path = os.path.join(log_dir, 'mdsd.err')
    info_file_path = os.path.join(log_dir, 'mdsd.info')
    warn_file_path = os.path.join(log_dir, 'mdsd.warn')
    # Need to provide EH events and Rsyslog spool path since the new mdsd master branch LAD doesnt create the directory needed
    eh_spool_path = os.path.join(log_dir, 'eh')

    update_selinux_settings_for_rsyslogomazuremds(RunGetOutput, g_ext_dir)

    mdsd_stdout_redirect_path = os.path.join(g_ext_dir, "mdsd.log")
    mdsd_stdout_stream = None

    g_dist_config.extend_environment(copy_env)

    # mdsd http proxy setting
    proxy_config = get_mdsd_proxy_config(waagent.HttpProxyConfigString, g_ext_settings, hutil.log)
    if proxy_config:
        copy_env['MDSD_http_proxy'] = proxy_config

    # Now prepare actual mdsd cmdline.
    command = '{0} -A -C -c {1} -R -r {2} -e {3} -w {4} -S {7} -o {5}{6}'.format(
        g_mdsd_bin_path,
        xml_file,
        g_mdsd_role_name,
        err_file_path,
        warn_file_path,
        info_file_path,
        g_ext_settings.get_mdsd_trace_option(),
        eh_spool_path).split(" ")

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
            telegraf_restart_retries = 0
            me_restart_retries = 0
            max_restart_retries = 10
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
                # 4. Check if telegraf is running, if not, then restart
                if not telhandler.is_running(is_lad=True):
                    if telegraf_restart_retries < max_restart_retries:
                        telegraf_restart_retries += 1
                        hutil.log("Telegraf binary process is not running. Restarting telegraf now. Retry count - {0}".format(telegraf_restart_retries))
                        tel_out, tel_msg = telhandler.stop_telegraf_service(is_lad=True)
                        if tel_out:
                            hutil.log(tel_msg)
                        else:
                            hutil.error(tel_msg)
                        start_telegraf_out, log_messages = telhandler.start_telegraf(is_lad=True)
                        if start_telegraf_out:
                            hutil.log("Successfully started metrics-sourcer.")
                        else:
                            hutil.error(log_messages)
                    else:
                        hutil.error("Telegraf binary process is not running. Failed to restart after {0} retries. Please check telegraf.log at {1}".format(max_restart_retries, log_dir))
                else:
                    telegraf_restart_retries = 0
                # 5. Check if ME is running, if not, then restart
                if enable_metrics_ext:
                    if not me_handler.is_running(is_lad=True):
                        if me_restart_retries < max_restart_retries:
                            me_restart_retries += 1
                            hutil.log("MetricsExtension binary process is not running. Restarting MetricsExtension now. Retry count - {0}".format(me_restart_retries))
                            me_out, me_msg = me_handler.stop_metrics_service(is_lad=True)
                            if me_out:
                                hutil.log(me_msg)
                            else:
                                hutil.error(me_msg)
                            start_metrics_out, log_messages = me_handler.start_metrics(is_lad=True)
                            if start_metrics_out:
                                hutil.log("Successfully started metrics-extension.")
                            else:
                                hutil.error(log_messages)
                        else:
                            hutil.error("MetricsExtension binary process is not running. Failed to restart after {0} retries. Please check /var/log/syslog for ME logs".format(max_restart_retries))
                    else:
                        me_restart_retries = 0
                    # 6. Regenerate the MSI auth token required for ME if it is nearing expiration
                    # Generate/regenerate MSI Token required by ME
                    global me_msi_token_expiry_epoch
                    generate_token = False
                    me_token_path = g_ext_dir + "/config/metrics_configs/AuthToken-MSI.json"

                    if me_msi_token_expiry_epoch is None  or me_msi_token_expiry_epoch == "":
                        if os.path.isfile(me_token_path):
                            with open(me_token_path, "r") as f:
                                authtoken_content = json.loads(f.read())
                                if authtoken_content and "expires_on" in authtoken_content:
                                    me_msi_token_expiry_epoch = authtoken_content["expires_on"]
                                else:
                                    generate_token = True
                        else:
                            generate_token = True

                    if me_msi_token_expiry_epoch:
                        currentTime = datetime.datetime.now()
                        token_expiry_time = datetime.datetime.fromtimestamp(float(me_msi_token_expiry_epoch))
                        if token_expiry_time - currentTime < datetime.timedelta(minutes=30):
                            # The MSI Token will expire within 30 minutes. We need to refresh the token
                            generate_token = True

                    if generate_token:
                        generate_token = False
                        msi_token_generated, me_msi_token_expiry_epoch, log_messages = me_handler.generate_MSI_token()
                        if msi_token_generated:
                            hutil.log("Successfully refreshed metrics-extension MSI Auth token.")
                        else:
                            hutil.error(log_messages)

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

        # mdsd all 3 allowed quick/consecutive crashes exhausted
        hutil.do_status_report(waagent_ext_event_type, "error", '1', "mdsd stopped: " + mdsd_crash_msg)
        # Need to tear down omsagent setup for LAD before returning/exiting if it was set up earlier
        oms.tear_down_omsagent_for_lad(RunGetOutput, False)
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
        errmsg = "Failed to launch mdsd with error: {0}, traceback: {1}".format(e, traceback.format_exc())
        hutil.error(errmsg)
        hutil.do_status_report(waagent_ext_event_type, 'error', '1', errmsg)
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=waagent_ext_event_type,
                                  isSuccess=False,
                                  version=hutil.get_extension_version(),
                                  message=errmsg)
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
            is_still_alive = RunGetOutput("cat /proc/" + pid.strip() + "/cmdline", should_log=False)[1]
            if is_still_alive.find('/waagent/') > 0:
                lad_pids.append(pid.strip())
            else:
                hutil.log("return not alive " + is_still_alive.strip())
    return lad_pids


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
            time.sleep(10)

            # Query OMI once again to make sure restart fixed the issue.
            # If not, attempt to re-install OMI as last resort.
            cmd_exit_status, cmd_output = RunGetOutput(cmd=omicli_noop_query_cmd, should_log=False)
            should_reinstall_omi = cmd_exit_status is not 0
            if should_reinstall_omi:
                hutil.error("OMI noop query failed even after OMI was restarted. Attempting to re-install the components.")
                configurator = create_core_components_configs()
                dependencies_err, dependencies_msg = setup_dependencies_and_mdsd(configurator)
                if dependencies_err != 0:
                    hutil.error("Re-installing the components failed with error code: " + str(dependencies_err) + ", error message: " +  dependencies_msg)
                    return omi_installed
                else:
                    omi_reinstalled = True

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
                waagent.AddExtensionEvent(name="Microsoft.Azure.Diagnostic.LinuxDiagnostic",
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
