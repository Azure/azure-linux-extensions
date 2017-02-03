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

import base64
import binascii
import datetime
import os
import os.path
import platform
import re
import signal
import subprocess
import sys
import syslog
import threading
import time
import traceback
import xml.dom.minidom
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
    import watcherutil
    from misc_helpers import *
    from config_mdsd_rsyslog import *
    from Utils.imds_util import ImdsLogger
except Exception as e:
    print 'A local import (e.g., waagent) failed. Exception: {0}\n' \
          'Stacktrace: {1}'.format(e, traceback.format_exc())
    print 'Are you running without waagent for some reason? Just passing here for now...'
    # We may add some waagent mock later to support this scenario.


def init_extension_settings():
    """Initialize extension's public & private settings. hutil must be already initialized prior to calling this."""
    global g_ext_settings

    # Need to read/parse the Json extension settings (context) first.
    hutil.try_parse_context()
    hutil.set_verbose_log(False)  # Explicitly set verbose flag to False. This is default anyway, but it will be made explicit and logged.

    g_ext_settings = LadExtSettings(hutil.get_handler_settings())


def init_globals():
    """Initialize all the globals in a function so that we can catch any exceptions that might be raised."""
    global WorkDir, MDSDFileResourcesDir, MDSDRoleName, MDSDFileResourcesPrefix
    global MDSDPidFile, MDSDPidPortFile, EnableSyslog, hutil, ExtensionOperationType
    global rsyslog_module_for_check, RunGetOutput, MdsdFolder, StartDaemonFilePath, omi_universal_pkg_name
    global imfile_config_filename, DebianConfig, RedhatConfig, UbuntuConfig1510OrHigher, SUSE11_MDSD_SSL_CERTS_FILE
    global SuseConfig11, SuseConfig12, CentosConfig, MDSD_LISTEN_PORT, All_Dist, distConfig, dist
    global distroNameAndVersion, UseSystemdServiceManager
    global g_ext_settings

    WorkDir = os.getcwd()
    MDSDFileResourcesDir = "/var/run/mdsd"
    MDSDRoleName = 'lad_mdsd'
    MDSDFileResourcesPrefix = os.path.join(MDSDFileResourcesDir, MDSDRoleName)
    MDSDPidFile = os.path.join(WorkDir, 'mdsd.pid')
    MDSDPidPortFile = MDSDFileResourcesPrefix + '.pidport'
    EnableSyslog = True
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
    waagent.Log("LinuxAzureDiagnostic started to handle.")
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    init_extension_settings()
    ExtensionOperationType = None

    def LogRunGetOutPut(cmd, should_log=True):
        if should_log:
            hutil.log("RunCmd "+cmd)
        error, msg = waagent.RunGetOutput(cmd, chk_err=should_log)
        if should_log:
            hutil.log("Return "+str(error)+":"+msg)
        return error, msg

    rsyslog_module_for_check = 'omprog.so'
    RunGetOutput = LogRunGetOutPut
    MdsdFolder = os.path.join(WorkDir, 'bin')
    StartDaemonFilePath = os.path.join(os.getcwd(), __file__)
    omi_universal_pkg_name = 'scx-1.6.2-337.universal.x64.sh'

    imfile_config_filename = os.path.join(WorkDir, 'imfileconfig')

    DebianConfig = {"installomi":"bash "+omi_universal_pkg_name+" --upgrade;",
                    "installrequiredpackage":'dpkg-query -l PACKAGE |grep ^ii ;  if [ ! $? == 0 ]; then apt-get update ; apt-get install -y PACKAGE; fi',
                    "packages":(),
                    "stoprsyslog" : "service rsyslog stop",
                    "restartrsyslog":"service rsyslog restart",
                    'checkrsyslog':'(dpkg-query -s rsyslog;dpkg-query -L rsyslog) |grep "Version\|' + rsyslog_module_for_check + '"',
                    'mdsd_env_vars': {"SSL_CERT_DIR": "/usr/lib/ssl/certs", "SSL_CERT_FILE ": "/usr/lib/ssl/cert.pem"}
                    }

    RedhatConfig =  {"installomi":"bash "+omi_universal_pkg_name+" --upgrade;",
                     "installrequiredpackage":'rpm -q PACKAGE ;  if [ ! $? == 0 ]; then yum install -y PACKAGE; fi',
                     "packages":('policycoreutils-python', 'tar'),  # policycoreutils-python missing on Oracle Linux (still needed to manipulate SELinux policy). tar is really missing on Oracle Linux 7!
                     "stoprsyslog" : "service rsyslog stop",
                     "restartrsyslog":"service rsyslog restart",
                     'checkrsyslog':'(rpm -qi rsyslog;rpm -ql rsyslog)|grep "Version\\|' + rsyslog_module_for_check + '"',
                     'mdsd_env_vars': {"SSL_CERT_DIR": "/etc/pki/tls/certs", "SSL_CERT_FILE": "/etc/pki/tls/cert.pem"}
                     }

    UbuntuConfig1510OrHigher = dict(DebianConfig.items()+
                        {'installrequiredpackages':'[ $(dpkg -l PACKAGES |grep ^ii |wc -l) -eq \'COUNT\' ] '
                            '|| apt-get install -y PACKAGES',
                         'packages':()
                        }.items())

    # For SUSE11, we need to create a CA certs file for our statically linked OpenSSL 1.0 libs
    SUSE11_MDSD_SSL_CERTS_FILE = "/etc/ssl/certs/mdsd-ca-certs.pem"

    SuseConfig11 = dict(RedhatConfig.items()+
                      {'installrequiredpackage':'rpm -qi PACKAGE;  if [ ! $? == 0 ]; then zypper --non-interactive install PACKAGE;fi; ',
                       "packages":('rsyslog',),
                       'restartrsyslog':"""\
    if [ ! -f /etc/sysconfig/syslog.org_lad ]; then cp /etc/sysconfig/syslog /etc/sysconfig/syslog.org_lad; fi;
    sed -i 's/SYSLOG_DAEMON="syslog-ng"/SYSLOG_DAEMON="rsyslogd"/g' /etc/sysconfig/syslog;
    service syslog restart""",
                       'mdsd_prep_cmds' :
                            (r'\cp /dev/null {0}'.format(SUSE11_MDSD_SSL_CERTS_FILE),
                             r'chown 0:0 {0}'.format(SUSE11_MDSD_SSL_CERTS_FILE),
                             r'chmod 0644 {0}'.format(SUSE11_MDSD_SSL_CERTS_FILE),
                             r"cat /etc/ssl/certs/????????.[0-9a-f] | sed '/^#/d' >> {0}".format(SUSE11_MDSD_SSL_CERTS_FILE)
                            ),
                       'mdsd_env_vars': {"SSL_CERT_FILE": SUSE11_MDSD_SSL_CERTS_FILE}
                      }.items())

    SuseConfig12 = dict(RedhatConfig.items()+
                      {'installrequiredpackage':' rpm -qi PACKAGE; if [ ! $? == 0 ]; then zypper --non-interactive install PACKAGE;fi; ','restartrsyslog':'service syslog restart',
                       "packages":('libgthread-2_0-0','ca-certificates-mozilla','rsyslog'),
                       'mdsd_env_vars': {"SSL_CERT_DIR": "/var/lib/ca-certificates/openssl", "SSL_CERT_FILE": "/etc/ssl/cert.pem"}
                      }.items())

    CentosConfig = dict(RedhatConfig.items()+
                        {'installrequiredpackage':'rpm -qi PACKAGE; if [ ! $? == 0 ]; then  yum install -y PACKAGE; fi',
                         "packages":('policycoreutils-python',)  # policycoreutils-python missing on CentOS (still needed to manipulate SELinux policy)
                        }.items())

    MDSD_LISTEN_PORT= '29131'  # No longer used, but we still need this to avoid port conflict with ASM mdsd
    All_Dist= {'debian':DebianConfig, 'Kali':DebianConfig,
               'Ubuntu':DebianConfig, 'Ubuntu:15.10':UbuntuConfig1510OrHigher,
               'Ubuntu:16.04' : UbuntuConfig1510OrHigher, 'Ubuntu:16.10' : UbuntuConfig1510OrHigher,
               'redhat':RedhatConfig, 'centos':CentosConfig, 'oracle':RedhatConfig,
               'SuSE:11':SuseConfig11, 'SuSE:12':SuseConfig12, 'SuSE':SuseConfig12}
    distConfig = None
    dist = platform.dist()
    distroNameAndVersion = dist[0] + ":" + dist[1]
    if distroNameAndVersion in All_Dist:  # if All_Dist.has_key(distroNameAndVersion):
        distConfig = All_Dist[distroNameAndVersion]
    elif All_Dist.has_key(dist[0]):
        distConfig = All_Dist[dist[0]]

    if distConfig is None:
        hutil.error("os version:" + distroNameAndVersion + " not supported")

    UseSystemdServiceManager = False
    if dist[0] == 'Ubuntu' and dist[1] >= '15.10':  # Use systemd for Ubuntu 15.10 or later
        UseSystemdServiceManager = True


def setup_dependencies_and_mdsd():
    global EnableSyslog

    # Install dependencies
    install_package_error = ""
    retry = 3
    while retry > 0:
        error, msg = install_required_package()
        hutil.log(msg)
        if error == 0:
            break
        else:
            retry -= 1
            hutil.log("Sleep 60 retry "+str(retry))
            install_package_error = msg
            time.sleep(60)
    if install_package_error:
        if len(install_package_error) > 1024:
            install_package_error = install_package_error[0:512]+install_package_error[-512:-1]
        hutil.error(install_package_error)
        return 2, install_package_error

    if EnableSyslog:
        error, msg = install_rsyslogom()
        if error != 0:
            hutil.error(msg)
            return 3, msg

    # Run mdsd prep commands
    if 'mdsd_prep_cmds' in distConfig:
        for cmd in distConfig['mdsd_prep_cmds']:
            RunGetOutput(cmd)

    # Install/start OMI
    omi_err, omi_msg = install_omi()
    if omi_err is not 0:
        return 4, omi_msg

    return 0, 'success'


def install_service():
    RunGetOutput('sed s#{WORKDIR}#' + WorkDir + '# ' +
                 WorkDir + '/services/mdsd-lde.service > /lib/systemd/system/mdsd-lde.service')
    RunGetOutput('systemctl daemon-reload')


def main(command):
    init_globals()

    # Declare global scope for globals that are assigned in this function
    global EnableSyslog, UseSystemdServiceManager, ExtensionOperationType

    # 'enableSyslog' is to be used for consistency, but we've had 'EnableSyslog' all the time, so accommodate it.
    EnableSyslog = g_ext_settings.read_public_config('enableSyslog').lower() != 'false' \
                   and g_ext_settings.read_public_config('EnableSyslog').lower() != 'false'

    ExtensionOperationType = get_extension_operation_type(command)

    config_valid, config_invalid_reason = generate_mdsd_rsyslog_configs(g_ext_settings, WorkDir, waagent.LibDir,
                                                                        imfile_config_filename, RunGetOutput,
                                                                        hutil.log, hutil.error)
    if not config_valid:
        config_invalid_log = "Invalid config settings given: " + config_invalid_reason +\
                             ". Install will proceed, but enable can't proceed, " \
                             "in which case it's still considered a success as it's an external error."
        hutil.log(config_invalid_log)
        if ExtensionOperationType is waagent.WALAEventOperation.Enable:
            hutil.do_status_report(ExtensionOperationType, "success", '0', config_invalid_log)
            waagent.AddExtensionEvent(name=hutil.get_name(),
                                      op=ExtensionOperationType,
                                      isSuccess=True,
                                      version=hutil.get_extension_version(),
                                      message=config_invalid_log)
            return

    for notsupport in ('WALinuxAgent-2.0.5','WALinuxAgent-2.0.4','WALinuxAgent-1'):
        code, str_ret = waagent.RunGetOutput("grep 'GuestAgentVersion.*" + notsupport + "' /usr/sbin/waagent", chk_err=False)
        if code == 0 and str_ret.find(notsupport) > -1:
            hutil.log("cannot run this extension on  " + notsupport)
            hutil.do_status_report(ExtensionOperationType, "error", '1', "cannot run this extension on  " + notsupport)
            return

    if distConfig is None:
        unsupported_distro_version_log = "LAD can't be installed on this distro/version (" + str(platform.dist()) + "), as it's not supported. This extension install/enable operation is still considered a success as it's an external error."
        hutil.log(unsupported_distro_version_log)
        hutil.do_status_report(ExtensionOperationType, "success", '0', unsupported_distro_version_log)
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=ExtensionOperationType,
                                  isSuccess=True,
                                  version=hutil.get_extension_version(),
                                  message="Can't be installed on this OS "+str(platform.dist()))
        return
    try:
        hutil.log("Dispatching command:" + command)

        if ExtensionOperationType is waagent.WALAEventOperation.Disable:
            if UseSystemdServiceManager:
                RunGetOutput('systemctl stop mdsd-lde && systemctl disable mdsd-lde')
            else:
                stop_mdsd()
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Disable succeeded")

        elif ExtensionOperationType is waagent.WALAEventOperation.Uninstall:
            if UseSystemdServiceManager:
                RunGetOutput('systemctl stop mdsd-lde && systemctl disable mdsd-lde ' +
                             '&& rm /lib/systemd/system/mdsd-lde.service')
            else:
                stop_mdsd()
            uninstall_omi()
            if EnableSyslog:
                uninstall_rsyslogom()
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Uninstall succeeded")

        elif ExtensionOperationType is waagent.WALAEventOperation.Install:
            if UseSystemdServiceManager:
                install_service()
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Install succeeded")

        elif ExtensionOperationType is waagent.WALAEventOperation.Enable:
            if UseSystemdServiceManager:
                install_service()
                RunGetOutput('systemctl enable mdsd-lde')
                mdsd_lde_active = RunGetOutput('systemctl status mdsd-lde')[0] is 0
                if not mdsd_lde_active or hutil.is_current_config_seq_greater_inused():
                    RunGetOutput('systemctl restart mdsd-lde')
            else:
                # if daemon process not runs
                mdsd_procs = get_mdsd_process()
                hutil.log("get pid:" + str(mdsd_procs))
                if len(mdsd_procs) != 2 or hutil.is_current_config_seq_greater_inused():
                    stop_mdsd()
                    start_daemon()
            hutil.set_inused_config_seq(hutil.get_seq_no())
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Enable succeeded")

        elif ExtensionOperationType is "Daemon":
            start_mdsd()

        elif ExtensionOperationType is waagent.WALAEventOperation.Update:
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Update succeeded")

    except Exception as e:
        hutil.error(("Failed to perform extension operation {0} with error:{1}, {2}").format(ExtensionOperationType, e, traceback.format_exc()))
        hutil.do_status_report(ExtensionOperationType,'error','0',
                      'Extension operation {0} failed:{1}'.format(ExtensionOperationType, e))


def start_daemon():
    args = ['python', StartDaemonFilePath, "-daemon"]
    log = open(os.path.join(os.getcwd(),'daemon.log'), 'w')
    hutil.log('start daemon '+str(args))
    subprocess.Popen(args, stdout=log, stderr=log)
    wait_n = 20
    while len(get_mdsd_process())==0 and wait_n >0:
        time.sleep(5)
        wait_n=wait_n-1
    if wait_n <=0:
        hutil.error("wait daemon start time out")


def start_watcher_thread():
    # Create monitor object that encapsulates monitoring activities
    watcher = watcherutil.Watcher(hutil.error, hutil.log, log_to_console=True)
    # Create an IMDS data logger and set it to the monitor object
    imds_logger = ImdsLogger(hutil.get_name(), hutil.get_extension_version(),
                             waagent.WALAEventOperation.HeartBeat, waagent.AddExtensionEvent)
    watcher.set_imds_logger(imds_logger)
    # Start a thread to perform periodic monitoring activity (e.g., /etc/fstab watcher, IMDS data logging)
    threadObj = threading.Thread(target=watcher.watch)
    threadObj.daemon = True
    threadObj.start()


def start_mdsd():
    global EnableSyslog, ExtensionOperationType
    with open(MDSDPidFile, "w") as pidfile:
         pidfile.write(str(os.getpid())+'\n')
         pidfile.close()

    # Assign correct ext op type for correct ext status/event reporting.
    # start_mdsd() is called only through "./diagnostic.py -daemon"
    # which has to be recognized as "Daemon" ext op type, but it's not a standard Azure ext op
    # type, so it needs to be reverted back to a standard one (which is "Enable").
    ExtensionOperationType = waagent.WALAEventOperation.Enable

    dependencies_err, dependencies_msg = setup_dependencies_and_mdsd()
    if dependencies_err != 0:
        dependencies_err_log_msg = "Failed to set up mdsd dependencies: {0}".format(dependencies_msg)
        hutil.error(dependencies_err_log_msg)
        hutil.do_status_report(ExtensionOperationType, 'error', '1', dependencies_err_log_msg)
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=ExtensionOperationType,
                                  isSuccess=False,
                                  version=hutil.get_extension_version(),
                                  message=dependencies_err_log_msg)
        return

    # Start OMI if it's not running.
    # This shouldn't happen, but this measure is put in place just in case (e.g., Ubuntu 16.04 systemd).
    # Don't check if starting succeeded, as it'll be done in the loop below anyway.
    omi_running = RunGetOutput("/opt/omi/bin/service_control is-running")[0] is 1
    if not omi_running:
        RunGetOutput("/opt/omi/bin/service_control restart")

    if not EnableSyslog:
        uninstall_rsyslogom()

    log_dir = hutil.get_log_dir()
    monitor_file_path = os.path.join(log_dir, 'mdsd.err')
    info_file_path = os.path.join(log_dir, 'mdsd.info')
    warn_file_path = os.path.join(log_dir, 'mdsd.warn')

    update_selinux_settings_for_rsyslogomazuremds(RunGetOutput, WorkDir)

    mdsd_log_path = os.path.join(WorkDir,"mdsd.log")
    mdsd_log = None
    copy_env = os.environ
    copy_env['LD_LIBRARY_PATH']=MdsdFolder
    if 'mdsd_env_vars' in distConfig:
        env_vars = distConfig['mdsd_env_vars']
        for var_name, var_value in env_vars.items():
            copy_env[var_name] = var_value

    # mdsd http proxy setting
    proxy_config = get_mdsd_proxy_config(waagent.HttpProxyConfigString, g_ext_settings, hutil.log)
    if proxy_config:
        copy_env['MDSD_http_proxy'] = proxy_config

    xml_file = os.path.join(WorkDir, './xmlCfg.xml')

    # We now validate the config and proceed only when it succeeds.
    config_validate_cmd = '{0} -v -c {1}'.format(os.path.join(MdsdFolder, "mdsd"), xml_file)
    config_validate_cmd_status, config_validate_cmd_msg = RunGetOutput(config_validate_cmd)
    if config_validate_cmd_status is not 0:
        # Invalid config. Log error and report success.
        message = "Invalid mdsd config given. Can't enable. This extension install/enable operation is still considered a success as it's an external error. Config validation result: "\
                  + config_validate_cmd_msg + ". Terminating LAD as it can't proceed."
        hutil.log(message)
        # No need to do success status report (it's already done). Just silently return.
        return

    # Config validated. Prepare actual mdsd cmdline.
    command = '{0} -A -C -c {1} -p {2} -R -r {3} -e {4} -w {5} -o {6}'.format(
        os.path.join(MdsdFolder,"mdsd"),
        xml_file,
        MDSD_LISTEN_PORT,
        MDSDRoleName,
        monitor_file_path,
        warn_file_path,
        info_file_path).split(" ")

    try:
        start_watcher_thread()

        num_quick_consecutive_crashes = 0

        while num_quick_consecutive_crashes < 3:  # We consider only quick & consecutive crashes for retries

            RunGetOutput("rm -f " + MDSDPidPortFile)  # Must delete any existing port num file
            mdsd_log = open(mdsd_log_path,"w")
            hutil.log("Start mdsd "+str(command))
            mdsd = subprocess.Popen(command,
                                     cwd=WorkDir,
                                     stdout=mdsd_log,
                                     stderr=mdsd_log,
                                     env=copy_env)

            with open(MDSDPidFile,"w") as pidfile:
                pidfile.write(str(os.getpid())+'\n')
                pidfile.write(str(mdsd.pid)+'\n')
                pidfile.close()

            last_mdsd_start_time = datetime.datetime.now()
            last_error_time = last_mdsd_start_time
            omi_installed = True
            omicli_path = "/opt/omi/bin/omicli"
            omicli_noop_query_cmd = omicli_path + " noop"
            # Continuously monitors mdsd process
            while True:
                time.sleep(30)
                if " ".join(get_mdsd_process()).find(str(mdsd.pid)) < 0 and len(get_mdsd_process()) >= 2:
                    mdsd.kill()
                    hutil.log("Another process is started, now exit")
                    return
                if mdsd.poll() is not None:     # if mdsd has terminated
                    time.sleep(60)
                    mdsd_log.flush()
                    break

                # mdsd is now up for at least 30 seconds.

                # Mitigate if memory leak is suspected.
                mdsd_memory_leak_suspected, mdsd_memory_usage_in_KB = check_suspected_memory_leak(mdsd.pid, hutil.error)
                if mdsd_memory_leak_suspected:
                    memory_leak_msg = "Suspected mdsd memory leak (Virtual memory usage: {0}MB). " \
                                      "Recycling mdsd to self-mitigate.".format(int((mdsd_memory_usage_in_KB+1023)/1024))
                    hutil.log(memory_leak_msg)
                    # Add a telemetry for a possible statistical analysis
                    waagent.AddExtensionEvent(name=hutil.get_name(),
                                              op=waagent.WALAEventOperation.HeartBeat,
                                              isSuccess=True,
                                              version=hutil.get_extension_version(),
                                              message=memory_leak_msg)
                    mdsd.kill()
                    break

                # Issue #128 LAD should restart OMI if it crashes
                omi_was_installed = omi_installed   # Remember the OMI install status from the last iteration
                omi_installed = os.path.isfile(omicli_path)

                if omi_was_installed and not omi_installed:
                    hutil.log("OMI is uninstalled. This must have been intentional and externally done. Will no longer check if OMI is up and running.")

                omi_reinstalled = not omi_was_installed and omi_installed
                if omi_reinstalled:
                    hutil.log("OMI is reinstalled. Will resume checking if OMI is up and running.")

                should_restart_omi = False
                if omi_installed:
                    cmd_exit_status, cmd_output = RunGetOutput(cmd=omicli_noop_query_cmd, should_log=False)
                    should_restart_omi = cmd_exit_status is not 0
                    if should_restart_omi:
                        hutil.error("OMI noop query failed. Output: " + cmd_output + ". OMI crash suspected. Restarting OMI and sending SIGHUP to mdsd after 5 seconds.")
                        omi_restart_msg = RunGetOutput("/opt/omi/bin/service_control restart")[1]
                        hutil.log("OMI restart result: " + omi_restart_msg)
                        time.sleep(5)

                should_signal_mdsd = should_restart_omi or omi_reinstalled
                if should_signal_mdsd:
                    omi_up_and_running = RunGetOutput(omicli_noop_query_cmd)[0] is 0
                    if omi_up_and_running:
                        mdsd.send_signal(signal.SIGHUP)
                        hutil.log("SIGHUP sent to mdsd")
                    else:   # OMI restarted but not staying up...
                        log_msg = "OMI restarted but not staying up. Will be restarted in the next iteration."
                        hutil.error(log_msg)
                        # Also log this issue on syslog as well
                        syslog.openlog('diagnostic.py', syslog.LOG_PID, syslog.LOG_DAEMON)  # syslog.openlog(ident, logoption, facility) -- not taking kw args in Python 2.6
                        syslog.syslog(syslog.LOG_ALERT, log_msg)    # syslog.syslog(priority, message) -- not taking kw args
                        syslog.closelog()

                if not os.path.exists(monitor_file_path):
                    continue
                monitor_file_ctime = datetime.datetime.strptime(time.ctime(int(os.path.getctime(monitor_file_path))), "%a %b %d %H:%M:%S %Y")
                if last_error_time >= monitor_file_ctime:
                    continue
                last_error_time = monitor_file_ctime
                last_error = tail(monitor_file_path)
                if len(last_error) > 0 and (datetime.datetime.now() - last_error_time) < datetime.timedelta(minutes=30):
                    hutil.log("Error in MDSD:"+last_error)
                    hutil.do_status_report(ExtensionOperationType, "success", '1', "message in /var/log/mdsd.err:"+str(last_error_time)+":"+last_error)

            # mdsd terminated.
            if mdsd_log:
                mdsd_log.close()
                mdsd_log = None

            # Check if this is NOT a quick crash -- we consider a crash quick
            # if it's within 30 minutes from the start time. If it's not quick,
            # we just continue by restarting mdsd.
            mdsd_up_time = datetime.datetime.now() - last_mdsd_start_time
            if mdsd_up_time > datetime.timedelta(minutes=30):
                mdsd_terminated_msg = "MDSD terminated after "+str(mdsd_up_time)+". " + tail(mdsd_log_path) + tail(monitor_file_path)
                hutil.log(mdsd_terminated_msg)
                num_quick_consecutive_crashes = 0
                continue

            # It's a quick crash. Log error and add an extension event.
            num_quick_consecutive_crashes += 1

            error = "MDSD crash(uptime=" + str(mdsd_up_time) + "):" + tail(mdsd_log_path) + tail(monitor_file_path)
            hutil.error("MDSD crashed:"+error)

            # Needs to reset rsyslog omazurelinuxmds config before retrying mdsd
            install_rsyslogom()

        # mdsd all 3 allowed quick/consecutive crashes exhausted
        hutil.do_status_report(ExtensionOperationType, "error", '1', "mdsd stopped:"+error)

        try:
            waagent.AddExtensionEvent(name=hutil.get_name(),
                                      op=ExtensionOperationType,
                                      isSuccess=False,
                                      version=hutil.get_extension_version(),
                                      message=error)
        except Exception:
            pass

    except Exception as e:
        if mdsd_log:
            hutil.error("Error :" + tail(mdsd_log_path))
        hutil.error(("Failed to launch mdsd with error:{0},"
                     "stacktrace:{1}").format(e, traceback.format_exc()))
        hutil.do_status_report(ExtensionOperationType, 'error', '1', 'Launch script failed:{0}'.format(e))
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=ExtensionOperationType,
                                  isSuccess=False,
                                  version=hutil.get_extension_version(),
                                  message="Launch script failed:"+str(e))
    finally:
        if mdsd_log:
            mdsd_log.close()


def stop_mdsd():
    pids = get_mdsd_process()
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
        pids = get_mdsd_process()
        if not pids:
            hutil.log("stop_mdsd(): All processes successfully terminated")
            terminated = True
        else:
            hutil.log("stop_mdsd() terminate check #{0}: Processes not terminated yet, rechecking in 2 seconds".format(num_checked))

    if not terminated:
        kill_cmd = "kill -9 " + " ".join(get_mdsd_process())
        hutil.log("stop_mdsd(): Processes not terminated in 20 seconds. Sending SIGKILL (" + kill_cmd + ")")
        RunGetOutput(kill_cmd)

    RunGetOutput("rm "+MDSDPidFile)

    return 0, "Terminated" if terminated else "SIGKILL'ed"


def get_mdsd_process():
    mdsd_pids = []
    if not os.path.exists(MDSDPidFile):
        return mdsd_pids

    with open(MDSDPidFile,"r") as pidfile:
        for pid in pidfile.readlines():
            is_still_alive = waagent.RunGetOutput("cat /proc/"+pid.strip()+"/cmdline",chk_err=False)[1]
            if is_still_alive.find('/waagent/') > 0 :
                mdsd_pids.append(pid.strip())
            else:
                hutil.log("return not alive "+is_still_alive.strip())
    return mdsd_pids


def install_omi():
    need_install_omi = 0
    need_fresh_install_omi = not os.path.exists('/opt/omi/bin/omiserver')

    isMysqlInstalled = RunGetOutput("which mysql")[0] is 0
    isApacheInstalled = RunGetOutput("which apache2 || which httpd || which httpd2")[0] is 0

    # Explicitly uninstall apache-cimprov & mysql-cimprov on rpm-based distros
    # to avoid hitting the scx upgrade issue (from 1.6.2-241 to 1.6.2-337)
    if ('OMI-1.0.8-4' in RunGetOutput('/opt/omi/bin/omiserver -v', should_log=False)[1]) \
            and ('rpm' in distConfig['installrequiredpackage']):
        RunGetOutput('rpm --erase apache-cimprov', should_log=False)
        RunGetOutput('rpm --erase mysql-cimprov', should_log=False)

    if 'OMI-1.0.8-6' not in RunGetOutput('/opt/omi/bin/omiserver -v')[1]:
        need_install_omi=1
    if isMysqlInstalled and not os.path.exists("/opt/microsoft/mysql-cimprov"):
        need_install_omi=1
    if isApacheInstalled and not os.path.exists("/opt/microsoft/apache-cimprov"):
        need_install_omi=1

    if need_install_omi:
        hutil.log("Begin omi installation.")
        isOmiInstalledSuccessfully = False
        maxTries = 5      # Try up to 5 times to install OMI
        for trialNum in range(1, maxTries+1):
            isOmiInstalledSuccessfully = RunGetOutput(distConfig["installomi"])[0] is 0
            if isOmiInstalledSuccessfully:
                break
            hutil.error("OMI install failed (trial #" + str(trialNum) + ").")
            if trialNum < maxTries:
                hutil.error("Retrying in 30 seconds...")
                time.sleep(30)
        if not isOmiInstalledSuccessfully:
            hutil.error("OMI install failed " + str(maxTries) + " times. Giving up...")
            return 1, "OMI install failed " + str(maxTries) + " times"

    shouldRestartOmi = False

    # Issue #265. OMI httpsport shouldn't be reconfigured when LAD is re-enabled or just upgraded.
    # In other words, OMI httpsport config should be updated only on a fresh OMI install.
    if need_fresh_install_omi:
        # Check if OMI is configured to listen to any non-zero port and reconfigure if so.
        omi_listens_to_nonzero_port = RunGetOutput(r"grep '^\s*httpsport\s*=' /etc/opt/omi/conf/omiserver.conf | grep -v '^\s*httpsport\s*=\s*0\s*$'")[0] is 0
        if omi_listens_to_nonzero_port:
            RunGetOutput("/opt/omi/bin/omiconfigeditor httpsport -s 0 < /etc/opt/omi/conf/omiserver.conf > /etc/opt/omi/conf/omiserver.conf_temp")
            RunGetOutput("mv /etc/opt/omi/conf/omiserver.conf_temp /etc/opt/omi/conf/omiserver.conf")
            shouldRestartOmi = True

    # Quick and dirty way of checking if mysql/apache process is running
    isMysqlRunning = RunGetOutput("ps -ef | grep mysql | grep -v grep")[0] is 0
    isApacheRunning = RunGetOutput("ps -ef | grep -E 'httpd|apache2' | grep -v grep")[0] is 0

    if os.path.exists("/opt/microsoft/mysql-cimprov/bin/mycimprovauth") and isMysqlRunning:
        mysqladdress = g_ext_settings.read_protected_config("mysqladdress")
        mysqlusername = g_ext_settings.read_protected_config("mysqlusername")
        mysqlpassword = g_ext_settings.read_protected_config("mysqlpassword")
        RunGetOutput("/opt/microsoft/mysql-cimprov/bin/mycimprovauth default "+mysqladdress+" "+mysqlusername+" '"+mysqlpassword+"'", should_log=False)
        shouldRestartOmi = True

    if os.path.exists("/opt/microsoft/apache-cimprov/bin/apache_config.sh") and isApacheRunning:
        RunGetOutput("/opt/microsoft/apache-cimprov/bin/apache_config.sh -c")
        shouldRestartOmi = True

    if shouldRestartOmi:
        RunGetOutput("/opt/omi/bin/service_control restart")

    return 0, "omi installed"


def uninstall_omi():
    isApacheRunning = RunGetOutput("ps -ef | grep -E 'httpd|apache' | grep -v grep")[0] is 0
    if os.path.exists("/opt/microsoft/apache-cimprov/bin/apache_config.sh") and isApacheRunning:
        RunGetOutput("/opt/microsoft/apache-cimprov/bin/apache_config.sh -u")
    hutil.log("omi will not be uninstalled")
    return 0, "do nothing"


rsyslog_om_mdsd_syslog_conf_prefix = "/etc/rsyslog.d/10-omazurelinuxmds"
rsyslog_om_mdsd_syslog_conf_path = rsyslog_om_mdsd_syslog_conf_prefix + ".conf"
rsyslog_om_mdsd_file_conf_path = "/etc/rsyslog.d/10-omazurelinuxmds-imfile.conf"

def uninstall_rsyslogom():
    #return RunGetOutput(distConfig['uninstallmdsd'])
    error,rsyslog_info = RunGetOutput(distConfig['checkrsyslog'])
    rsyslog_module_path = None
    match = re.search("(.*)"+rsyslog_module_for_check,rsyslog_info)
    if match:
       rsyslog_module_path = match.group(1)
    if rsyslog_module_path == None:
        return 1,"rsyslog not installed"
    if os.path.exists(rsyslog_om_mdsd_syslog_conf_path):
        RunGetOutput("rm -f {0}/omazuremds.so {1}*".format(rsyslog_module_path,
                                                           rsyslog_om_mdsd_syslog_conf_prefix))

    if distConfig.has_key("restartrsyslog"):
        RunGetOutput(distConfig["restartrsyslog"])
    else:
        RunGetOutput("service rsyslog restart")

    return 0,"rm omazurelinuxmds done"


def install_rsyslogom():
    error, rsyslog_info = RunGetOutput(distConfig['checkrsyslog'])
    rsyslog_module_path = None
    match = re.search("(.*)"+rsyslog_module_for_check, rsyslog_info)
    if match:
       rsyslog_module_path = match.group(1)
    if rsyslog_module_path == None:
        return 1,"rsyslog not installed"

    #error,output = RunGetOutput(distConfig['installmdsd'])

    lad_rsyslog_om_folder = None
    for v in {'8':'rsyslog8','7':'rsyslog7','5':'rsyslog5'}.items():
        if re.search('Version\s*:\s*'+v[0],rsyslog_info):
            lad_rsyslog_om_folder = v[1]

    if lad_rsyslog_om_folder and rsyslog_module_path:
        # Remove old-path conf files to avoid confusion
        RunGetOutput("rm -f /etc/rsyslog.d/omazurelinuxmds.conf /etc/rsyslog.d/omazurelinuxmds_fileom.conf")
        # Copy necesssary files. First, stop rsyslog to avoid SEGV on overwriting omazuremds.so.
        if distConfig.has_key("stoprsyslog"):
            RunGetOutput(distConfig["stoprsyslog"])
        else:
            RunGetOutput("service rsyslog stop")
        RunGetOutput("cp -f {0}/omazuremds.so {1}".format(lad_rsyslog_om_folder, rsyslog_module_path))  # Copy the *.so mdsd rsyslog output module
        RunGetOutput("cp -f {0}/omazurelinuxmds.conf {1}".format(lad_rsyslog_om_folder, rsyslog_om_mdsd_syslog_conf_path))  # Copy mdsd rsyslog syslog conf file
        RunGetOutput("cp -f {0} {1}".format(imfile_config_filename, rsyslog_om_mdsd_file_conf_path))  # Copy mdsd rsyslog filecfg conf file
        # Update __MDSD_SOCKET_FILE_PATH__ with the valid path for the latest rsyslog module (5/7/8)
        mdsd_json_socket_file_path = MDSDFileResourcesPrefix + "_json.socket"
        cmd_to_run = "sed -i 's#__MDSD_SOCKET_FILE_PATH__#{0}#g' {1}"
        RunGetOutput(cmd_to_run.format(mdsd_json_socket_file_path, rsyslog_om_mdsd_syslog_conf_path))

    else:
        return 1,"rsyslog version can't be detected"

    if distConfig.has_key("restartrsyslog"):
        RunGetOutput(distConfig["restartrsyslog"])
    else:
        RunGetOutput("service rsyslog restart")
    return 0,"install mdsdom completed"


def install_required_package():
    packages = distConfig['packages']

    errorcode = 0
    output_all = ""

    if 'installrequiredpackages' in distConfig:
        package_str = str.join(' ', packages)
        if package_str:
            cmd = distConfig['installrequiredpackages'].replace('PACKAGES', package_str).replace('COUNT', str(len(packages)))
            hutil.log(cmd)
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable='/bin/bash')
            timeout=360
            time.sleep(1)
            while process.poll() is None and timeout > 0:
                time.sleep(10)
                timeout-=1
            if process.poll() is None:
                hutil.error("Timeout when execute:"+cmd)
                errorcode = 1
                process.kill()
            output_all, unused_err = process.communicate()
            errorcode += process.returncode
            return errorcode,str(output_all)
    else:
        cmd_temp = distConfig['installrequiredpackage']
        if len(cmd_temp) >0:
            for p in packages:
                cmd = cmd_temp.replace("PACKAGE",p)
                hutil.log(cmd)
                process = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True,executable='/bin/bash')
                timeout=360
                time.sleep(1)
                while process.poll() is None and timeout > 0:
                    time.sleep(10)
                    timeout-=1
                if process.poll() is None:
                    hutil.error("Timeout when execute:"+cmd)
                    errorcode = 1
                    process.kill()
                output, unused_err = process.communicate()
                output_all += output
                errorcode+=process.returncode
            return errorcode,str(output_all)
    return 0,"not pacakge need install"


if __name__ == '__main__' :
    if len(sys.argv) <= 1:
        print('No command line argument was specified.\nYou must be executing this program manually for testing.\n'
              'In that case, one of "install", "enable", "disable", "uninstall", or "update" should be given.')
    else:
        try:
            main(sys.argv[1])
        except Exception as e:
            ext_version = ET.parse('manifest.xml').find('{http://schemas.microsoft.com/windowsazure}Version').text
            waagent.AddExtensionEvent(name="Microsoft.OSTCExtension.LinuxDiagnostic",
                                      op=wala_event_type_for_telemetry(get_extension_operation_type(sys.argv[1])),
                                      isSuccess=False,
                                      version=ext_version,
                                      message="Unknown exception thrown from diagnostic.py.\n"
                                              "Error: {0}\nStackTrace: {1}".format(e, traceback.format_exc()))

